// Extension: badge-simulator
// Badge Simulator canvas: runs an app from badge/apps in the badger.github.io
// 3D badge simulator, reloads it whenever its files change, and can ask Copilot
// to deploy it to a connected badge. See README.md in this folder.
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, statSync, watch, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { joinSession, createCanvas } from "@github/copilot-sdk/extension";

const extDir = dirname(fileURLToPath(import.meta.url));
const webDir = join(extDir, "web");
const buildInfo = JSON.parse(readFileSync(join(webDir, "BUILD_INFO.json"), "utf8"));
const runtimeBase = `https://raw.githubusercontent.com/badger/badger.github.io/${buildInfo.revision}/public/simulator/`;
const cacheDir = join(process.env.COPILOT_HOME || join(homedir(), ".copilot"), "cache", "badge-simulator", buildInfo.revision);

const mime = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".wasm": "application/wasm",
    ".glb": "model/gltf-binary", ".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
};
const buttonBits = {
    down: 1, up: 2, select: 4, c: 4, right: 8, b: 8, left: 16, a: 16, home: 32,
    back: 8192, menu: 16384,
};
const ignoredFile = (name) => name === ".DS_Store" || name === "__pycache__" || name.endsWith(".pyc") || name.startsWith(".#");

let session;
const instances = new Map();
const inflight = new Map();

// ---- repository + app discovery ---------------------------------------------
function repoRoot(ctx) {
    const cwd = ctx?.session?.workingDirectory;
    if (cwd && existsSync(join(cwd, "badge", "apps"))) return resolve(cwd);
    return resolve(extDir, "..", "..", "..");
}
const appsDir = (root) => join(root, "badge", "apps");
function listApps(root) {
    try {
        return readdirSync(appsDir(root), { withFileTypes: true })
            .filter((d) => d.isDirectory() && existsSync(join(appsDir(root), d.name, "__init__.py")))
            .map((d) => d.name)
            .sort((a, b) => a.localeCompare(b));
    } catch {
        return [];
    }
}
function appFiles(dir, base = dir, out = []) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (ignoredFile(entry.name)) continue;
        const full = join(dir, entry.name);
        if (entry.isDirectory()) appFiles(full, base, out);
        else if (entry.isFile()) out.push({ path: relative(base, full).split(sep).join("/"), data: readFileSync(full).toString("base64") });
    }
    return out;
}

// ---- persisted selection --------------------------------------------------------
const stateFile = () => (session?.workspacePath ? join(session.workspacePath, "files", "badge-simulator.json") : null);
function loadLastApp() {
    try { return JSON.parse(readFileSync(stateFile(), "utf8")).app ?? null; } catch { return null; }
}
function saveLastApp(app) {
    const file = stateFile();
    if (!file) return;
    try { mkdirSync(dirname(file), { recursive: true }); writeFileSync(file, JSON.stringify({ app }) + "\n"); } catch {}
}

// ---- runtime proxy with disk cache ------------------------------------------------
async function runtimeFile(rel) {
    const file = join(cacheDir, rel);
    if (!file.startsWith(cacheDir + sep)) throw Object.assign(new Error("Bad path"), { status: 400 });
    if (existsSync(file)) return readFileSync(file);
    if (!inflight.has(rel)) {
        inflight.set(rel, (async () => {
            const response = await fetch(runtimeBase + rel.split("/").map(encodeURIComponent).join("/"));
            if (!response.ok) throw Object.assign(new Error(`${response.status} fetching ${rel}`), { status: response.status });
            const bytes = Buffer.from(await response.arrayBuffer());
            mkdirSync(dirname(file), { recursive: true });
            const tmp = `${file}.${process.pid}.tmp`;
            writeFileSync(tmp, bytes);
            renameSync(tmp, file);
            return bytes;
        })().finally(() => inflight.delete(rel)));
    }
    return inflight.get(rel);
}

// ---- per-instance state + server ---------------------------------------------------
function readBody(req) {
    return new Promise((resolveBody, reject) => {
        const chunks = [];
        req.on("data", (c) => chunks.push(c));
        req.on("end", () => {
            try { resolveBody(chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {}); } catch (e) { reject(e); }
        });
        req.on("error", reject);
    });
}
const json = (res, status, body) => { res.writeHead(status, { "Content-Type": mime[".json"], "Cache-Control": "no-store" }); res.end(JSON.stringify(body)); };

function broadcast(inst, event) {
    const data = `data: ${JSON.stringify(event)}\n\n`;
    for (const client of inst.clients) client.write(data);
}

