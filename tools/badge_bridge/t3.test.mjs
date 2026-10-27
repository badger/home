import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  T3Source,
  applyShellItem,
  ascii,
  childRequests,
  classify,
  summarize,
  summarizeShell,
} from "./t3.mjs";

const NOW = Date.parse("2026-10-27T03:00:00Z");
const iso = (secondsAgo) => new Date(NOW - secondsAgo * 1000).toISOString();

function thread(overrides = {}) {
  return {
    id: "thread-0000000001",
    projectId: "p1",
    title: "Fix the login flow",
    status: "completed",
    activityRunStatus: null,
    lineage: { parentThreadId: null, relationshipToParent: null, rootThreadId: "thread-0000000001" },
    modelSelection: { instanceId: "codex", model: "gpt-5.6-sol" },
    pendingRuntimeRequest: null,
    pendingBackgroundTasks: [],
    updatedAt: iso(30),
    latestRunCompletedAt: iso(30),
    lastVisitedAt: iso(60),
    latestVisibleMessage: { role: "assistant", text: "All tests pass.", updatedAt: iso(30) },
    ...overrides,
  };
}

describe("classify", () => {
  test("approvals and input need attention", () => {
    assert.deepEqual(classify(thread({ pendingRuntimeRequest: { kind: "command" } })), {
      state: "attention",
      detail: "approve command",
    });
    assert.equal(
      classify(thread({ status: "waiting", pendingRuntimeRequest: { kind: "user_input" } })).detail,
      "needs your input",
    );
  });

  test("non-blocking input while busy keeps working", () => {
    const busy = thread({
      status: "running",
      activityRunStatus: "running",
      pendingRuntimeRequest: { kind: "user_input", blocking: false },
    });
    assert.equal(classify(busy).state, "working");
  });

  test("auth refresh is not an approval", () => {
    assert.equal(classify(thread({ pendingRuntimeRequest: { kind: "auth_refresh" }, status: "idle" })).state, "idle");
  });

  test("running statuses are working", () => {
    for (const status of ["preparing", "queued", "starting", "running", "waiting"]) {
      assert.equal(classify(thread({ status, activityRunStatus: status })).state, "working");
    }
  });

  test("background work holds completion", () => {
    const held = thread({ pendingBackgroundTasks: [{ kind: "subagent" }] });
    assert.deepEqual(classify(held), { state: "working", detail: "background work" });
  });

  test("recent failures and usage limits are errors; old ones are idle", () => {
    assert.deepEqual(classify(thread({ status: "failed", lastErrorClass: "provider_error" }), undefined, NOW), {
      state: "error",
      detail: "provider error",
    });
    assert.equal(
      classify(thread({ status: "completed", lastErrorClass: "usage_limit" }), undefined, NOW).detail,
      "usage limit",
    );
    const old = thread({ status: "failed", latestRunCompletedAt: iso(3 * 86400), updatedAt: iso(3 * 86400) });
    assert.equal(classify(old, undefined, NOW).state, "idle");
  });

  test("recent unseen completions are done; seen or old ones are idle", () => {
    assert.equal(classify(thread(), undefined, NOW).state, "done");
    assert.equal(classify(thread({ lastVisitedAt: iso(5) }), undefined, NOW).state, "idle");
    assert.equal(classify(thread({ lastVisitedAt: null }), undefined, NOW).state, "done");
    const old = thread({ latestRunCompletedAt: iso(25 * 3600), lastVisitedAt: iso(30 * 3600) });
    assert.equal(classify(old, undefined, NOW).state, "idle");
  });
});

describe("childRequests", () => {
  test("a live subagent's approval bubbles up to its ancestors", () => {
    const root = thread({ id: "root", status: "running", activityRunStatus: "running" });
    const mid = thread({
      id: "mid",
      activityRunStatus: "running",
      lineage: { parentThreadId: "root", relationshipToParent: "subagent" },
    });
    const leaf = thread({
      id: "leaf",
      activityRunStatus: "waiting",
      lineage: { parentThreadId: "mid", relationshipToParent: "subagent" },
      pendingRuntimeRequest: { kind: "file-change" },
    });
    const result = childRequests([root, mid, leaf]);
    assert.equal(result.get("root"), "approval");
    assert.equal(result.get("mid"), "approval");
    assert.deepEqual(classify(root, result.get("root")), { state: "attention", detail: "subagent approval" });
  });
});

