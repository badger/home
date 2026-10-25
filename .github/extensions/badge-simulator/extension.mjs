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

function selectApp(inst, app) {
    if (app && !listApps(inst.root).includes(app)) throw new Error(`Unknown app "${app}". Apps live in badge/apps/<name>/__init__.py.`);
    inst.app = app || null;
    inst.revision++;
    inst.status = inst.app ? `Loading ${inst.app}` : "Choose an app to run";
    inst.log = [];
    saveLastApp(inst.app);
    watchApp(inst);
    broadcast(inst, { type: "reload", app: inst.app, revision: inst.revision });
}

function deployPrompt(app) {
    return [
        `Deploy the \`${app}\` app from \`badge/apps/${app}\` to the GitHub Universe badge that is connected over USB.`,
        "Follow the repository instructions: read `hardware/USB_SERIAL.md` (especially \"Installing an app\") and `badge/AGENTS.md` before touching the badge.",
        "Use `mpremote devs` to find the badge port, then only explicit `mpremote connect <port> ...` commands, one at a time (never run serial commands concurrently).",
        `\`/system\` is read-only over the serial REPL, so put the badge into USB mass-storage mode, copy \`badge/apps/${app}\` to \`/system/apps/${app}\` on the BADGER volume, eject it, reset the badge, and verify with \`mpremote connect <port> fs ls :/system/apps/${app}\`.`,
        "If no badge is connected or a step needs me to press buttons on the badge, tell me exactly what to do.",
    ].join("\n");
}

async function handle(inst, req, res) {
    const url = new URL(req.url, "http://localhost");
    const path = decodeURIComponent(url.pathname);
    try {
        if (path === "/events") {
            res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-store", Connection: "keep-alive" });
            res.write(": connected\n\n");
            inst.clients.add(res);
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
            if (path === "/api/log") {
                for (const line of body.lines ?? []) inst.log.push(String(line));
                if (inst.log.length > 500) inst.log.splice(0, inst.log.length - 500);
                return json(res, 200, { ok: true });
            }
            if (path === "/api/status") { inst.status = String(body.status ?? ""); inst.state = String(body.state ?? ""); return json(res, 200, { ok: true }); }
            if (path === "/api/select") { selectApp(inst, body.app); return json(res, 200, { ok: true }); }
            if (path === "/api/screenshot") {
                const pending = inst.screenshots.get(body.id);
                if (pending) { inst.screenshots.delete(body.id); pending(body.screen); }
                return json(res, 200, { ok: true });
            }
            if (path === "/api/deploy") {
                const app = body.app || inst.app;
                if (!app) return json(res, 400, { error: "No app selected" });
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
        root, app: null, revision: 0, status: "Starting", state: "", log: [],
        clients: new Set(), screenshots: new Map(), watcher: null, reloadTimer: null, server: null, url: "",
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
const requireClient = (inst) => {
    if (!inst.clients.size) throw new Error("The Badge Simulator canvas is not connected yet. Wait a moment and try again.");
};

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
                    description: "Reload the current app from disk (normally automatic when files change). Pass {restart_runtime:true} to also reboot the MicroPython runtime.",
                    inputSchema: { type: "object", properties: { restart_runtime: { type: "boolean" } } },
                    handler: (ctx) => {
                        const inst = instanceFor(ctx);
                        inst.revision++;
                        inst.log = [];
                        broadcast(inst, ctx.input?.restart_runtime ? { type: "restart" } : { type: "reload", app: inst.app, revision: inst.revision });
                        return { app: inst.app, revision: inst.revision };
                    },
                },
                {
                    name: "get_output",
                    description: "Return the simulator status and recent MicroPython console output (print output and tracebacks) for the running app.",
                    inputSchema: { type: "object", properties: { lines: { type: "number", description: "Number of recent lines (default 80)" } } },
                    handler: (ctx) => {
                        const inst = instanceFor(ctx);
                        return { app: inst.app, revision: inst.revision, status: inst.status, state: inst.state, output: inst.log.slice(-(ctx.input?.lines ?? 80)).join("\n") };
                    },
                },
                {
                    name: "press",
                    description: "Press a badge button in the simulator. button: up, down, left, right, select, home, back, menu (or a, b, c).",
                    inputSchema: {
                        type: "object",
                        properties: { button: { type: "string" }, duration_ms: { type: "number", description: "Hold time (default 120)" } },
                        required: ["button"],
                    },
                    handler: (ctx) => {
                        const inst = instanceFor(ctx);
                        requireClient(inst);
                        const name = String(ctx.input?.button ?? "").toLowerCase().replace(/^button_/, "");
                        const bit = buttonBits[name];
                        if (!bit) throw new Error(`Unknown button "${ctx.input?.button}". Use one of: ${Object.keys(buttonBits).join(", ")}`);
                        const ms = Math.max(30, Math.min(5000, Number(ctx.input?.duration_ms ?? 120)));
                        broadcast(inst, { type: "press", bit, ms });
                        return { pressed: name, duration_ms: ms };
                    },
                },
                {
                    name: "screenshot",
                    description: "Capture the simulated badge screen as a PNG and return its file path (view it with the view tool).",
                    handler: async (ctx) => {
                        const inst = instanceFor(ctx);
                        requireClient(inst);
                        const id = Math.random().toString(36).slice(2);
                        const dataUrl = await new Promise((ok, fail) => {
                            const timer = setTimeout(() => { inst.screenshots.delete(id); fail(new Error("Timed out waiting for the canvas")); }, 5000);
                            inst.screenshots.set(id, (value) => { clearTimeout(timer); ok(value); });
                            broadcast(inst, { type: "screenshot", id });
                        });
                        const dir = join(session.workspacePath ?? cacheDir, "files", "badge-simulator");
                        mkdirSync(dir, { recursive: true });
                        const file = join(dir, `${inst.app ?? "screen"}-${Date.now()}.png`);
                        writeFileSync(file, Buffer.from(String(dataUrl).replace(/^data:image\/png;base64,/, ""), "base64"));
                        return { path: file, app: inst.app };
                    },
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