function watchApp(inst) {
    inst.watcher?.close();
    inst.watcher = null;
    clearTimeout(inst.reloadTimer);
    if (!inst.app) return;
    try {
        inst.watcher = watch(join(appsDir(inst.root), inst.app), { recursive: true }, (_type, name) => {
            if (name && String(name).split(/[\\/]/).some(ignoredFile)) return;
            clearTimeout(inst.reloadTimer);
            inst.reloadTimer = setTimeout(() => {
                inst.revision++;
                broadcast(inst, { type: "reload", app: inst.app, revision: inst.revision });
            }, 300);
        });
        inst.watcher.on("error", () => {});
    } catch (error) {
        session?.log(`badge-simulator: could not watch ${inst.app}: ${error.message}`, { level: "warning" });
    }
}

// ---- console output, waiting and diagnostics -----------------------------------------
// inst.log is a sliding window; cursors are absolute line numbers so callers can
// ask for "output since X" even after older lines are trimmed or an app reloads.
const LOG_LIMIT = 2000;
const cursorOf = (inst) => inst.logBase + inst.log.length;
const linesSince = (inst, cursor) => inst.log.slice(Math.max(0, Number(cursor ?? 0) - inst.logBase));
function clearLog(inst) { inst.logBase += inst.log.length; inst.log = []; inst.fatal = false; }
function notify(inst) { for (const waiter of [...inst.waiters]) waiter(); }
function waitUntil(inst, check, timeoutMs) {
    return new Promise((done) => {
        let timer;
        const waiter = () => { const result = check(); if (result) finish(result); };
        const finish = (result) => { clearTimeout(timer); inst.waiters.delete(waiter); done(result); };
        inst.waiters.add(waiter);
        timer = setTimeout(() => finish(null), timeoutMs);
        waiter();
    });
}
const clampMs = (value, fallback, max = 60000) => Math.max(0, Math.min(max, Number(value ?? fallback) || 0));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function ingestLog(inst, lines) {
    for (const raw of lines) {
        const line = String(raw);
        const marker = /^\[sim-exec:([\w-]+):(begin|ok|error)\]$/.exec(line);
        if (marker) {
            const [, id, kind] = marker;
            if (kind === "begin") inst.execCurrent = { id, lines: [] };
            else {
                const pending = inst.execs.get(id);
                const output = inst.execCurrent?.id === id ? inst.execCurrent.lines : [];
                inst.execCurrent = null;
                if (pending) { inst.execs.delete(id); pending({ ok: kind === "ok", output: output.join("\n") }); }
            }
            continue;
        }
        if (inst.execCurrent) { inst.execCurrent.lines.push(line); continue; }
        // badgeware.fatal_error() prints "- ERROR: ..." and parks on an error screen.
        if (line.startsWith("- ERROR:")) inst.fatal = true;
        if (line.startsWith("[simulator] Running ") || line.startsWith("[simulator] Restarting app")) inst.fatal = false;
        inst.log.push(line);
    }
    if (inst.log.length > LOG_LIMIT) { const drop = inst.log.length - LOG_LIMIT; inst.log.splice(0, drop); inst.logBase += drop; }
    notify(inst);
}

// Turns the latest MicroPython traceback in the current run into repo paths.
function lastError(inst) {
    let start = 0;
    for (let i = inst.log.length - 1; i >= 0; i--) if (inst.log[i].startsWith("[simulator] Running ")) { start = i; break; }
    const run = inst.log.slice(start);
    let tb = -1;
    for (let i = run.length - 1; i >= 0; i--) if (/^(Traceback \(most recent call last\):|- ERROR:)/.test(run[i])) { tb = i; break; }
    if (tb < 0) return null;
    const frames = [];
    let message = "";
    const traceback = [];
    for (const [offset, line] of run.slice(tb).entries()) {
        traceback.push(line);
        const frame = /File "([^"]+)", line (\d+)(?:, in (.+))?/.exec(line);
        if (frame) {
            const [, rawFile, lineNo, fn] = frame;
            const file = rawFile.replace(/^\/+/, "/");
            const repoFile = file.startsWith("/system/") ? `badge/${file.slice("/system/".length)}` : null;
            frames.push({ file, line: Number(lineNo), function: fn ?? null, repo_path: repoFile && existsSync(join(inst.root, repoFile)) ? `${repoFile}:${lineNo}` : null });
        } else if (offset > 0 && !/^\s/.test(line)) { message = line; break; }
        else if (offset === 0 && line.startsWith("- ERROR:")) message = line.slice(8).trim();
    }
    const inApp = [...frames].reverse().find((f) => f.repo_path?.startsWith(`badge/apps/${inst.app}/`)) ?? [...frames].reverse().find((f) => f.repo_path);
    return { message, location: inApp?.repo_path ?? null, frames, traceback: traceback.join("\n") };
}

