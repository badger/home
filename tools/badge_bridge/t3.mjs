// T3 Code status for the badge bridge.
//
// Follows each configured T3 Code server's orchestration shell with a
// read-only `orchestration:read` session token: one snapshot plus live deltas
// over the protocol-2 Effect RPC WebSocket (`orchestration.subscribeShell`),
// falling back to slow polling of GET /api/orchestration/shell. Every
// top-level thread is classified and served as a small ASCII-only summary
// that a badge can parse cheaply.

const PROTOCOL = "2";
const SHELL_PATH = "/api/orchestration/shell?omitIdleSubagents=1&omitOlderSettled=1";
const SHELL_REQUEST = 1;
const PING_MS = 5000;
const SILENCE_MS = 20000;
const RUNNING = new Set(["preparing", "queued", "starting", "running", "waiting"]);
const BUSY = new Set(["preparing", "starting", "running"]);
const RANK = { attention: 0, working: 1, error: 2, done: 3, idle: 4 };
const MAX_THREADS = 12;
// Completions and failures older than this are history, shown as idle.
const RECENT_MS = 24 * 60 * 60 * 1000;

const APPROVAL_LABELS = {
  command: "approve command",
  "file-read": "approve file read",
  "file-change": "approve file edit",
  "mcp-elicitation": "MCP needs input",
  permission: "approve permission",
  dynamic_tool_call: "approve tool call",
};
const ERROR_LABELS = {
  usage_limit: "usage limit",
  provider_error: "provider error",
  transport_error: "connection error",
  permission_error: "permission error",
  validation_error: "validation error",
};

export function ascii(text, max) {
  const clean = String(text ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201c\u201d]/g, '"')
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/\u2026/g, "...")
    .replace(/\s/g, " ")
    .replace(/[^\x20-\x7e]/g, "")
    .replace(/ {2,}/g, " ")
    .trim();
  return clean.length > max ? `${clean.slice(0, max - 1).trimEnd()}~` : clean;
}

const holdsCompletion = (tasks = []) =>
  tasks.some((task) => task.awaited === true || task.kind === "subagent" || task.kind === "background_task");

function isLive(thread) {
  return thread.activityRunStatus !== undefined
    ? thread.activityRunStatus !== null
    : ["preparing", "starting", "running", "waiting"].includes(thread.status);
}

// A live subagent's pending request surfaces on every ancestor thread.
export function childRequests(threads) {
  const byId = new Map(threads.map((thread) => [thread.id, thread]));
  const result = new Map();
  for (const child of threads) {
    const request = child.pendingRuntimeRequest;
    if (child.lineage?.relationshipToParent !== "subagent" || !request) continue;
    if (request.kind === "auth_refresh" || !isLive(child)) continue;
    const kind = request.kind === "user_input" ? "input" : "approval";
    const seen = new Set([child.id]);
    let node = child;
    while (node?.lineage?.relationshipToParent === "subagent" && node.lineage.parentThreadId) {
      const parentId = node.lineage.parentThreadId;
      if (seen.has(parentId)) break;
      seen.add(parentId);
      if (result.get(parentId) !== "approval") result.set(parentId, kind);
      node = byId.get(parentId);
    }
  }
  return result;
}

export function classify(thread, child, now = Date.now()) {
  const request = thread.pendingRuntimeRequest;
  const run = thread.activityRunStatus ?? thread.status;
  if ((request && request.kind !== "user_input" && request.kind !== "auth_refresh") || child === "approval") {
    const label = request ? APPROVAL_LABELS[request.kind] : null;
    return { state: "attention", detail: label || "subagent approval" };
  }
  if ((request?.kind === "user_input" && (request.blocking !== false || !BUSY.has(run))) || child === "input") {
    return { state: "attention", detail: "needs your input" };
  }
  if (thread.blockedOnThreadWait) return { state: "working", detail: "waiting on thread" };
  if (RUNNING.has(run)) return { state: "working", detail: run };
  if (holdsCompletion(thread.pendingBackgroundTasks) && thread.status !== "failed") {
    return { state: "working", detail: "background work" };
  }
  const ended = Date.parse(thread.latestRunCompletedAt || thread.updatedAt || "");
  const recent = Number.isFinite(ended) && now - ended < RECENT_MS;
  if ((thread.status === "failed" || thread.lastErrorClass === "usage_limit") && recent) {
    return { state: "error", detail: ERROR_LABELS[thread.lastErrorClass] || "failed" };
  }
  if (thread.status === "completed" && recent) {
    const visited = Date.parse(thread.lastVisitedAt || "");
    if (!visited || ended > visited) return { state: "done", detail: "finished" };
  }
  if (thread.status === "interrupted" || thread.status === "cancelled") {
    return { state: "idle", detail: "stopped" };
  }
  return { state: "idle", detail: "" };
}