describe("summaries", () => {
  test("hides subagents, archived and deleted threads and sanitizes text", () => {
    const shell = {
      projects: [{ id: "p1", title: "home \u2014 badge" }],
      threads: [
        thread({ id: "a", title: "Caf\u00e9 \u201cfix\u201d \ud83d\ude80 now" }),
        thread({ id: "b", lineage: { parentThreadId: "a", relationshipToParent: "subagent" } }),
        thread({ id: "c", archivedAt: iso(1) }),
        thread({ id: "d", deletedAt: iso(1) }),
      ],
    };
    const rows = summarizeShell(shell, "mbp", NOW);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].title, 'Cafe "fix" now');
    assert.equal(rows[0].project, "home - badge");
    assert.equal(rows[0].src, "mbp");
    assert.equal(rows[0].age, 30);
  });

  test("ascii truncates with a marker", () => {
    assert.equal(ascii("abcdefghij", 6), "abcde~");
    assert.equal(ascii(null, 5), "");
  });

  test("sorts by urgency then recency, counts, and reports stale sources", () => {
    const fresh = {
      name: "mbp",
      staleMs: 30000,
      lastOk: NOW - 2000,
      shell: {
        projects: [],
        threads: [
          thread({ id: "idle", lastVisitedAt: iso(1), updatedAt: iso(5) }),
          thread({ id: "work", status: "running", activityRunStatus: "running", updatedAt: iso(50) }),
          thread({ id: "ask", pendingRuntimeRequest: { kind: "permission" }, updatedAt: iso(500) }),
          thread({ id: "fail", status: "failed", updatedAt: iso(9) }),
          thread({ id: "work2", status: "queued", activityRunStatus: "queued", updatedAt: iso(10) }),
        ],
      },
    };
    const stale = { name: "desk", staleMs: 30000, lastOk: NOW - 120000, shell: fresh.shell, error: "T3 offline" };
    const status = summarize([fresh, stale], NOW);
    assert.equal(status.ok, true);
    assert.deepEqual(status.counts, { attention: 1, working: 2, error: 1, done: 0, idle: 1 });
    assert.deepEqual(
      status.threads.map((row) => row.state),
      ["attention", "working", "working", "error", "idle"],
    );
    assert.equal(status.threads[1].detail, "queued");
    assert.deepEqual(status.sources[1], { name: "desk", ok: false, age: 120, error: "T3 offline" });
    assert.ok(JSON.stringify(status).length < 2500);
  });

  test("filters counts and threads to one source but reports them all", () => {
    const make = (name, threads) => ({ name, staleMs: 30000, lastOk: NOW - 1000, shell: { projects: [], threads } });
    const sources = [
      make("mbp", [thread({ id: "m1", status: "running", activityRunStatus: "running" })]),
      make("fate", [thread({ id: "f1", pendingRuntimeRequest: { kind: "command" } }), thread({ id: "f2" })]),
    ];
    const status = summarize(sources, NOW, "fate");
    assert.equal(status.src, "fate");
    assert.deepEqual(status.sources.map((source) => source.name), ["mbp", "fate"]);
    assert.deepEqual(status.counts, { attention: 1, working: 0, error: 0, done: 1, idle: 0 });
    assert.deepEqual(new Set(status.threads.map((row) => row.src)), new Set(["fate"]));
    assert.equal(summarize(sources, NOW).counts.working, 1);
  });

  test("never fails without data", () => {
    const status = summarize([{ name: "mbp", staleMs: 30000, lastOk: 0, shell: null, error: null }], NOW);
    assert.equal(status.ok, false);
    assert.equal(status.sources[0].error, "connecting");
    assert.deepEqual(status.threads, []);
  });
});