function snapshot(inst) {
    const stats = inst.stats ?? {};
    const age = inst.statsAt ? Date.now() - inst.statsAt : null;
    return {
        app: inst.app, revision: inst.revision, status: inst.status, state: inst.state,
        crashed: inst.state === "error" || Boolean(inst.fatal),
        running: stats.running ?? null, fps: stats.fps ?? null, frames: stats.frames ?? null,
        resolution: stats.width ? `${stats.width}x${stats.height}` : null,
        paused: stats.paused ?? null, upside_down: stats.rotated ?? null, backlight: stats.backlight ?? null,
        connected: inst.clients.size > 0, stats_age_ms: age,
        error: lastError(inst), cursor: cursorOf(inst),
        ...(stats.paused ? { note: "The canvas is hidden, so the simulator is paused. Ask the user to show the Badge Simulator panel." } : {}),
    };
}

function selectApp(inst, app) {
    if (app && !listApps(inst.root).includes(app)) throw new Error(`Unknown app "${app}". Apps live in badge/apps/<name>/__init__.py.`);
    inst.app = app || null;
    inst.revision++;
    inst.status = inst.app ? `Loading ${inst.app}` : "Choose an app to run";
    inst.state = "";
    clearLog(inst);
    saveLastApp(inst.app);
    watchApp(inst);
    broadcast(inst, { type: "reload", app: inst.app, revision: inst.revision });
}

function deployPrompt(app) {
    return [
        `Deploy the \`${app}\` app from \`badge/apps/${app}\` to the GitHub Universe badge connected over USB, using USB mass storage. This request came from the Badge Simulator **Deploy** button, so the user has already tested it in the simulator; deploy to the hardware now.`,
        "",
        "Before touching the badge, read and follow the repository instructions: `hardware/USB_SERIAL.md` (all of \"Installing an app\", including \"Menu icon patch\") and `badge/AGENTS.md` (\"Working with a connected badge\"). They take precedence over this summary.",
        "",
        "1. Run `mpremote devs` to find the badge port (USB `2e8a:1101`). Use only explicit `mpremote connect <port> ...` commands, one at a time; never run serial commands concurrently.",
        "2. While the badge is in serial mode, run the menu icon patch check from `hardware/USB_SERIAL.md` to see whether `/system/apps/menu/app.py` needs the repository's patched `app.py`.",
        "3. Put the badge into USB mass-storage mode with `mpremote connect <port> exec \"import powman; powman.reset_into_msc()\"` (the serial error as it reboots is expected) and wait for the `BADGER` volume. Its root is the badge's `/system`.",
        `4. Copy the whole \`badge/apps/${app}\` directory into \`apps/\` on the volume (replacing any old copy), remove any \`.DS_Store\` or \`._*\` files, and confirm it matches with \`diff -rq\`. If step 2 showed the menu is unpatched, also copy \`badge/apps/menu/app.py\` to \`apps/menu/app.py\`. Do not change other system files.`,
        `5. Eject the volume, wait for the serial port to return, reset the badge, and verify with \`mpremote connect <port> fs ls :/system/apps/${app}\`.`,
        "6. Finally reboot the badge with `mpremote connect <port> reset` so it is out of mass-storage, REPL, and any test mode and back at the normal menu. Report success only after this reboot.",
        "",
        "Do not use `mpremote fs cp` or `mpremote mount` to install into `/system`; it is read-only over serial. If no badge is connected or a step needs me to press buttons on the badge, tell me exactly what to do.",
    ].join("\n");
}