function secondsSince(iso, now) {
  const time = Date.parse(iso || "");
  return Number.isFinite(time) ? Math.max(0, Math.round((now - time) / 1000)) : null;
}

export function summarizeShell(shell, sourceName, now) {
  const threads = Array.isArray(shell?.threads) ? shell.threads : [];
  const projects = new Map((shell?.projects || []).map((project) => [project.id, project.title]));
  const children = childRequests(threads);
  return threads
    .filter((thread) => !thread.deletedAt && !thread.archivedAt)
    .filter((thread) => thread.lineage?.relationshipToParent !== "subagent")
    .map((thread) => {
      const { state, detail } = classify(thread, children.get(thread.id), now);
      return {
        id: String(thread.id).slice(-8),
        title: ascii(thread.title || "Untitled thread", 40),
        project: ascii(projects.get(thread.projectId) || "", 20),
        src: sourceName,
        state,
        detail,
        model: ascii(thread.modelSelection?.model || "", 24),
        age: secondsSince(thread.updatedAt, now),
        msg: ascii(thread.latestVisibleMessage?.text || "", 90),
      };
    });
}

// `only` limits counts and threads to one source; every source is still
// reported so the badge can offer the others.
export function summarize(sources, now = Date.now(), only = null) {
  const counts = { attention: 0, working: 0, error: 0, done: 0, idle: 0 };
  const threads = [];
  const report = [];
  for (const source of sources) {
    const fresh = source.shell && source.lastOk && now - source.lastOk < source.staleMs;
    report.push({
      name: source.name,
      ok: Boolean(fresh),
      age: source.lastOk ? Math.round((now - source.lastOk) / 1000) : null,
      error: fresh ? null : source.error || "connecting",
    });
    if (!fresh || (only && source.name !== only)) continue;
    for (const thread of summarizeShell(source.shell, source.name, now)) {
      counts[thread.state] += 1;
      threads.push(thread);
    }
  }
  threads.sort((a, b) => RANK[a.state] - RANK[b.state] || (a.age ?? 1e12) - (b.age ?? 1e12));
  return {
    v: 1,
    at: Math.round(now / 1000),
    ok: report.some((source) => source.ok),
    src: only,
    sources: report,
    counts,
    threads: threads.slice(0, MAX_THREADS),
  };
}

// Applies one subscribeShell stream item to `holder.shell`. Returns true when
// the item carried the authoritative snapshot.
export function applyShellItem(holder, item) {
  if (!item || typeof item !== "object") return false;
  if (item.kind === "snapshot") {
    const snapshot = item.snapshot;
    if (!snapshot) return false;
    // Projects-only refreshes carry resolved repository roots; treat them as a
    // project metadata patch rather than replacing every thread.
    if (item.resolvedRepositoryIdentityRoots || snapshot.resolvedRepositoryIdentityRoots) {
      if (holder.shell && Array.isArray(snapshot.projects)) {
        const merged = new Map(holder.shell.projects.map((project) => [project.id, project]));
        for (const project of snapshot.projects) merged.set(project.id, project);
        holder.shell.projects = [...merged.values()];
      }
      return false;
    }
    holder.shell = {
      snapshotSequence: snapshot.snapshotSequence ?? 0,
      threads: Array.isArray(snapshot.threads) ? snapshot.threads : [],
      projects: Array.isArray(snapshot.projects) ? snapshot.projects : [],
    };
    return true;
  }
  const shell = holder.shell;
  if (!shell || typeof item.sequence !== "number" || item.sequence <= shell.snapshotSequence) return false;
  if (item.kind === "thread.updated" || item.kind === "thread.removed") {
    const id = item.thread?.id ?? item.threadId;
    shell.threads = shell.threads.filter((thread) => thread.id !== id);
    if (item.kind === "thread.updated" && item.location === "active" && item.thread) {
      shell.threads.push(item.thread);
    }
  } else if (item.kind === "project.updated" && item.project) {
    shell.projects = [...shell.projects.filter((project) => project.id !== item.project.id), item.project];
  } else if (item.kind === "project.removed") {
    shell.projects = shell.projects.filter((project) => project.id !== item.projectId);
  }
  shell.snapshotSequence = item.sequence;
  return false;
}

