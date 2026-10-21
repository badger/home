/**
 * AgentViz's own parsers -> privacy-filtered badge snapshots, over local UDP.
 * No agent hooks, AI services, transcript server, or upstream modification.
 */
import { build } from "esbuild";
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import dgram from "node:dgram";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { isIPv4 } from "node:net";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

export const REVISION = "b4c924022745a588497098c241a91458213cf1a3";
export const MAX_SOURCE = 16 * 1024 * 1024;
export const MAX_PACKET = 4096;
const TRACKS = ["reasoning", "tool_call", "context", "output", "agent"];
const LIMIT = 2147483647;
const integer = value => Math.max(0, Math.min(LIMIT, Math.round(Number(value) || 0)));
const safeLabel = (value, limit, fallback) =>
  String(value || fallback).replace(/[^a-zA-Z0-9_. -]/g, "").slice(0, limit).trim() || fallback;

export async function loadParser(source) {
  const revision = execFileSync("git", ["-C", source, "rev-parse", "HEAD"],
    { encoding: "utf8" }).trim();
  if (revision !== REVISION) throw new Error(`Use AgentViz revision ${REVISION}`);
  // Bundle upstream TypeScript and extensionless imports without copying parsers.
  const result = await build({
    entryPoints: [path.join(source, "src/lib/parseSession.ts")],
    bundle: true, write: false, platform: "node", format: "esm", logLevel: "silent",
  });
  return import("data:text/javascript;base64," +
    Buffer.from(result.outputFiles[0].text).toString("base64"));
}

export function completeText(buffer) {
  if (buffer.length > MAX_SOURCE) throw new Error("Session too large");
  const text = buffer.toString("utf8");
  // Standalone JSON imports are valid without a trailing newline.
  try {
    const value = JSON.parse(text);
    if (value && typeof value === "object"
        && typeof value.type !== "string" && typeof value.kind !== "number") return text;
  } catch {
    // JSONL is only consumed through its last complete record boundary.
  }
  return text.slice(0, text.lastIndexOf("\n") + 1);
}

export function snapshot(parsed, format) {
  const all = parsed?.events || [];
  const metadata = parsed?.metadata || {};
  const issues = metadata.parseIssues;
  if (issues && (issues.malformedLines > 0 || issues.invalidEvents > 0)) {
    throw new Error("Invalid session");
  }
  const toolCounts = new Map();
  for (const event of all) {
    if (event.track === "tool_call") {
      const name = safeLabel(event.toolName, 18, "tool");
      toolCounts.set(name, (toolCounts.get(name) || 0) + 1);
    }
  }
  const events = all.slice(-24).map((event, i) => {
    const track = TRACKS.indexOf(event.track);
    if (track < 0) throw new Error("Invalid session");
    const lifecycle = { "subagent.started": "Agent started", "subagent.completed": "Agent done",
      "subagent.failed": "Agent failed" };
    const title = track === 1 ? safeLabel(event.toolName, 18, "tool") :
      track === 0 ? "Reasoning" : track === 4 ? (lifecycle[event.raw?.type] || "Agent event") :
      event.agent === "user" ? "User input" : track === 3 ? "Response" : "Context";
    return [all.length - Math.min(24, all.length) + i,
      integer(event.t * 1000), integer(event.duration * 1000), track, title,
      safeLabel(event.agentName || event.agent, 12, "assistant"),
      event.isError ? 1 : 0, integer(event.turnIndex)];
  });
  const usage = metadata.tokenUsage;
  return {
    state: all.length ? "ok" : "waiting",
    message: all.length ? "" : "Waiting for events",
    source: safeLabel(format, 16, "session"),
    metrics: [integer(all.length), integer(metadata.totalTurns),
      integer(metadata.totalToolCalls), integer(metadata.errorCount),
      integer(metadata.duration * 1000),
      usage?.inputTokens == null ? -1 : integer(usage.inputTokens),
      usage?.outputTokens == null ? -1 : integer(usage.outputTokens)],
    events,
    tools: [...toolCounts].sort((a, b) => b[1] - a[1]).slice(0, 4),
  };
}

export function encode(payload, config, epoch, seq) {
  const data = Buffer.from(JSON.stringify({
    v: 1, token: config.token, epoch, seq, ...payload,
  }));
  if (data.length > MAX_PACKET) throw new Error("Badge snapshot exceeds packet limit");
  return data;
}

export function validateConfig(config) {
  if (!config || !isIPv4(config.badge) || config.badge === "0.0.0.0" ||
      config.badge === "255.255.255.255" ||
      !/^[0-9a-f]{32}$/.test(config.token || "") ||
      !Number.isInteger(config.port ?? 9138) ||
      (config.port ?? 9138) < 1 || (config.port ?? 9138) > 65535) {
    throw new Error("Config requires badge IPv4, a 32-character hex token, and valid port");
  }
  return { ...config, port: config.port ?? 9138 };
}

