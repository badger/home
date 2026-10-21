import assert from "node:assert/strict";
import dgram from "node:dgram";
import { once } from "node:events";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import {
  Bridge, completeText, encode, loadParser, MAX_PACKET, MAX_SOURCE, snapshot,
  validateConfig, validateURL,
} from "./bridge.mjs";

const source = process.env.AGENTVIZ_SOURCE;
assert.ok(source, "Set AGENTVIZ_SOURCE to the pinned upstream checkout");
const parser = await loadParser(source);
const directory = await mkdtemp(path.join(os.tmpdir(), "badge-agentviz-"));
after(() => rm(directory, { recursive: true }));
const config = { badge: "127.0.0.1", token: "b".repeat(32) };

test("uses upstream parsers across real supported session fixtures", async () => {
  for (const [fixture, format] of [
    ["test-claude-code.jsonl", "claude-code"], ["test-copilot.jsonl", "copilot-cli"],
    ["test-codex.jsonl", "codex"], ["test-vscode-chat.json", "vscode-chat"],
    ["atif-minimal.json", "atif"], ["test-copilot-prompts.json", "copilot-prompts"],
  ]) {
    const text = await readFile(path.join(source, "src/__tests__/fixtures", fixture), "utf8");
    assert.equal(parser.detectFormat(text), format, fixture);
    const result = snapshot(parser.parseSession(text), format);
    assert.ok(result.metrics[0] > 0, fixture);
    assert.ok(result.events.length <= 24);
    assert.ok(encode(result, config, "a".repeat(32), 0).length <= MAX_PACKET);
    assert.ok(result.events.every(e => e[3] >= 0 && e[3] <= 4));
  }
});

test("real multi-agent tool pairing, errors and identity reach the compact view", async () => {
  const text = await readFile(path.join(source, "src/__tests__/fixtures/test-multiagent.jsonl"), "utf8");
  const parsed = parser.parseSession(text);
  const payload = snapshot(parsed, parser.detectFormat(text));
  assert.ok(payload.events.some(e => e[5] === "general-purp"));
  assert.ok(payload.events.some(e => e[6] === 1));
  assert.ok(payload.events.some(e => e[3] === 4 && e[4] === "Agent failed"));
  assert.ok(payload.metrics[2] > 0);
  assert.ok(parsed.events.some(e => e.toolOutput));
});

test("privacy boundary excludes raw prompts, arguments, output, paths and model text", () => {
  const secret = "PRIVATE_SOURCE_PROMPT_TOKEN";
  const payload = snapshot({
    events: [{ t: 0, duration: 1, track: "tool_call", toolName: "bash",
      text: secret, raw: { secret }, toolInput: secret, toolOutput: secret,
      agent: "assistant", turnIndex: 0, isError: false }],
    metadata: { customTitle: secret, primaryModel: secret, totalToolCalls: 1 },
  }, "copilot-cli");
  const wire = encode(payload, config, "a".repeat(32), 0).toString();
  assert.ok(!wire.includes(secret));
  assert.equal(payload.events[0][4], "bash");
  assert.deepEqual(payload.metrics.slice(5), [-1, -1]);
});

test("caps memory-facing labels, event window and datagram size", () => {
  const payload = snapshot({
    events: Array.from({ length: 10000 }, (_, i) => ({
      t: i, duration: 0, track: "tool_call", toolName: "x".repeat(999),
      agentName: "y".repeat(999), turnIndex: 0,
    })), metadata: {},
  }, "copilot-cli");
  assert.equal(payload.events.length, 24);
  assert.equal(payload.events[0][0], 9976);
  assert.equal(payload.events[23][4].length, 18);
  assert.equal(payload.events[23][5].length, 12);
  assert.ok(encode(payload, config, "a".repeat(32), 0).length <= MAX_PACKET);
});

test("record boundaries include complete JSON but never incomplete JSONL", () => {
  assert.equal(completeText(Buffer.from('{"x":1}\n{"x":')), '{"x":1}\n');
  assert.equal(completeText(Buffer.from('{"x":1}')), '{"x":1}');
  assert.equal(completeText(Buffer.from('{"type":"user.message","data":{}}')), "");
  assert.equal(completeText(Buffer.from('{"requests":[')), "");
  assert.throws(() => completeText(Buffer.alloc(MAX_SOURCE + 1)), /too large/);
  assert.throws(() => snapshot({ events: [], metadata: {
    parseIssues: { malformedLines: 1, invalidEvents: 0 },
  } }, "session"), /Invalid session/);
});