async function handle(inst, req, res) {
    const url = new URL(req.url, "http://localhost");
    const path = decodeURIComponent(url.pathname);
    try {
        // Only serve this loopback origin: reject DNS-rebinding hosts, foreign origins and
        // POSTs without the page's custom header (which cross-origin callers can't send
        // without a CORS preflight this server never approves).
        const origin = new URL(inst.url).host;
        if (req.headers.host !== origin) return json(res, 403, { error: "Forbidden" });
        if (req.headers.origin && req.headers.origin !== `http://${origin}`) return json(res, 403, { error: "Forbidden" });
        if (req.method === "POST" && req.headers["x-badge-simulator"] !== "1") return json(res, 403, { error: "Forbidden" });
        if (path === "/events") {
            res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-store", Connection: "keep-alive" });
            res.write(": connected\n\n");
            inst.clients.add(res);
            notify(inst);
            const ping = setInterval(() => res.write(": ping\n\n"), 25000);
            req.on("close", () => { clearInterval(ping); inst.clients.delete(res); });
            return;
        }
        if (path === "/api/state") return json(res, 200, { apps: listApps(inst.root), app: inst.app });
        if (path === "/api/app") {
            if (!inst.app) { res.writeHead(204); return res.end(); }
            const dir = join(appsDir(inst.root), inst.app);
            if (!existsSync(join(dir, "__init__.py"))) return json(res, 404, { error: `badge/apps/${inst.app}/__init__.py not found` });
            return json(res, 200, { app: inst.app, revision: inst.revision, files: appFiles(dir) });
        }
        if (req.method === "POST") {
            const body = await readBody(req);
            if (path === "/api/log") { ingestLog(inst, body.lines ?? []); return json(res, 200, { ok: true }); }
            if (path === "/api/status") { inst.status = String(body.status ?? ""); inst.state = String(body.state ?? ""); notify(inst); return json(res, 200, { ok: true }); }
            if (path === "/api/stats") {
                // Several clients (the Copilot panel, a test browser) may be connected; prefer a visible one.
                const now = Date.now();
                inst.statsBy.set(body.client, { ...body, at: now });
                for (const [id, entry] of inst.statsBy) if (now - entry.at > 5000) inst.statsBy.delete(id);
                const entries = [...inst.statsBy.values()];
                const best = entries.filter((e) => !e.paused).sort((x, y) => y.at - x.at)[0] ?? entries.sort((x, y) => y.at - x.at)[0];
                inst.stats = best; inst.statsAt = best.at;
                notify(inst);
                return json(res, 200, { ok: true });
            }
            if (path === "/api/select") { selectApp(inst, body.app); return json(res, 200, { ok: true }); }
            if (path === "/api/screenshot") {
                const pending = inst.screenshots.get(body.id);
                if (pending) { inst.screenshots.delete(body.id); pending(body.screen); }
                return json(res, 200, { ok: true });
            }
            if (path === "/api/deploy") {
                const app = body.app || inst.app;
                if (!app) return json(res, 400, { error: "No app selected" });
                if (!listApps(inst.root).includes(app)) return json(res, 400, { error: `Unknown app "${app}"` });
                await session.send({ prompt: deployPrompt(app) });
                return json(res, 200, { ok: true });
            }
            return json(res, 404, { error: "Not found" });
        }
        if (path.startsWith("/simulator/")) {
            const rel = path.slice("/simulator/".length);
            const bytes = await runtimeFile(rel);
            res.writeHead(200, { "Content-Type": mime[extname(rel)] ?? "application/octet-stream", "Cache-Control": "max-age=86400" });
            return res.end(bytes);
        }
        const file = resolve(webDir, "." + (path === "/" ? "/index.html" : path));
        if (!file.startsWith(webDir + sep) || !existsSync(file) || !statSync(file).isFile()) return json(res, 404, { error: "Not found" });
        res.writeHead(200, { "Content-Type": mime[extname(file)] ?? "application/octet-stream", "Cache-Control": "no-store" });
        res.end(readFileSync(file));
    } catch (error) {
        if (!res.headersSent) json(res, error.status ?? 500, { error: error.message });
        else res.end();
    }
}

async function startInstance(ctx) {
    const root = repoRoot(ctx);
    const inst = {
        root, app: null, revision: 0, status: "Starting", state: "", log: [], logBase: 0,
        stats: null, statsAt: 0, waiters: new Set(), execs: new Map(), execCurrent: null,
        clients: new Set(), statsBy: new Map(), screenshots: new Map(), watcher: null, reloadTimer: null, server: null, url: "",
    };
    const remembered = loadLastApp();
    if (remembered && listApps(root).includes(remembered)) inst.app = remembered;
    inst.server = createServer((req, res) => void handle(inst, req, res));
    await new Promise((r) => inst.server.listen(0, "127.0.0.1", r));
    inst.url = `http://127.0.0.1:${inst.server.address().port}/`;
    let appsTimer;
    try {
        inst.appsWatcher = watch(appsDir(root), () => {
            clearTimeout(appsTimer);
            appsTimer = setTimeout(() => broadcast(inst, { type: "apps", apps: listApps(root) }), 500);
        });
        inst.appsWatcher.on("error", () => {});
    } catch {}
    watchApp(inst);
    return inst;
}