export function validateURL(address) {
  const url = new URL(address);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
      || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("--url must be a loopback AgentViz HTTP origin, e.g. http://127.0.0.1:5173");
  }
  return url;
}

async function boundedBytes(stream) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of stream) {
    bytes += chunk.length;
    if (bytes > MAX_SOURCE) throw new Error("Session too large");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

export async function readSource({ session, url }) {
  if (session) {
    const info = await stat(session);
    if (!info.isFile()) throw new Error("Source unavailable");
    if (info.size > MAX_SOURCE) throw new Error("Session too large");
    return completeText(await boundedBytes(createReadStream(session)));
  }
  const response = await fetch(new URL("/api/file", validateURL(url)), {
    signal: AbortSignal.timeout(2500), redirect: "error",
  });
  if (!response.ok) throw new Error("Source unavailable");
  return completeText(await boundedBytes(response.body));
}

function headerOnly(text, format) {
  const types = format === "copilot-cli" ? ["session.start", "session.resume"] :
    format === "codex" ? ["session_meta", "turn_context"] : [];
  const records = text.split("\n").filter(line => line.trim()).map(line => JSON.parse(line));
  return records.length > 0 && records.every(record => types.includes(record.type));
}

export class Bridge {
  constructor(parser, source, config, socket) {
    this.parser = parser;
    this.source = source;
    this.config = validateConfig(config);
    this.socket = socket;
    this.epoch = randomBytes(16).toString("hex");
    this.seq = 0;
    this.previous = null;
    this.identities = [];
    this.payload = null;
    this.lastError = "";
  }

  async tick() {
    let payload;
    try {
      const text = await readSource(this.source);
      if (text !== this.previous) {
        const format = text.trim() ? this.parser.detectFormat(text) : "session";
        const parsed = text.trim() ? this.parser.parseSession(text) : null;
        if (text.trim() && !parsed && !headerOnly(text, format)) {
          throw new Error("Invalid session");
        }
        const identities = (parsed?.events || []).map(event => JSON.stringify([
          event.t, event.track, event.agent, event.toolCallId,
          event.agentName, event.raw?.id, event.raw?.type,
        ]));
        const reordered = this.identities.some((id, index) => identities[index] !== id);
        if (this.previous !== null && (!text.startsWith(this.previous) || reordered)) {
          this.epoch = randomBytes(16).toString("hex");
          this.seq = 0;
        }
        this.payload = snapshot(parsed, format);
        this.identities = identities;
        this.previous = text;
      }
      payload = this.payload;
      if (this.lastError) console.error("AgentViz source recovered");
      this.lastError = "";
    } catch (error) {
      const message = error instanceof SyntaxError ? "Invalid session" :
        ["Invalid session", "Session too large"].includes(error.message)
          ? error.message : "Source unavailable";
      if (message !== this.lastError) console.error(`AgentViz: ${message}`);
      this.lastError = message;
      payload = { state: "error", message, source: "session",
        metrics: [0, 0, 0, 0, 0, -1, -1], events: [], tools: [] };
    }
    const packet = encode(payload, this.config, this.epoch, this.seq++);
    await new Promise((resolve, reject) =>
      this.socket.send(packet, this.config.port, this.config.badge,
        error => error ? reject(error) : resolve()));
  }
}

async function main() {
  const { values } = parseArgs({ options: {
    source: { type: "string" }, session: { type: "string" }, url: { type: "string" },
    config: { type: "string" }, once: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  } });
  if (values.help) {
    console.log("node bridge.mjs --source /path/to/agentviz --config private.json " +
      "(--session /path/to/session.jsonl | --url http://127.0.0.1:5173) [--once]");
    return;
  }
  if (!values.source || !values.config || Boolean(values.session) === Boolean(values.url)) {
    throw new Error("Provide --source, --config, and exactly one of --session or --url");
  }
  if (values.url) validateURL(values.url);
  const config = validateConfig(JSON.parse(await readFile(values.config, "utf8")));
  const parser = await loadParser(path.resolve(values.source));
  const socket = dgram.createSocket("udp4");
  let stopped = false;
  const stop = () => { stopped = true; };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
  try {
    const bridge = new Bridge(parser, values, config, socket);
    console.log(`AgentViz ${REVISION.slice(0, 12)} -> badge ${config.badge}:${config.port}`);
    console.log("Metadata only; LIVE FEED means bridge connected, not agent running.");
    do {
      await bridge.tick();
      if (!values.once && !stopped) await new Promise(resolve => setTimeout(resolve, 1000));
    } while (!values.once && !stopped);
  } finally {
    socket.close();
    process.removeListener("SIGINT", stop);
    process.removeListener("SIGTERM", stop);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => {
    console.error("AgentViz bridge:", error.message);
    process.exitCode = 1;
  });
}