describe("applyShellItem", () => {
  const snapshot = (threads, sequence = 10) => ({
    kind: "snapshot",
    snapshot: { snapshotSequence: sequence, threads, projects: [{ id: "p1", title: "home" }] },
  });

  test("snapshots replace state; deltas apply in sequence order", () => {
    const holder = {};
    assert.equal(applyShellItem(holder, snapshot([thread({ id: "a" }), thread({ id: "b" })])), true);
    applyShellItem(holder, { kind: "thread.updated", sequence: 11, location: "active", thread: thread({ id: "a", title: "new" }) });
    applyShellItem(holder, { kind: "thread.updated", sequence: 9, location: "active", thread: thread({ id: "a", title: "stale" }) });
    applyShellItem(holder, { kind: "thread.removed", sequence: 12, threadId: "b" });
    applyShellItem(holder, { kind: "thread.updated", sequence: 13, location: "archive", thread: thread({ id: "c" }) });
    applyShellItem(holder, { kind: "project.updated", sequence: 14, project: { id: "p2", title: "web" } });
    applyShellItem(holder, { kind: "project.removed", sequence: 15, projectId: "p1" });
    assert.deepEqual(holder.shell.threads.map((t) => [t.id, t.title]), [["a", "new"]]);
    assert.deepEqual(holder.shell.projects, [{ id: "p2", title: "web" }]);
    assert.equal(holder.shell.snapshotSequence, 15);
  });

  test("projects-only refresh snapshots patch projects without dropping threads", () => {
    const holder = {};
    applyShellItem(holder, snapshot([thread({ id: "a" })]));
    const patch = {
      kind: "snapshot",
      resolvedRepositoryIdentityRoots: ["/x"],
      snapshot: { snapshotSequence: 99, threads: [], projects: [{ id: "p1", title: "renamed" }] },
    };
    assert.equal(applyShellItem(holder, patch), false);
    assert.equal(holder.shell.threads.length, 1);
    assert.equal(holder.shell.projects[0].title, "renamed");
    assert.equal(holder.shell.snapshotSequence, 10);
  });

  test("ignores deltas before the first snapshot and junk items", () => {
    const holder = {};
    applyShellItem(holder, { kind: "thread.updated", sequence: 1, location: "active", thread: thread() });
    applyShellItem(holder, null);
    applyShellItem(holder, { kind: "synchronized" });
    assert.equal(holder.shell, undefined);
  });
});

class FakeSocket {
  static last = null;
  constructor(url) {
    this.url = url;
    this.sent = [];
    this.readyState = 0;
    FakeSocket.last = this;
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.();
    });
  }
  send(text) {
    this.sent.push(JSON.parse(text));
  }
  receive(message) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