function describeError(error) {
  if (error && (error.name === "TimeoutError" || error.name === "AbortError")) return "T3 timed out";
  const text = `${error?.message || ""} ${error?.cause?.code || ""}`;
  if (/fetch failed|ECONNREFUSED|ENOTFOUND|EHOSTUNREACH|ECONNRESET/i.test(text)) return "T3 offline";
  return ascii(error?.message || "T3 unreachable", 40);
}

export class T3Source {
  constructor({ name, url, token }, options = {}) {
    this.name = name;
    this.url = url.replace(/\/+$/, "");
    this.token = token;
    this.fetch = options.fetch || globalThis.fetch;
    this.WebSocket = options.WebSocket || globalThis.WebSocket;
    this.now = options.now || Date.now;
    this.timeoutMs = options.timeoutMs || 8000;
    this.staleMs = options.staleMs || 30000;
    this.shell = null;
    this.lastOk = 0;
    this.error = null;
    this.socket = null;
  }

  headers(extra = {}) {
    return {
      Authorization: `Bearer ${this.token}`,
      "x-t3-orchestration-protocol": PROTOCOL,
      Accept: "application/json",
      ...extra,
    };
  }

  async request(path, init = {}) {
    const response = await this.fetch(this.url + path, {
      ...init,
      headers: this.headers(init.headers),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (response.status === 401 || response.status === 403) throw new Error("T3 token rejected");
    if (!response.ok) {
      throw Object.assign(new Error(`T3 HTTP ${response.status}`), { status: response.status });
    }
    return response.json();
  }

  async poll() {
    try {
      const shell = await this.request(SHELL_PATH);
      if (!shell || !Array.isArray(shell.threads)) throw new Error("unexpected T3 shell");
      this.shell = {
        snapshotSequence: shell.snapshotSequence ?? 0,
        threads: shell.threads,
        projects: Array.isArray(shell.projects) ? shell.projects : [],
      };
      this.lastOk = this.now();
      this.error = null;
      return true;
    } catch (error) {
      this.error = describeError(error);
      return false;
    }
  }

  async ticket() {
    try {
      return (await this.request("/api/auth/websocket-ticket/rpc", { method: "POST" })).ticket;
    } catch (error) {
      if (error.status !== 404) throw error;
      return (await this.request("/api/auth/websocket-ticket", { method: "POST" })).ticket;
    }
  }

  // Resolves when the socket closes; rejects if it cannot be opened.
  async follow() {
    const ticket = await this.ticket();
    const url = new URL(`${this.url}/ws`);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.searchParams.set("orchestrationProtocol", PROTOCOL);
    url.searchParams.set("wsTicket", ticket);
    url.searchParams.set("clientSurface", "badge-bridge");
    const socket = new this.WebSocket(url.href);
    this.socket = socket;
    return new Promise((resolve, reject) => {
      let opened = false;
      let heard = this.now();
      let ping = null;
      const send = (message) => {
        if (socket.readyState === 1) socket.send(JSON.stringify(message));
      };
      const finish = (error) => {
        clearInterval(ping);
        if (this.socket === socket) this.socket = null;
        if (opened) resolve(error);
        else reject(error || new Error("T3 socket closed"));
      };
      socket.onopen = () => {
        opened = true;
        send({
          _tag: "Request",
          id: SHELL_REQUEST,
          tag: "orchestration.subscribeShell",
          payload: { omitIdleSubagents: true, omitOlderSettled: true },
          headers: [],
        });
        ping = setInterval(() => {
          if (this.now() - heard > SILENCE_MS) {
            this.error = "T3 stopped responding";
            socket.close();
            return;
          }
          send({ _tag: "Ping" });
        }, PING_MS);
      };
      socket.onmessage = (event) => {
        heard = this.now();
        let messages;
        try {
          messages = [].concat(JSON.parse(String(event.data)));
        } catch {
          return;
        }
        for (const message of messages) {
          if (message._tag === "Chunk") {
            if (message.requestId === SHELL_REQUEST) {
              for (const item of message.values || []) applyShellItem(this, item);
            }
            // The server waits for an Ack before sending the next chunk.
            send({ _tag: "Ack", requestId: message.requestId });
          } else if (message._tag === "Exit" && message.requestId === SHELL_REQUEST) {
            const cause = message.exit?.cause?.[0];
            this.error = ascii(cause?.error?.message || cause?._tag || "T3 stream ended", 40);
            socket.close();
            continue;
          } else if (message._tag === "Defect") {
            this.error = "T3 server defect";
            socket.close();
            continue;
          }
          if (this.shell) {
            this.lastOk = this.now();
            this.error = null;
          }
        }
      };
      socket.onerror = () => {
        if (!this.error) this.error = "T3 socket error";
      };
      socket.onclose = () => finish(null);
    });
  }
}

export function parseSources(source = process.env) {
  const entries = (source.BADGE_BRIDGE_T3_SOURCES || "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  return entries.map((entry) => {
    const at = entry.indexOf("@");
    if (at <= 0) throw new Error(`BADGE_BRIDGE_T3_SOURCES entry must be name@url: ${entry}`);
    const name = entry.slice(0, at).trim();
    const url = entry.slice(at + 1).trim();
    if (!/^[a-z0-9-]{1,16}$/i.test(name)) throw new Error(`Invalid T3 source name: ${name}`);
    if (!/^https?:\/\//.test(url)) throw new Error(`T3 source ${name} needs an http(s) URL`);
    const key = `BADGE_BRIDGE_T3_TOKEN_${name.toUpperCase().replace(/-/g, "_")}`;
    const token = (source[key] || "").trim();
    if (!token) throw new Error(`${key} is required for T3 source ${name}`);
    return { name: name.toLowerCase(), url, token };
  });
}

export class T3Status {
  constructor(sources, options = {}) {
    this.sources = sources.map((source) => new T3Source(source, options));
    this.now = options.now || Date.now;
    this.retryMs = options.retryMs || 3000;
    this.maxRetryMs = options.maxRetryMs || 30000;
    this.log = options.log || ((line) => console.log(line));
    this.timers = new Map();
    this.stopped = true;
  }

  start() {
    this.stopped = false;
    for (const source of this.sources) this.run(source, this.retryMs);
  }

  async run(source, delay) {
    if (this.stopped) return;
    let next = delay;
    try {
      const started = this.now();
      await source.follow();
      // A long-lived stream resets the backoff; a quick drop keeps growing it.
      next = this.now() - started > 60000 ? this.retryMs : Math.min(delay * 2, this.maxRetryMs);
      this.log(`t3 ${source.name}: stream closed (${source.error || "ok"}); retrying in ${next}ms`);
    } catch (error) {
      source.error = describeError(error);
      this.log(`t3 ${source.name}: ${source.error}; polling once, retrying in ${next}ms`);
      // Keep the badge fed with a one-off snapshot while the socket is down.
      if (!source.shell || this.now() - source.lastOk > source.staleMs) await source.poll();
      next = Math.min(delay * 2, this.maxRetryMs);
    }
    if (this.stopped) return;
    this.timers.set(source, setTimeout(() => this.run(source, next), next));
  }

  stop() {
    this.stopped = true;
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    for (const source of this.sources) source.socket?.close();
  }

  status(only = null) {
    const known = this.sources.some((source) => source.name === only);
    return summarize(this.sources, this.now(), known ? only : null);
  }
}
