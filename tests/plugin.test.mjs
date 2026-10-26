import assert from "node:assert/strict";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { loadProvider } from "./helpers/plugin-harness.mjs";
import { MAX_FILE_BYTES, saveAppFile } from "../com.github.copilot/extensions/badge-simulator/workspace.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const extension = join("com.github.copilot", "extensions", "badge-simulator");
const json = (path) => JSON.parse(readFileSync(path, "utf8"));
const manifest = json(join(root, "plugin.json"));
const headers = { "Content-Type": "application/json", "X-Badge-Simulator": "1" };
async function post(url, path, body, status = 200) {
    const response = await fetch(new URL(path, url), { method: "POST", headers, body: JSON.stringify(body) });
    const data = await response.json();
    assert.equal(response.status, status, JSON.stringify(data));
    return data;
}
async function fixture(t, empty = false) {
    const temp = mkdtempSync(join(tmpdir(), "badge-plugin-test-"));
    const project = join(temp, "My Badge Project");
    const installed = join(temp, "Plugin Cache");
    mkdirSync(project);
    cpSync(join(root, extension), join(installed, extension), { recursive: true });
    cpSync(join(root, "skills", "hyb26-skill"), join(installed, "skills", "hyb26-skill"), {
        recursive: true, filter: (path) => !path.includes("__pycache__"),
    });
    if (!empty) {
        mkdirSync(join(project, "badge", "apps", "mine"), { recursive: true });
        writeFileSync(join(project, "badge", "apps", "mine", "__init__.py"), 'print("workspace app")\n');
    }
    const provider = await loadProvider(join(installed, extension, "extension.mjs"), project, join(temp, "Artifacts"), join(temp, "Cache"));
    t.after(async () => {
        await provider.close();
        rmSync(temp, { recursive: true, force: true });
    });
    return { provider, project, installed, temp };
}

test("portable manifest and marketplace canvas layout", () => {
    const fields = new Set(["$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"]);
    assert.equal(manifest.$schema, "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json");
    assert.match(manifest.name, /^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/);
    assert.ok(manifest.name.length <= 64);
    assert.match(manifest.version, /^\d+\.\d+\.\d+$/);
    for (const field of Object.keys(manifest)) assert.ok(fields.has(field), `Unknown manifest field: ${field}`);
    assert.ok(manifest.keywords.includes("canvas"));
    assert.equal(manifest.extensions["com.github.copilot"].logo, "assets/preview.png");
    assert.ok(!manifest.extensions["com.github.awesome-copilot"], "External plugins ship materialized components");
    const preview = readFileSync(join(root, "assets", "preview.png"));
    assert.equal(preview.toString("hex", 0, 8), "89504e470d0a1a0a");
    assert.ok(preview.readUInt32BE(16) >= 160 && preview.readUInt32BE(20) >= 120);
    assert.deepEqual(readdirSync(join(root, "com.github.copilot", "extensions")), ["badge-simulator"]);
    const build = json(join(root, extension, "web", "BUILD_INFO.json"));
    assert.match(build.revision, /^[a-f0-9]{40}$/);
});