describe("T3Source.follow", () => {
  test("mints a ticket, subscribes, acks every chunk and tracks freshness", async () => {
    let clock = NOW;
    const fetchCalls = [];
    const source = new T3Source(
      { name: "mbp", url: "https://t3.example", token: "secret" },
      {
        now: () => clock,
        WebSocket: FakeSocket,
        fetch: async (url, init) => {
          fetchCalls.push({ url, method: init.method, auth: init.headers.Authorization });
          return new Response(JSON.stringify({ ticket: "tick et", expiresAt: "x" }), { status: 200 });
        },
      },
    );
    const done = source.follow();
    await new Promise((resolve) => setTimeout(resolve, 5));
    const socket = FakeSocket.last;
    assert.deepEqual(fetchCalls, [
      { url: "https://t3.example/api/auth/websocket-ticket/rpc", method: "POST", auth: "Bearer secret" },
    ]);
    const url = new URL(socket.url);
    assert.equal(url.protocol, "wss:");
    assert.equal(url.pathname, "/ws");
    assert.equal(url.searchParams.get("orchestrationProtocol"), "2");
    assert.equal(url.searchParams.get("wsTicket"), "tick et");
    assert.deepEqual(socket.sent[0], {
      _tag: "Request",
      id: 1,
      tag: "orchestration.subscribeShell",
      payload: { omitIdleSubagents: true, omitOlderSettled: true },
      headers: [],
    });

    clock += 1000;
    socket.receive({
      _tag: "Chunk",
      requestId: 1,
      values: [{ kind: "snapshot", snapshot: { snapshotSequence: 5, threads: [thread({ id: "a" })], projects: [] } }],
    });
    assert.deepEqual(socket.sent.at(-1), { _tag: "Ack", requestId: 1 });
    assert.equal(source.lastOk, NOW + 1000);
    assert.equal(source.shell.threads.length, 1);

    clock += 1000;
    socket.receive([
      { _tag: "Chunk", requestId: 1, values: [{ kind: "thread.removed", sequence: 6, threadId: "a" }] },
      { _tag: "Pong" },
    ]);
    assert.equal(source.shell.threads.length, 0);
    assert.equal(socket.sent.filter((message) => message._tag === "Ack").length, 2);
    assert.equal(source.lastOk, NOW + 2000);

    socket.receive({
      _tag: "Exit",
      requestId: 1,
      exit: { _tag: "Failure", cause: [{ _tag: "Fail", error: { message: "Missing scope" } }] },
    });
    assert.equal(await done, null);
    assert.equal(source.error, "Missing scope");
    assert.equal(source.socket, null);
  });

  test("falls back to the legacy ticket path on 404 and rejects on bad tokens", async () => {
    const urls = [];
    const replies = [
      () => new Response("{}", { status: 404 }),
      () => new Response(JSON.stringify({ ticket: "t2" }), { status: 200 }),
    ];
    const source = new T3Source(
      { name: "mbp", url: "http://t3.example:3773", token: "secret" },
      {
        WebSocket: FakeSocket,
        fetch: async (url) => {
          urls.push(url);
          return replies.shift()();
        },
      },
    );
    const done = source.follow();
    await new Promise((resolve) => setTimeout(resolve, 5));
    assert.deepEqual(urls, [
      "http://t3.example:3773/api/auth/websocket-ticket/rpc",
      "http://t3.example:3773/api/auth/websocket-ticket",
    ]);
    assert.equal(new URL(FakeSocket.last.url).protocol, "ws:");
    FakeSocket.last.close();
    await done;

    const rejected = new T3Source(
      { name: "mbp", url: "https://t3.example", token: "bad" },
      { WebSocket: FakeSocket, fetch: async () => new Response("no", { status: 401 }) },
    );
    await assert.rejects(rejected.follow(), /T3 token rejected/);
  });
});

describe("T3Source.poll", () => {
  test("sends the protocol header and bearer token", async () => {
    let seen;
    const source = new T3Source(
      { name: "mbp", url: "https://t3.example/", token: "secret" },
      {
        now: () => NOW,
        fetch: async (url, init) => {
          seen = { url, init };
          return new Response(JSON.stringify({ threads: [], projects: [] }), { status: 200 });
        },
      },
    );
    assert.equal(await source.poll(), true);
    assert.equal(seen.url, "https://t3.example/api/orchestration/shell?omitIdleSubagents=1&omitOlderSettled=1");
    assert.equal(seen.init.headers.Authorization, "Bearer secret");
    assert.equal(seen.init.headers["x-t3-orchestration-protocol"], "2");
    assert.equal(source.lastOk, NOW);
  });

  test("records readable errors and keeps the last good shell", async () => {
    const replies = [
      () => new Response(JSON.stringify({ threads: [], projects: [] }), { status: 200 }),
      () => new Response("nope", { status: 401 }),
      () => {
        throw new TypeError("fetch failed");
      },
    ];
    const source = new T3Source({ name: "mbp", url: "https://t3.example", token: "t" }, { fetch: async () => replies.shift()() });
    await source.poll();
    assert.equal(await source.poll(), false);
    assert.equal(source.error, "T3 token rejected");
    assert.ok(source.shell);
    await source.poll();
    assert.equal(source.error, "T3 offline");
  });
});