function instanceFor(ctx) {
    const inst = instances.get(ctx.instanceId);
    if (!inst) throw new Error("The Badge Simulator canvas is not open. Open it with open_canvas first.");
    return inst;
}
async function requireClient(inst, timeoutMs = 15000) {
    if (inst.clients.size) return;
    if (!await waitUntil(inst, () => inst.clients.size > 0, timeoutMs)) {
        throw new Error("The Badge Simulator canvas is not connected. Open it (or re-run open_canvas with the same instanceId) and keep it visible, then try again.");
    }
}

// ---- agent actions ------------------------------------------------------------------
function buttonBit(button) {
    const name = String(button ?? "").toLowerCase().replace(/^button_/, "");
    const bit = buttonBits[name];
    if (!bit) throw new Error(`Unknown button "${button}". Use one of: ${Object.keys(buttonBits).join(", ")}`);
    return { name, bit };
}
async function doPress(inst, input) {
    await requireClient(inst);
    const names = Array.isArray(input?.button) ? input.button : String(input?.button ?? "").split("+");
    const pressed = names.map(buttonBit);
    const ms = Math.max(30, Math.min(10000, Number(input?.duration_ms ?? 120)));
    broadcast(inst, { type: "press", bit: pressed.reduce((mask, b) => mask | b.bit, 0), ms });
    return { pressed: pressed.map((b) => b.name).join("+"), duration_ms: ms };
}
async function doScreenshot(inst, label) {
    await requireClient(inst);
    const id = Math.random().toString(36).slice(2);
    const dataUrl = await new Promise((ok, fail) => {
        const timer = setTimeout(() => { inst.screenshots.delete(id); fail(new Error("Timed out waiting for the canvas")); }, 5000);
        inst.screenshots.set(id, (value) => { clearTimeout(timer); ok(value); });
        broadcast(inst, { type: "screenshot", id });
    });
    const dir = join(session.workspacePath ?? cacheDir, "files", "badge-simulator");
    mkdirSync(dir, { recursive: true });
    const slug = label ? `-${String(label).replace(/[^\w-]+/g, "_").slice(0, 40)}` : "";
    const file = join(dir, `${inst.app ?? "screen"}${slug}-${Date.now()}.png`);
    writeFileSync(file, Buffer.from(String(dataUrl).replace(/^data:image\/png;base64,/, ""), "base64"));
    return { path: file, app: inst.app };
}
async function doExec(inst, input) {
    await requireClient(inst);
    const code = String(input?.code ?? "");
    if (!code.trim()) throw new Error("Pass MicroPython source in `code`.");
    const id = Math.random().toString(36).slice(2, 10);
    const timeout = clampMs(input?.timeout_ms, 5000);
    const result = await new Promise((done) => {
        const timer = setTimeout(() => { inst.execs.delete(id); done(null); }, timeout);
        inst.execs.set(id, (value) => { clearTimeout(timer); done(value); });
        broadcast(inst, { type: "exec", id, code });
    });
    if (!result) {
        const partial = inst.execCurrent?.id === id ? inst.execCurrent.lines.join("\n") : "";
        return {
            ok: false, timed_out: true, output: partial,
            hint: "No result yet. The code may still be running, the app may be blocking without calling badge.poll(), or the canvas may be hidden (paused). Check get_output.",
            ...snapshot(inst),
        };
    }
    return { ...result, ran_in: inst.state === "stopped" ? "standalone" : "app", app: inst.app, state: inst.state };
}
async function doWaitFor(inst, input) {
    const since = input?.since ?? cursorOf(inst);
    const pattern = input?.pattern ? new RegExp(input.pattern) : null;
    const onCrash = input?.until_crash !== false;
    const minFrames = input?.frames ? Number(input.frames) : null;
    const startFrames = new Map([...inst.statsBy].map(([id, e]) => [id, e.frames]));
    const outcome = await waitUntil(inst, () => {
        if (pattern) {
            const hit = linesSince(inst, since).find((line) => pattern.test(line));
            if (hit !== undefined) return { reason: "match", matched_line: hit };
        }
        if (onCrash && (inst.state === "error" || inst.fatal)) return { reason: "crash" };
        if (minFrames) {
            for (const [id, e] of inst.statsBy) {
                if (!startFrames.has(id)) startFrames.set(id, e.frames);
                else if (!e.paused && e.frames - startFrames.get(id) >= minFrames) return { reason: "frames" };
            }
        }
        return null;
    }, clampMs(input?.timeout_ms, 5000));
    return { ...(outcome ?? { reason: "timeout" }), ...snapshot(inst), output: linesSince(inst, since).slice(-80).join("\n") };
}
function doReload(inst, restartRuntime) {
    inst.revision++;
    inst.state = "";
    clearLog(inst);
    broadcast(inst, restartRuntime ? { type: "restart" } : { type: "reload", app: inst.app, revision: inst.revision });
}
async function waitForRun(inst, timeoutMs = 15000) {
    const since = cursorOf(inst);
    const ok = await waitUntil(inst, () => linesSince(inst, since).some((l) => l.startsWith("[simulator] Running ")) || null, timeoutMs);
    if (!ok) throw new Error("The app did not start within the timeout. Check get_output.");
}

