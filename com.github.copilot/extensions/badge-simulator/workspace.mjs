import { createHash, randomUUID } from "node:crypto";
import { execFile } from "node:child_process";
import { existsSync, lstatSync, mkdirSync, readFileSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, extname, isAbsolute, join, relative, sep } from "node:path";
import { promisify } from "node:util";
import { isUtf8 } from "node:buffer";

export const MAX_FILE_BYTES = 4 * 1024 * 1024;
const textExtensions = new Set([".py", ".md", ".txt", ".json", ".csv", ".toml", ".ini", ".yaml", ".yml", ".cfg"]);
const imageTypes = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp" };
const versionOf = (bytes) => createHash("sha256").update(bytes).digest("hex");
const fail = (status, message) => { throw Object.assign(new Error(message), { status }); };
const inside = (root, path) => {
    const rel = relative(root, path);
    return rel === "" || (!isAbsolute(rel) && rel !== ".." && !rel.startsWith(".." + sep));
};

export function allowedFile(name) {
    return !name.startsWith(".") && name !== "__pycache__" && !/^(secrets\.py)$/i.test(name) && !/\.py[co]$/i.test(name);
}

function safeSegments(path) {
    if (typeof path !== "string" || !path || path.length > 240) fail(400, "Provide a relative file path of at most 240 characters.");
    const segments = path.split("/");
    if (segments.some((part) => !part || !allowedFile(part) || /[\\<>:"|?*\x00-\x1f]/.test(part)
        || /[. ]$/.test(part) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part))) {
        fail(400, "Use a relative app path without hidden files, secrets.py, parent traversal, or reserved filenames.");
    }
    return segments;
}

function ensureContained(root, path) {
    let parent = path;
    while (!existsSync(parent)) parent = dirname(parent);
    if (!inside(realpathSync(root), realpathSync(parent))) fail(403, "Linked paths must stay inside the app project.");
    if (existsSync(path) && lstatSync(path).isSymbolicLink()) fail(403, "Cannot edit linked files or directories.");
}

export function appDirectory(root, app) {
    if (typeof app !== "string" || !/^[a-zA-Z0-9_-]+$/.test(app)) fail(400, "Invalid app name.");
    const dir = join(root, "badge", "apps", app);
    ensureContained(root, dir);
    if (!existsSync(join(dir, "__init__.py"))) fail(404, `App "${app}" does not exist.`);
    return dir;
}

function filePath(root, app, path) {
    const dir = appDirectory(root, app);
    const file = join(dir, ...safeSegments(path));
    ensureContained(dir, file);
    return file;
}

export function readAppFile(root, app, path) {
    const file = filePath(root, app, path);
    if (!existsSync(file) || !statSync(file).isFile()) fail(404, "File not found.");
    if (statSync(file).size > MAX_FILE_BYTES) fail(413, "The editor supports files up to 4 MiB.");
    const bytes = readFileSync(file);
    const editable = textExtensions.has(extname(file).toLowerCase()) && !bytes.includes(0) && isUtf8(bytes);
    const mime = imageTypes[extname(file).toLowerCase()] ?? null;
    return {
        app, path, size: bytes.length, version: versionOf(bytes),
        text: editable ? bytes.toString("utf8") : null,
        image: mime ? `data:${mime};base64,${bytes.toString("base64")}` : null,
    };
}

export function saveAppFile(root, { app, path, text, data, version }) {
    const file = filePath(root, app, path);
    if (version !== null && typeof version !== "string") fail(400, "Pass the file version, or null to create a new file.");
    if (existsSync(file) && !statSync(file).isFile()) fail(400, "The path is not a regular file.");
    if (existsSync(file) && statSync(file).size > MAX_FILE_BYTES) fail(413, "The editor supports files up to 4 MiB.");
    const previous = existsSync(file) ? versionOf(readFileSync(file)) : null;
    if (version !== previous) fail(409, "This file changed on disk. Your draft is preserved; reload the file before saving again.");
    if ((typeof text === "string") === (typeof data === "string")) fail(400, "Provide either text or base64 file data.");
    if (typeof text === "string" && !textExtensions.has(extname(file).toLowerCase())) fail(400, "This file type must be uploaded as an asset.");
    if (typeof data === "string" && !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(data)) fail(400, "Invalid base64 file data.");
    const bytes = typeof text === "string" ? Buffer.from(text, "utf8") : Buffer.from(data, "base64");
    if (bytes.length > MAX_FILE_BYTES) fail(413, "The editor supports files up to 4 MiB.");
    mkdirSync(dirname(file), { recursive: true });
    const temporary = join(dirname(file), `.badge-editor-${randomUUID()}.tmp`);
    try {
        writeFileSync(temporary, bytes, { flag: "wx" });
        renameSync(temporary, file);
    } finally {
        rmSync(temporary, { force: true });
    }
    return { app, path, version: versionOf(bytes), size: bytes.length };
}

export async function createApp(root, app, script) {
    if (typeof app !== "string" || !/^[a-z][a-z0-9_-]{0,63}$/.test(app) || ["menu", "startup"].includes(app)) {
        fail(400, "Use a lowercase app name starting with a letter (up to 64 letters, numbers, hyphens or underscores); menu and startup are reserved.");
    }
    const apps = join(root, "badge", "apps");
    ensureContained(root, apps);
    const target = join(apps, app);
    if (existsSync(target)) fail(409, `App "${app}" already exists; choose another name.`);
    const candidates = process.platform === "win32" ? ["python", "python3"] : ["python3", "python"];
    for (const command of candidates) {
        try {
            await promisify(execFile)(command, ["-B", script, app, "--apps-dir", apps], { cwd: root, timeout: 15000, windowsHide: true });
            return { app };
        } catch (error) {
            if (error.code === "ENOENT") continue;
            fail(500, `Could not create app: ${error.stderr || error.message}`);
        }
    }
    fail(500, "Creating an app requires Python 3.10+ on PATH. Install Python and try again.");
}
