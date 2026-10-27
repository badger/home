#!/usr/bin/env node
// Badge bridge: a small authenticated front door that badge apps reach over
// plain HTTPS (Tailscale Funnel), so the badge never joins the tailnet itself.
//
//   GET  /health                         unauthenticated liveness probe
//   GET  /t3/status                      compact T3 Code thread status
//   POST /gateway/v1/chat/completions    clamped proxy to an LLM gateway
//
// Every path also works under /badge/... so it can sit behind
// `tailscale funnel --set-path /badge`. Configuration comes from the
// environment; see README.md.

import crypto from "node:crypto";
import http from "node:http";
import { pathToFileURL } from "node:url";

import { T3Status, parseSources } from "./t3.mjs";

const MAX_BODY_BYTES = 16 * 1024;
const FAILED_AUTH_PER_MINUTE = 30;
// The badge simulator runs apps in a browser page on a loopback origin.
const LOOPBACK_ORIGIN = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/;

export class ConfigError extends Error {}

function list(value) {
  return (value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function positiveInt(source, name, fallback) {
  const raw = source[name];
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value <= 0) {
    throw new ConfigError(`${name} must be a positive integer`);
  }
  return value;
}

function baseUrl(source, name) {
  const raw = (source[name] || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new ConfigError(`${name} must be a URL`);
  }
  if (!["http:", "https:", "ws:", "wss:"].includes(url.protocol)) {
    throw new ConfigError(`${name} must use http(s) or ws(s)`);
  }
  return raw.replace(/\/+$/, "");
}

export function loadConfig(source = process.env) {
  const tokens = list(source.BADGE_BRIDGE_TOKEN);
  if (!tokens.length) throw new ConfigError("BADGE_BRIDGE_TOKEN is required");
  if (tokens.some((token) => token.length < 24)) {
    throw new ConfigError("Each BADGE_BRIDGE_TOKEN must be at least 24 characters");
  }
  const gatewayUrl = baseUrl(source, "BADGE_BRIDGE_GATEWAY_URL");
  if (gatewayUrl && !source.BADGE_BRIDGE_GATEWAY_KEY) {
    throw new ConfigError("BADGE_BRIDGE_GATEWAY_KEY is required with BADGE_BRIDGE_GATEWAY_URL");
  }
  let t3Sources;
  try {
    t3Sources = parseSources(source);
  } catch (error) {
    throw new ConfigError(error.message);
  }
  return {
    host: source.BADGE_BRIDGE_HOST || "127.0.0.1",
    port: positiveInt(source, "BADGE_BRIDGE_PORT", 8787),
    tokens,
    ratePerMinute: positiveInt(source, "BADGE_BRIDGE_RATE_PER_MIN", 60),
    gateway: gatewayUrl
      ? {
          url: gatewayUrl,
          key: source.BADGE_BRIDGE_GATEWAY_KEY,
          models: list(source.BADGE_BRIDGE_GATEWAY_MODELS),
          maxTokens: positiveInt(source, "BADGE_BRIDGE_GATEWAY_MAX_TOKENS", 400),
          timeoutMs: positiveInt(source, "BADGE_BRIDGE_GATEWAY_TIMEOUT_MS", 30000),
        }
      : null,
    t3Sources,
  };
}

const digest = (value) => crypto.createHash("sha256").update(value).digest();

export function errorBody(message) {
  return { error: { message } };
}

class HttpError extends Error {
  constructor(status, message, headers = {}) {
    super(message);
    this.status = status;
    this.headers = headers;
  }
}

function send(res, status, body, headers = {}) {
  const payload = Buffer.isBuffer(body) ? body : Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
    ...headers,
  });
  res.end(payload);
}