test("only loopback AgentViz origins and explicit IPv4 badge destinations", () => {
  validateURL("http://127.0.0.1:5173");
  for (const value of ["https://127.0.0.1", "http://example.com", "http://127.0.0.1/path",
    "http://user:pass@localhost:5173", "http://localhost/?token=secret"]) {
    assert.throws(() => validateURL(value));
  }
  for (const bad of [{ ...config, badge: "example.com" }, { ...config, token: "x" },
    { ...config, port: 0 }, { ...config, badge: "255.255.255.255" }]) {
    assert.throws(() => validateConfig(bad));
  }
});

test("real UDP heartbeat, append, truncation, source failure and recovery", async () => {
  const receiver = dgram.createSocket("udp4");
  const sender = dgram.createSocket("udp4");
  receiver.bind(0, "127.0.0.1");
  await once(receiver, "listening");
  const file = path.join(directory, "trace.jsonl");
  const lines = [
    { type: "session.start", data: { producer: "copilot-agent", sessionId: "synthetic" },
      timestamp: "2026-01-01T00:00:00Z" },
    { type: "user.message", data: { content: "PRIVATE PROMPT" },
      timestamp: "2026-01-01T00:00:01Z" },
    { type: "tool.execution_start", data: { toolCallId: "t1", toolName: "bash",
      arguments: { command: "PRIVATE COMMAND" } }, timestamp: "2026-01-01T00:00:02Z" },
  ].map(value => JSON.stringify(value) + "\n");
  const bridge = new Bridge(parser, { session: file },
    { ...config, port: receiver.address().port }, sender);
  async function receive() {
    const message = once(receiver, "message");
    await bridge.tick();
    return JSON.parse((await message)[0]);
  }
  try {
    await writeFile(file, lines.slice(0, 2).join(""));
    const first = await receive();
    assert.equal(first.state, "ok");
    const heartbeat = await receive();
    assert.deepEqual(first.events, heartbeat.events);
    assert.equal(heartbeat.seq, first.seq + 1);
    await writeFile(file, lines.join("") + '{"type":');
    const appended = await receive();
    assert.ok(appended.events.length > first.events.length);
    assert.equal(appended.epoch, first.epoch);
    assert.ok(!JSON.stringify(appended).includes("PRIVATE"));
    await writeFile(file, lines[0]);
    const reset = await receive();
    assert.notEqual(reset.epoch, first.epoch);
    assert.equal(reset.state, "waiting");
    await rm(file);
    assert.equal((await receive()).state, "error");
    await writeFile(file, lines.join(""));
    assert.equal((await receive()).state, "ok");
  } finally {
    sender.close();
    receiver.close();
  }
});

test("late inserted normalized events reset the epoch instead of moving evidence", async () => {
  const file = path.join(directory, "reordered.jsonl");
  const packets = [];
  const socket = { send(data, port, host, callback) {
    packets.push(JSON.parse(data));
    callback(null);
  } };
  const bridge = new Bridge(parser, { session: file }, config, socket);
  const line = (type, content, timestamp) => JSON.stringify({
    type, data: { content, producer: "copilot-agent" }, timestamp,
  }) + "\n";
  let text = line("session.start", "", "2026-01-01T00:00:00Z") +
    line("user.message", "test", "2026-01-01T00:00:02Z");
  await writeFile(file, text);
  await bridge.tick();
  text += line("user.message", "earlier event", "2026-01-01T00:00:01Z");
  await writeFile(file, text);
  await bridge.tick();
  assert.notEqual(packets[0].epoch, packets[1].epoch);
});

test("polls the existing AgentViz /api/file endpoint and reports HTTP failures", async () => {
  const fixture = await readFile(path.join(source,
    "src/__tests__/fixtures/test-copilot.jsonl"));
  let status = 200;
  const server = http.createServer((request, response) => {
    assert.equal(request.url, "/api/file");
    response.writeHead(status);
    response.end(status === 200 ? fixture : "Not found");
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const packets = [];
  const socket = { send(packet, port, host, callback) {
    packets.push(JSON.parse(packet));
    callback(null);
  } };
  try {
    const bridge = new Bridge(parser, { url: `http://127.0.0.1:${server.address().port}` },
      config, socket);
    await bridge.tick();
    assert.equal(packets.at(-1).state, "ok");
    status = 500;
    await bridge.tick();
    assert.equal(packets.at(-1).state, "error");
    assert.equal(packets.at(-1).message, "Source unavailable");
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
