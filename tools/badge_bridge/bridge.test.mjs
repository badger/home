import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { ConfigError, loadConfig, startServer } from "./bridge.mjs";

const TOKEN = "t".repeat(32);
const GATEWAY_KEY = "sk-badge-test-key";

function makeFetch() {
  const calls = [];
  let reply = () =>
    new Response(JSON.stringify({ choices: [{ message: { content: "hi" } }] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  const fetch = async (url, init) => {
    calls.push({ url, init, body: JSON.parse(init.body) });
    return reply();
  };
  return { fetch, calls, setReply: (fn) => (reply = fn) };
}

describe("loadConfig", () => {
  test("requires a long token", () => {
    assert.throws(() => loadConfig({}), ConfigError);
    assert.throws(() => loadConfig({ BADGE_BRIDGE_TOKEN: "short" }), ConfigError);
  });

  test("requires a gateway key with a gateway url", () => {
    assert.throws(
      () => loadConfig({ BADGE_BRIDGE_TOKEN: TOKEN, BADGE_BRIDGE_GATEWAY_URL: "https://gw" }),
      ConfigError,
    );
  });

  test("parses lists and defaults", () => {
    const config = loadConfig({
      BADGE_BRIDGE_TOKEN: `${TOKEN}, ${"u".repeat(30)}`,
      BADGE_BRIDGE_GATEWAY_URL: "https://gw.example:8317/",
      BADGE_BRIDGE_GATEWAY_KEY: GATEWAY_KEY,
      BADGE_BRIDGE_GATEWAY_MODELS: "a, b",
    });
    assert.equal(config.tokens.length, 2);
    assert.equal(config.port, 8787);
    assert.equal(config.host, "127.0.0.1");
    assert.equal(config.gateway.url, "https://gw.example:8317");
    assert.deepEqual(config.gateway.models, ["a", "b"]);
    assert.equal(config.gateway.maxTokens, 400);
    assert.deepEqual(config.t3Sources, []);
  });

  test("parses T3 sources with per-source tokens", () => {
    const config = loadConfig({
      BADGE_BRIDGE_TOKEN: TOKEN,
      BADGE_BRIDGE_T3_SOURCES: "mbp@https://nt-mbp.example.ts.net/, desk-top@http://10.0.0.2:3773",
      BADGE_BRIDGE_T3_TOKEN_MBP: "tok-a",
      BADGE_BRIDGE_T3_TOKEN_DESK_TOP: "tok-b",
    });
    assert.deepEqual(
      config.t3Sources.map(({ name, url, token }) => [name, url, token]),
      [
        ["mbp", "https://nt-mbp.example.ts.net/", "tok-a"],
        ["desk-top", "http://10.0.0.2:3773", "tok-b"],
      ],
    );
    assert.throws(
      () => loadConfig({ BADGE_BRIDGE_TOKEN: TOKEN, BADGE_BRIDGE_T3_SOURCES: "mbp@https://x" }),
      /BADGE_BRIDGE_T3_TOKEN_MBP/,
    );
  });
});

describe("bridge server", () => {
  let server;
  let base;
  let upstream;
  let t3Snapshot;
  let clock;

  before(async () => {
    upstream = makeFetch();
    t3Snapshot = { ok: true, threads: [] };
    clock = { now: 1_000_000 };
    const config = loadConfig({
      BADGE_BRIDGE_TOKEN: TOKEN,
      BADGE_BRIDGE_RATE_PER_MIN: "5",
      BADGE_BRIDGE_GATEWAY_URL: "https://gateway.example:8317",
      BADGE_BRIDGE_GATEWAY_KEY: GATEWAY_KEY,
      BADGE_BRIDGE_GATEWAY_MODELS: "claude-haiku-4-5",
    });
    server = await startServer(config, {
      port: 0,
      fetch: upstream.fetch,
      now: () => clock.now,
      log: () => {},
      t3: { status: (only) => ({ ...t3Snapshot, ...(only ? { src: only } : {}) }) },
    });
    base = `http://127.0.0.1:${server.address().port}`;
  });

  after(() => server.close());

  const auth = { Authorization: `Bearer ${TOKEN}` };
  const nextMinute = () => {
    clock.now += 61_000;
  };

  test("health needs no auth, with or without the /badge prefix", async () => {
    for (const path of ["/health", "/badge/health"]) {
      const res = await fetch(base + path);
      assert.equal(res.status, 200);
      assert.deepEqual(await res.json(), { ok: true });
    }
  });

  test("rejects missing and wrong tokens with a JSON error", async () => {
    nextMinute();
    for (const headers of [{}, { Authorization: "Bearer nope" }]) {
      const res = await fetch(`${base}/badge/t3/status`, { headers });
      assert.equal(res.status, 401);
      assert.equal((await res.json()).error.message, "badge bridge: unauthorized");
    }
  });

  test("serves T3 status", async () => {
    nextMinute();
    t3Snapshot = { ok: true, threads: [{ title: "x" }] };
    const res = await fetch(`${base}/badge/t3/status`, { headers: auth });
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), t3Snapshot);
    const filtered = await fetch(`${base}/badge/t3/status?src=fate`, { headers: auth });
    assert.equal((await filtered.json()).src, "fate");
  });

  test("proxies chat with the gateway key, clamped tokens and no streaming", async () => {
    nextMinute();
    upstream.calls.length = 0;
    const res = await fetch(`${base}/badge/gateway/v1/chat/completions`, {
      method: "POST",
      headers: { ...auth, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-haiku-4-5",
        messages: [{ role: "user", content: "hello" }],
        max_tokens: 5000,
        stream: true,
        stream_options: { include_usage: true },
      }),
    });
    assert.equal(res.status, 200);
    assert.equal((await res.json()).choices[0].message.content, "hi");
    assert.ok(res.headers.get("content-length"));
    const [call] = upstream.calls;
    assert.equal(call.url, "https://gateway.example:8317/v1/chat/completions");
    assert.equal(call.init.headers.Authorization, `Bearer ${GATEWAY_KEY}`);
    assert.equal(call.body.max_tokens, 400);
    assert.equal(call.body.stream, false);
    assert.equal("stream_options" in call.body, false);
  });

  test("defaults max_tokens when missing and keeps smaller values", async () => {
    nextMinute();
    upstream.calls.length = 0;
    for (const max_tokens of [undefined, 200]) {
      await fetch(`${base}/gateway/v1/chat/completions`, {
        method: "POST",
        headers: auth,
        body: JSON.stringify({ model: "claude-haiku-4-5", messages: [{ role: "user", content: "x" }], max_tokens }),
      });
    }
    assert.deepEqual(
      upstream.calls.map((call) => call.body.max_tokens),
      [400, 200],
    );
  });

  test("refuses models outside the allowlist", async () => {
    nextMinute();
    const res = await fetch(`${base}/gateway/v1/chat/completions`, {
      method: "POST",
      headers: auth,
      body: JSON.stringify({ model: "muse-spark-1.3", messages: [{ role: "user", content: "x" }] }),
    });
    assert.equal(res.status, 400);
    assert.match((await res.json()).error.message, /not allowed/);
  });

  test("passes gateway errors through unchanged", async () => {
    nextMinute();
    upstream.setReply(
      () =>
        new Response(JSON.stringify({ error: { message: "upstream says no" } }), {
          status: 403,
          headers: { "content-type": "application/json" },
        }),
    );
    const res = await fetch(`${base}/gateway/v1/chat/completions`, {
      method: "POST",
      headers: auth,
      body: JSON.stringify({ model: "claude-haiku-4-5", messages: [{ role: "user", content: "x" }] }),
    });
    assert.equal(res.status, 403);
    assert.deepEqual(await res.json(), { error: { message: "upstream says no" } });
    upstream.setReply(() => new Response("{}", { status: 200 }));
  });

  test("reports an unreachable gateway as 502", async () => {
    nextMinute();
    upstream.setReply(() => {
      throw new TypeError("fetch failed");
    });
    const res = await fetch(`${base}/gateway/v1/chat/completions`, {
      method: "POST",
      headers: auth,
      body: JSON.stringify({ model: "claude-haiku-4-5", messages: [{ role: "user", content: "x" }] }),
    });
    assert.equal(res.status, 502);
    upstream.setReply(() => new Response("{}", { status: 200 }));
  });

  test("rejects oversized and malformed bodies", async () => {
    nextMinute();
    const big = await fetch(`${base}/gateway/v1/chat/completions`, {
      method: "POST",
      headers: auth,
      body: "x".repeat(20_000),
    });
    assert.equal(big.status, 413);
    const bad = await fetch(`${base}/gateway/v1/chat/completions`, {
      method: "POST",
      headers: auth,
      body: "not json",
    });
    assert.equal(bad.status, 400);
  });

  test("rate limits each token per minute", async () => {
    nextMinute();
    const statuses = [];
    for (let i = 0; i < 6; i += 1) {
      statuses.push((await fetch(`${base}/t3/status`, { headers: auth })).status);
    }
    assert.deepEqual(statuses, [200, 200, 200, 200, 200, 429]);
    const limited = await fetch(`${base}/t3/status`, { headers: auth });
    assert.equal((await limited.json()).error.message, "badge bridge rate limit");
    assert.ok(Number(limited.headers.get("retry-after")) >= 1);
  });

  test("locks out repeated bad tokens", async () => {
    nextMinute();
    let last;
    for (let i = 0; i < 31; i += 1) {
      last = await fetch(`${base}/t3/status`, { headers: { Authorization: "Bearer wrong" } });
    }
    assert.equal(last.status, 429);
  });

  test("answers CORS preflights only for loopback origins", async () => {
    nextMinute();
    const ok = await fetch(`${base}/badge/t3/status`, {
      method: "OPTIONS",
      headers: { Origin: "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET" },
    });
    assert.equal(ok.status, 204);
    assert.equal(ok.headers.get("access-control-allow-origin"), "http://127.0.0.1:5173");
    assert.match(ok.headers.get("access-control-allow-headers"), /Authorization/);
    const real = await fetch(`${base}/badge/t3/status`, { headers: { ...auth, Origin: "http://localhost:9000" } });
    assert.equal(real.headers.get("access-control-allow-origin"), "http://localhost:9000");
    const foreign = await fetch(`${base}/badge/t3/status`, {
      method: "OPTIONS",
      headers: { Origin: "https://evil.example", "Access-Control-Request-Method": "GET" },
    });
    assert.equal(foreign.headers.get("access-control-allow-origin"), null);
    assert.equal(foreign.status, 401);
  });

  test("unknown routes are 404 JSON", async () => {
    nextMinute();
    const res = await fetch(`${base}/badge/nope`, { headers: auth });
    assert.equal(res.status, 404);
    assert.ok((await res.json()).error.message);
  });
});