async function runScript(inst, input) {
    await requireClient(inst);
    const steps = Array.isArray(input?.steps) ? input.steps : [];
    const stopOnCrash = input?.stop_on_crash !== false;
    if (input?.restart) { doReload(inst, false); await waitForRun(inst); }
    const since = cursorOf(inst);
    const results = [];
    for (const [index, step] of steps.entries()) {
        let result;
        try {
            if (step.press !== undefined) {
                result = await doPress(inst, { button: step.press, duration_ms: step.duration_ms });
                await sleep(result.duration_ms + 60);
            } else if (step.wait_ms !== undefined) {
                await sleep(clampMs(step.wait_ms, 0));
                result = { waited_ms: clampMs(step.wait_ms, 0) };
            } else if (step.screenshot !== undefined) {
                result = await doScreenshot(inst, typeof step.screenshot === "string" ? step.screenshot : `step${index + 1}`);
            } else if (step.exec !== undefined) {
                result = await doExec(inst, { code: step.exec, timeout_ms: step.timeout_ms });
            } else if (step.wait_for !== undefined) {
                const options = typeof step.wait_for === "object" && step.wait_for ? step.wait_for : { pattern: String(step.wait_for) };
                const waited = await doWaitFor(inst, { timeout_ms: step.timeout_ms, since: step.since_start ? since : undefined, ...options });
                result = { reason: waited.reason, matched_line: waited.matched_line };
            } else if (step.rotate !== undefined) {
                broadcast(inst, { type: "rotate", value: step.rotate === "toggle" ? undefined : Boolean(step.rotate) });
                await sleep(300);
                result = { rotated: step.rotate };
            } else throw new Error(`Unknown step ${JSON.stringify(step)}. Use press, wait_ms, screenshot, exec, wait_for or rotate.`);
            results.push({ step: index + 1, ...step, result });
        } catch (error) {
            results.push({ step: index + 1, ...step, error: error.message });
            break;
        }
        if (stopOnCrash && (inst.state === "error" || inst.fatal)) { results.push({ step: index + 1, stopped: "app crashed" }); break; }
    }
    return { steps: results, ...snapshot(inst), output: linesSince(inst, since).slice(-120).join("\n") };
}