function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    const declared = Number(req.headers["content-length"] || 0);
    if (declared > limit) {
      reject(new HttpError(413, "badge bridge: request body too large"));
      req.resume();
      return;
    }
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > limit) {
        reject(new HttpError(413, "badge bridge: request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

export function prepareChatRequest(body, gateway) {
  let payload;
  try {
    payload = JSON.parse(body.toString("utf8"));
  } catch {
    throw new HttpError(400, "badge bridge: body must be JSON");
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new HttpError(400, "badge bridge: body must be a JSON object");
  }
  if (typeof payload.model !== "string" || !payload.model) {
    throw new HttpError(400, "badge bridge: model is required");
  }
  if (gateway.models.length && !gateway.models.includes(payload.model)) {
    throw new HttpError(400, `badge bridge: model ${payload.model} is not allowed`);
  }
  if (!Array.isArray(payload.messages) || !payload.messages.length) {
    throw new HttpError(400, "badge bridge: messages are required");
  }
  const clamp = (value) =>
    Number.isInteger(value) && value > 0 ? Math.min(value, gateway.maxTokens) : gateway.maxTokens;
  payload.max_tokens = clamp(payload.max_tokens);
  if ("max_completion_tokens" in payload) {
    payload.max_completion_tokens = clamp(payload.max_completion_tokens);
  }
  payload.stream = false;
  delete payload.stream_options;
  return payload;
}

export function createBridge(config, options = {}) {
  const fetchImpl = options.fetch || globalThis.fetch;
  const now = options.now || Date.now;
  const log = options.log || ((line) => console.log(line));
  const t3 = options.t3 || null;
  const tokenDigests = config.tokens.map(digest);
  const windows = new Map();
  let failures = { start: 0, count: 0 };

  function authenticate(req) {
    const header = req.headers.authorization || "";
    const match = /^Bearer\s+(.+)$/i.exec(header);
    if (match) {
      const presented = digest(match[1].trim());
      const index = tokenDigests.findIndex((known) => crypto.timingSafeEqual(known, presented));
      if (index >= 0) return index;
    }
    const time = now();
    if (time - failures.start >= 60000) failures = { start: time, count: 0 };
    failures.count += 1;
    if (failures.count > FAILED_AUTH_PER_MINUTE) {
      throw new HttpError(429, "badge bridge: too many failed attempts", { "Retry-After": "60" });
    }
    throw new HttpError(401, "badge bridge: unauthorized");
  }

  function rateLimit(tokenIndex) {
    const time = now();
    let window = windows.get(tokenIndex);
    if (!window || time - window.start >= 60000) {
      window = { start: time, count: 0 };
      windows.set(tokenIndex, window);
    }
    window.count += 1;
    if (window.count > config.ratePerMinute) {
      const retry = Math.max(1, Math.ceil((window.start + 60000 - time) / 1000));
      throw new HttpError(429, "badge bridge rate limit", { "Retry-After": String(retry) });
    }
  }

  async function proxyChat(req, res) {
    const gateway = config.gateway;
    if (!gateway) throw new HttpError(503, "badge bridge: gateway not configured");
    const payload = prepareChatRequest(await readBody(req, MAX_BODY_BYTES), gateway);
    let upstream;
    try {
      upstream = await fetchImpl(`${gateway.url}/v1/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${gateway.key}`,
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(gateway.timeoutMs),
      });
    } catch (error) {
      if (error && (error.name === "TimeoutError" || error.name === "AbortError")) {
        throw new HttpError(504, "badge bridge: gateway timed out");
      }
      throw new HttpError(502, "badge bridge: gateway unreachable");
    }
    const bytes = Buffer.from(await upstream.arrayBuffer());
    send(res, upstream.status, bytes, {
      "Content-Type": upstream.headers.get("content-type") || "application/json",
    });
    return upstream.status;
  }

  async function handle(req, res) {
    const started = now();
    let status = 500;
    let path = "?";
    try {
      const url = new URL(req.url || "/", "http://bridge.invalid");
      path = url.pathname.replace(/^\/badge(?=\/|$)/, "") || "/";
      const origin = req.headers.origin;
      if (origin && LOOPBACK_ORIGIN.test(origin)) {
        res.setHeader("Access-Control-Allow-Origin", origin);
        res.setHeader("Vary", "Origin");
        if (req.method === "OPTIONS") {
          res.writeHead((status = 204), {
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
            "Access-Control-Max-Age": "600",
          });
          res.end();
          return;
        }
      }
      if (path === "/health" && (req.method === "GET" || req.method === "HEAD")) {
        send(res, (status = 200), { ok: true });
        return;
      }
      const tokenIndex = authenticate(req);
      rateLimit(tokenIndex);
      if (path === "/t3/status" && req.method === "GET") {
        if (!t3) throw new HttpError(503, "badge bridge: T3 Code not configured");
        send(res, (status = 200), t3.status(url.searchParams.get("src")));
        return;
      }
      if (path === "/gateway/v1/chat/completions" && req.method === "POST") {
        status = await proxyChat(req, res);
        return;
      }
      throw new HttpError(404, "badge bridge: not found");
    } catch (error) {
      if (error instanceof HttpError) {
        status = error.status;
        if (!res.headersSent) send(res, status, errorBody(error.message), error.headers);
      } else {
        status = 500;
        log(`bridge error on ${path}: ${error && error.message}`);
        if (!res.headersSent) send(res, status, errorBody("badge bridge: internal error"));
      }
    } finally {
      // Never log headers or bodies: they carry tokens and prompts.
      log(`${new Date(started).toISOString()} ${req.method} ${path} ${status} ${now() - started}ms`);
    }
  }

  return { handle };
}

export function startServer(config, options = {}) {
  const bridge = createBridge(config, options);
  const server = http.createServer((req, res) => {
    bridge.handle(req, res);
  });
  server.requestTimeout = 60000;
  server.headersTimeout = 15000;
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(options.port ?? config.port, config.host, () => resolve(server));
  });
}

async function main() {
  let config;
  try {
    config = loadConfig();
  } catch (error) {
    if (error instanceof ConfigError) {
      console.error(`badge bridge: ${error.message}`);
      process.exit(2);
    }
    throw error;
  }
  let t3 = null;
  if (config.t3Sources.length) {
    t3 = new T3Status(config.t3Sources);
    t3.start();
  }
  const server = await startServer(config, { t3 });
  const { port } = server.address();
  console.log(
    `badge bridge listening on http://${config.host}:${port} ` +
      `(gateway ${config.gateway ? "on" : "off"}, t3 ${t3 ? "on" : "off"})`,
  );
  const stop = () => {
    if (t3) t3.stop();
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 2000).unref();
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