test("skills and project loaders reference real packaged files", () => {
    assert.deepEqual(readdirSync(join(root, "skills")).sort(), ["badge-simulator", "hyb26-skill"]);
    for (const name of readdirSync(join(root, "skills"))) {
        const skill = readFileSync(join(root, "skills", name, "SKILL.md"), "utf8").replaceAll("\r\n", "\n");
        assert.ok(skill.startsWith(`---\nname: ${name}\n`));
        assert.match(skill, /\ndescription: .+\n/);
        for (const [, target] of skill.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
            if (/^https?:|^#/.test(target)) continue;
            assert.ok(existsSync(resolve(root, "skills", name, target.split("#")[0])), `${name}: missing ${target}`);
        }
        assert.ok(readFileSync(join(root, ".github", "skills", name, "SKILL.md"), "utf8").includes(`../../../skills/${name}/SKILL.md`));
    }
    assert.ok(readFileSync(join(root, ".github", "extensions", "badge-simulator", "extension.mjs"), "utf8").includes(`../../../com.github.copilot/extensions/badge-simulator/extension.mjs`));
});

test("installed canvas reads the consuming workspace, not its plugin cache", async (t) => {
    const { provider, project } = await fixture(t);
    const { url } = await provider.open("mine", { app: "mine" });
    assert.equal(provider.canvas.id, "badge-simulator");
    const state = await fetch(new URL("/api/state", url)).then((r) => r.json());
    assert.deepEqual(state.apps, ["mine"]);
    assert.equal(state.project_root, project);
    const payload = await fetch(new URL("/api/app", url)).then((r) => r.json());
    assert.equal(Buffer.from(payload.files[0].data, "base64").toString(), 'print("workspace app")\n');
    const html = await fetch(url).then((r) => r.text());
    assert.ok(html.includes("data-source") && html.includes("data-new-app"));
    for (const file of ["editor.js", "simulator.css", "simulator.js"]) {
        assert.equal((await fetch(new URL(file, url))).status, 200);
    }
    assert.throws(() => provider.action("mine", "load_app", { app: "flappy_mona" }), /Unknown app/);
    const denied = await fetch(new URL("/api/file", url), { method: "POST", body: "{}" });
    assert.equal(denied.status, 403);
    const foreign = await fetch(new URL("/api/state", url), { headers: { Origin: "https://example.com" } });
    assert.equal(foreign.status, 403);
    await post(url, "/api/deploy", { app: "mine" });
    assert.ok(provider.prompts[0].includes(JSON.stringify(project)));
    assert.ok(provider.prompts[0].includes("hyb26-skill"));
    await provider.close();
    await assert.rejects(fetch(url));
});

test("editing, assets, optimistic conflicts, and live reload", async (t) => {
    const { provider, project } = await fixture(t);
    const { url } = await provider.open("edit", { app: "mine" });
    const fileUrl = new URL("/api/file?app=mine&path=__init__.py", url);
    const file = await fetch(fileUrl).then((r) => r.json());
    const abort = new AbortController();
    const stream = await fetch(new URL("/events", url), { signal: abort.signal });
    const reader = stream.body.getReader();
    await reader.read();
    try {
        await post(url, "/api/file", { app: "mine", path: "__init__.py", version: file.version, text: 'print("edited")\n' });
        const changed = await Promise.race([
            reader.read().then(({ value }) => Buffer.from(value).toString()),
            new Promise((_, reject) => { const timer = setTimeout(() => reject(new Error("No live reload")), 5000); timer.unref(); }),
        ]);
        assert.match(changed, /"type":"reload"/);
    } finally { abort.abort(); }
    const saved = join(project, "badge", "apps", "mine", "__init__.py");
    assert.equal(readFileSync(saved, "utf8"), 'print("edited")\n');
    await post(url, "/api/file", { app: "mine", path: "__init__.py", version: file.version, text: "stale draft" }, 409);
    assert.equal(readFileSync(saved, "utf8"), 'print("edited")\n');
    await post(url, "/api/file", { app: "mine", path: "lib/helper.py", version: null, text: "answer = 42\n" });
    assert.equal(readFileSync(join(project, "badge", "apps", "mine", "lib", "helper.py"), "utf8"), "answer = 42\n");
    const png = readFileSync(join(root, "assets", "preview.png"));
    await post(url, "/api/file", { app: "mine", path: "assets/custom.png", version: null, data: png.toString("base64") });
    const asset = await fetch(new URL("/api/file?app=mine&path=assets/custom.png", url)).then((r) => r.json());
    assert.equal(asset.text, null);
    assert.ok(asset.image.startsWith("data:image/png;base64,"));
    await post(url, "/api/file", { app: "mine", path: "assets/custom.png", version: null, data: png.toString("base64") }, 409);
});

test("file writes reject traversal, secrets, oversized data, and external links", async (t) => {
    const { provider, project, temp } = await fixture(t);
    const { url } = await provider.open("paths", { app: "mine" });
    for (const path of ["../outside.py", "/absolute.py", "C:\\outside.py", "lib/../../outside.py", ".env", "secrets.py", "lib/SECRETS.py", "NUL.py"]) {
        await post(url, "/api/file", { app: "mine", path, text: "no", version: null }, 400);
    }
    assert.throws(() => saveAppFile(project, { app: "mine", path: "big.txt", text: "x".repeat(MAX_FILE_BYTES + 1), version: null }), /4 MiB/);
    const outside = join(temp, "Outside");
    mkdirSync(outside);
    const link = join(project, "badge", "apps", "mine", "linked");
    try { symlinkSync(outside, link, process.platform === "win32" ? "junction" : "dir"); }
    catch (error) { if (error.code === "EPERM") return; throw error; }
    await post(url, "/api/file", { app: "mine", path: "linked/outside.py", text: "no", version: null }, 403);
    assert.ok(!existsSync(join(outside, "outside.py")));
});

test("a blank workspace can create and run its own scaffold without modifying the plugin", async (t) => {
    const { provider, project, installed } = await fixture(t, true);
    const { url } = await provider.open("new");
    assert.equal((await fetch(new URL("/api/app", url))).status, 204);
    await post(url, "/api/create", { app: "my_app" }, 201);
    const checks = await provider.action("new", "check_app");
    assert.equal(checks.ok, true, JSON.stringify(checks.errors));
    assert.deepEqual(Array.from(checks.warnings), []);
    assert.ok(existsSync(join(project, "badge", "apps", "my_app", "icon.png")));
    assert.ok(!existsSync(join(installed, "badge")));
    await post(url, "/api/create", { app: "my_app" }, 409);
    await post(url, "/api/create", { app: "../escape" }, 400);
    const other = join(project, "Other Project");
    mkdirSync(other);
    await assert.rejects(provider.open("new", { project_root: other }), /another project/);
    const fresh = await provider.open("other", { project_root: other });
    const state = await fetch(new URL("/api/state", fresh.url)).then((r) => r.json());
    assert.equal(state.app, null, "Selection belongs to a project, not the plugin cache");
});