// Static checks that mirror the repo's PR validation and common porting mistakes.
const legacyPatterns = [
    [/^\s*(import badge\b|from badge import)/m, "Imports `badge`; on 2026 firmware `badge` is a runtime global, do not import it."],
    [/from badgeware import [^\n]*\b(io|brushes|shapes|screen|PixelFont|run)\b/, "Imports 2025 badgeware APIs (io/brushes/shapes/screen/PixelFont/run); 2026 apps use the runtime globals."],
    [/\bio\.(BUTTON_\w+|pressed|held|released|ticks)/, "Uses 2025 `io.*` input/timing; use badge.pressed()/held()/released() and badge.ticks."],
    [/\bbrushes\.|\bshapes\.[a-z]/, "Uses 2025 `brushes`/`shapes`; use color.rgb(), screen.pen and shape.*."],
    [/\bscreen\.draw\(/, "Uses 2025 `screen.draw()`; use screen.shape()."],
];
function pngSize(file) {
    const b = readFileSync(file);
    if (b.length < 24 || b.toString("ascii", 1, 4) !== "PNG") return null;
    return { width: b.readUInt32BE(16), height: b.readUInt32BE(20) };
}
function readmeDescription(text) {
    const skip = ["#", ">", "|", "-", "*", "!", "[!", "```", "<"];
    const paragraph = [];
    for (const line of text.split(/\r?\n/)) {
        const s = line.trim();
        if (!s) { if (paragraph.length) break; continue; }
        if (skip.some((p) => s.startsWith(p))) { if (paragraph.length) break; continue; }
        paragraph.push(s);
    }
    const joined = paragraph.join(" ");
    const m = /^(.+?[.!?])(?=\s|$)/.exec(joined);
    return (m ? m[1] : joined).trim();
}
function checkApp(inst, app) {
    app = app || inst.app;
    if (!app) throw new Error("No app selected.");
    const dir = join(appsDir(inst.root), app);
    if (!existsSync(dir)) throw new Error(`badge/apps/${app} does not exist.`);
    const errors = [], warnings = [];
    if (!existsSync(join(dir, "__init__.py"))) errors.push("Missing __init__.py.");
    const icon = join(dir, "icon.png");
    if (!existsSync(icon)) errors.push("Missing 24x24 icon.png.");
    else { const size = pngSize(icon); if (!size) errors.push("icon.png is not a PNG."); else if (size.width !== 24 || size.height !== 24) warnings.push(`icon.png is ${size.width}x${size.height}; the menu expects 24x24.`); }
    const readme = ["README.md", "readme.md"].map((n) => join(dir, n)).find(existsSync);
    if (!readme) errors.push("Missing README.md (the Validate app READMEs check will fail).");
    else {
        const sentence = readmeDescription(readFileSync(readme, "utf8"));
        if (!sentence) errors.push("README.md has no description paragraph after the title.");
        else if (sentence.length < 10) errors.push("README description is too short (minimum 10 characters).");
        else if (sentence.length > 200) errors.push(`README first sentence is too long (${sentence.length} > 200 characters).`);
        else if (!".!?".includes(sentence.at(-1))) errors.push("README first sentence must end with punctuation.");
    }
    const files = appFiles(dir).map((f) => f.path);
    for (const rel of files.filter((f) => f.endsWith(".py"))) {
        const text = readFileSync(join(dir, rel), "utf8");
        for (const [re, message] of legacyPatterns) {
            const m = re.exec(text);
            if (m) warnings.push(`badge/apps/${app}/${rel}:${text.slice(0, m.index).split("\n").length}: ${message}`);
        }
    }
    if (existsSync(join(appsDir(inst.root), "..", "secrets.py")) && readFileSync(join(appsDir(inst.root), "..", "secrets.py"), "utf8").match(/^\s*(WIFI_SSID|WIFI_PASSWORD|GITHUB_USERNAME|GITHUB_TOKEN)\s*=\s*["'][^"']+["']/m))
        warnings.push("badge/secrets.py contains values; keep it empty in source control.");
    return { app, ok: errors.length === 0, errors, warnings, files };
}

session = await joinSession({
    canvases: [
        createCanvas({
            id: "badge-simulator",
            displayName: "Badge Simulator",
            description:
                "Runs a Universe 2026 badge app from badge/apps/<app> in the 3D badge simulator. The canvas reloads automatically whenever the app's files change, mirrors the app theme, and has a Deploy button that asks Copilot to install the app on a connected badge. Open it with input {app: \"<folder name>\"} while building or testing an app.",
            inputSchema: {
                type: "object",
                properties: { app: { type: "string", description: "Folder name under badge/apps to run, e.g. flappy_mona" } },
            },
            actions: [
                {
                    name: "load_app",
                    description: "Switch the simulator to another app in badge/apps.",
                    inputSchema: { type: "object", properties: { app: { type: "string" } }, required: ["app"] },
                    handler: (ctx) => { const inst = instanceFor(ctx); selectApp(inst, ctx.input?.app); return { app: inst.app }; },
                },
                {
                    name: "reload",
                    description: "Reload the current app from disk (normally automatic when files change). Pass {restart_runtime:true} to also reboot the MicroPython runtime, and {wait:true} to wait until it is running again.",
                    inputSchema: { type: "object", properties: { restart_runtime: { type: "boolean" }, wait: { type: "boolean" } } },
                    handler: async (ctx) => {
                        const inst = instanceFor(ctx);
                        doReload(inst, ctx.input?.restart_runtime);
                        if (ctx.input?.wait) await waitForRun(inst);
                        return { app: inst.app, revision: inst.revision, cursor: cursorOf(inst) };
                    },
                },
                {
                    name: "get_output",
                    description: "Return simulator status (running/crashed, fps, resolution, paused, orientation), the latest traceback mapped to a repo file:line, and recent MicroPython console output. Pass `since` (a cursor from a previous call) to get only new lines.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            lines: { type: "number", description: "Number of recent lines (default 80)" },
                            since: { type: "number", description: "Only return lines after this cursor" },
                        },
                    },
                    handler: (ctx) => {
                        const inst = instanceFor(ctx);
                        const lines = ctx.input?.since !== undefined ? linesSince(inst, ctx.input.since) : inst.log;
                        return { ...snapshot(inst), output: lines.slice(-(ctx.input?.lines ?? 80)).join("\n") };
                    },
                },
                {
                    name: "press",
                    description: "Press badge buttons in the simulator. button: up, down, left, right, select, home, back, menu (or a, b, c); combine with \"a+b\" or an array.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            button: { oneOf: [{ type: "string" }, { type: "array", items: { type: "string" } }] },
                            duration_ms: { type: "number", description: "Hold time (default 120, max 10000)" },
                        },
                        required: ["button"],
                    },
                    handler: (ctx) => doPress(instanceFor(ctx), ctx.input),
                },
                {
                    name: "screenshot",
                    description: "Capture the simulated badge screen at its native resolution as a PNG and return its file path (view it with the view tool).",
                    inputSchema: { type: "object", properties: { label: { type: "string" } } },
                    handler: (ctx) => doScreenshot(instanceFor(ctx), ctx.input?.label),
                },
                {
                    name: "exec",
                    description: "Run MicroPython in the simulator, like the badge REPL, and return its output or traceback. While the app runs, code executes between frames inside the app module's globals, so you can inspect or change live state (expressions print their repr). If the app has crashed or stopped, it runs as a standalone program instead (reload to restart the app). Useful for checking APIs, files under /state, and app variables.",
                    inputSchema: {
                        type: "object",
                        properties: { code: { type: "string" }, timeout_ms: { type: "number", description: "Default 5000" } },
                        required: ["code"],
                    },
                    handler: (ctx) => doExec(instanceFor(ctx), ctx.input),
                },
                {
                    name: "wait_for",
                    description: "Wait until console output matches a regex `pattern`, the app crashes, a number of `frames` render, or `timeout_ms` passes (default 5000). Returns the reason, status and new output. Pass `since` (a cursor) to include output already printed.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            pattern: { type: "string" }, frames: { type: "number" }, timeout_ms: { type: "number" },
                            since: { type: "number" }, until_crash: { type: "boolean", description: "Also stop on crash (default true)" },
                        },
                    },
                    handler: (ctx) => doWaitFor(instanceFor(ctx), ctx.input),
                },
                {
                    name: "run_script",
                    description: "Run a scripted test: a list of steps executed in order, returning per-step results, screenshot paths, final status and output. Steps: {press:\"a\", duration_ms}, {wait_ms}, {screenshot:\"label\"}, {exec:\"code\"}, {wait_for:\"regex\" or {pattern, frames, until_crash}, timeout_ms}, {rotate:true|false|\"toggle\"}. Set restart:true to reload the app first. Stops on crash unless stop_on_crash:false.",
                    inputSchema: {
                        type: "object",
                        properties: {
                            steps: { type: "array", items: { type: "object" } },
                            restart: { type: "boolean" },
                            stop_on_crash: { type: "boolean" },
                        },
                        required: ["steps"],
                    },
                    handler: (ctx) => runScript(instanceFor(ctx), ctx.input),
                },
                {
                    name: "rotate",
                    description: "Turn the simulated badge upside down or back (same as the Rotate button). Pass upside_down true/false, or omit to toggle.",
                    inputSchema: { type: "object", properties: { upside_down: { type: "boolean" } } },
                    handler: async (ctx) => {
                        const inst = instanceFor(ctx);
                        await requireClient(inst);
                        broadcast(inst, { type: "rotate", value: ctx.input?.upside_down });
                        await sleep(1200);
                        return { upside_down: inst.stats?.rotated ?? null };
                    },
                },
                {
                    name: "check_app",
                    description: "Static pre-flight checks for an app (default: the current one): __init__.py, 24x24 icon.png, README description rules from the PR check, and 2025-era API usage that breaks on 2026 firmware.",
                    inputSchema: { type: "object", properties: { app: { type: "string" } } },
                    handler: (ctx) => checkApp(instanceFor(ctx), ctx.input?.app),
                },
            ],
            open: async (ctx) => {
                let inst = instances.get(ctx.instanceId);
                if (!inst) {
                    inst = await startInstance(ctx);
                    instances.set(ctx.instanceId, inst);
                }
                const app = ctx.input && typeof ctx.input === "object" ? ctx.input.app : undefined;
                if (app && app !== inst.app) selectApp(inst, app);
                return { title: inst.app ? `Badge Simulator · ${inst.app}` : "Badge Simulator", url: inst.url };
            },
            onClose: async (ctx) => {
                const inst = instances.get(ctx.instanceId);
                if (!inst) return;
                instances.delete(ctx.instanceId);
                inst.watcher?.close();
                inst.appsWatcher?.close();
                clearTimeout(inst.reloadTimer);
                for (const client of inst.clients) client.end();
                await new Promise((r) => inst.server.close(() => r()));
            },
        }),
    ],
});
