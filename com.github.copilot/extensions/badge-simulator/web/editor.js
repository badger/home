const $ = (selector) => document.querySelector(selector);
const source = $("[data-source]");
const files = $("[data-files]");
const save = $("[data-save]");
const appPicker = $("[data-app]");
const appDialog = $("[data-app-dialog]");
const fileDialog = $("[data-file-dialog]");
const uploadInput = $("[data-upload-input]");
const message = $("[data-editor-message]");
let app = null;
let path = null;
let version = null;
let savedText = "";
let editable = false;
let saving = false;
let pendingUpload = null;
let syncId = 0;
let readId = 0;
const dirty = () => editable && source.value !== savedText;
const headers = { "Content-Type": "application/json", "X-Badge-Simulator": "1" };

async function api(url, body) {
    const response = await fetch(url, body === undefined ? {} : { method: "POST", headers, body: JSON.stringify(body) });
    if (response.status === 204) return null;
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
    return result;
}
function report(text, error = false) {
    message.textContent = text;
    message.dataset.error = String(error);
}
function updateSave() {
    save.disabled = !dirty() || saving;
    $("[data-file-name]").textContent = path ? `${app}/${path}${dirty() ? " *" : ""}` : "No file selected";
}
function discardDraft() {
    if (saving) { report("Wait for the current save to finish.", true); return false; }
    return !dirty() || window.confirm("Discard the unsaved changes in this file?");
}
function showFile(file) {
    path = file.path;
    version = file.version;
    editable = file.text !== null;
    source.value = savedText = file.text ?? "";
    source.disabled = !editable;
    source.hidden = !editable;
    $("[data-asset-preview]").hidden = editable;
    $("[data-asset-image]").replaceChildren();
    if (file.image) {
        const image = document.createElement("img");
        image.src = file.image;
        image.alt = `App asset: ${file.path}`;
        $("[data-asset-image]").append(image);
    }
    $("[data-asset-info]").textContent = `${file.path} (${file.size.toLocaleString()} bytes)`;
    $("[data-reload-file]").disabled = false;
    files.value = path;
    updateSave();
}
async function openFile(nextPath) {
    const id = ++readId;
    const nextApp = app;
    source.disabled = true;
    try {
        const file = await api(`/api/file?app=${encodeURIComponent(nextApp)}&path=${encodeURIComponent(nextPath)}`);
        if (id !== readId || app !== nextApp) return;
        if (dirty()) return;
        showFile(file);
        report("Saves update the workspace and reload the simulator. Ctrl/Cmd+S to save.");
    } finally {
        if (id === readId) source.disabled = !editable;
    }
}
async function sync() {
    const id = ++syncId;
    try {
        const payload = await api("/api/app");
        if (id !== syncId) return;
        if (dirty()) {
            report("Workspace updated. Your unsaved draft is preserved; save to check for conflicts, or reload the file.", true);
            return;
        }
        const changedApp = app !== (payload?.app ?? null);
        app = payload?.app ?? null;
        if (changedApp) { path = null; readId++; }
        files.replaceChildren(...(payload?.files ?? []).map((file) => new Option(file.path, file.path)));
        $("[data-new-file]").disabled = !app;
        $("[data-upload]").disabled = !app;
        if (!app) {
            path = null;
            editable = false;
            source.value = savedText = "";
            source.disabled = true;
            source.hidden = false;
            $("[data-asset-preview]").hidden = true;
            $("[data-asset-image]").replaceChildren();
            $("[data-reload-file]").disabled = true;
            updateSave();
            report("Create an app to start building in this workspace.");
            return;
        }
        const next = [...files.options].some((option) => option.value === path) ? path : "__init__.py";
        await openFile(next);
    } catch (error) { report(error.message, true); }
}

source.addEventListener("input", updateSave);
source.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!save.disabled) save.click();
    } else if (event.key === "Tab" && !event.shiftKey) {
        event.preventDefault();
        source.setRangeText("    ", source.selectionStart, source.selectionEnd, "end");
        updateSave();
    }
});
save.addEventListener("click", async () => {
    const text = source.value;
    saving = true;
    updateSave();
    try {
        const result = await api("/api/file", { app, path, text, version });
        version = result.version;
        savedText = text;
        report("Saved to the workspace. Simulator reloading.");
    } catch (error) { report(error.message, true); }
    finally { saving = false; updateSave(); }
});
files.addEventListener("change", () => {
    const selected = files.value;
    if (!discardDraft()) { files.value = path ?? ""; return; }
    savedText = source.value;
    void openFile(selected).catch((error) => report(error.message, true));
});
$("[data-reload-file]").addEventListener("click", () => {
    if (!discardDraft()) return;
    savedText = source.value;
    void openFile(path).catch((error) => report(error.message, true));
});
appPicker.addEventListener("change", (event) => {
    if (!discardDraft()) {
        event.stopImmediatePropagation();
        appPicker.value = app ?? "";
    } else {
        savedText = source.value;
        readId++;
    }
}, true);
window.addEventListener("beforeunload", (event) => {
    if (!dirty()) return;
    event.preventDefault();
    event.returnValue = "";
});
$("[data-toggle-editor]").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const open = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(open));
    $("#sim").dataset.editor = open ? "open" : "closed";
    window.dispatchEvent(new Event("resize"));
});
for (const button of document.querySelectorAll("[data-cancel-dialog]")) {
    button.addEventListener("click", () => button.closest("dialog").close());
}
$("[data-new-app]").addEventListener("click", () => {
    if (!discardDraft()) return;
    $("[data-app-error]").textContent = "";
    appDialog.showModal();
});
$("[data-create-app]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.currentTarget.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
        await api("/api/create", { app: new FormData(event.currentTarget).get("app") });
        savedText = source.value;
        appDialog.close();
        await sync();
    } catch (error) { $("[data-app-error]").textContent = error.message; }
    finally { submit.disabled = false; }
});
function newFile(upload = null) {
    if (!discardDraft()) return;
    pendingUpload = upload;
    $("[data-file-error]").textContent = "";
    $("[data-file-dialog-title]").textContent = upload ? "Add asset" : "New file";
    $("[data-replace-option]").hidden = !upload;
    $("[data-create-file] [name=replace]").checked = false;
    $("[data-create-file] [name=path]").value = upload ? `assets/${upload.name}` : "helpers.py";
    fileDialog.showModal();
}
$("[data-new-file]").addEventListener("click", () => newFile());
$("[data-upload]").addEventListener("click", () => { uploadInput.value = ""; uploadInput.click(); });
uploadInput.addEventListener("change", () => {
    const file = uploadInput.files?.[0];
    if (file && file.size > 4 * 1024 * 1024) report("Assets must be 4 MiB or smaller.", true);
    else if (file) newFile(file);
});
$("[data-create-file]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.currentTarget.querySelector('[type="submit"]');
    const nextPath = new FormData(event.currentTarget).get("path");
    submit.disabled = true;
    try {
        let body = { app, path: nextPath, version: null, text: "" };
        if (pendingUpload) {
            const data = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result).split(",")[1]);
                reader.onerror = () => reject(new Error("Could not read the selected asset."));
                reader.readAsDataURL(pendingUpload);
            });
            body = { app, path: nextPath, version: null, data };
            if ($("[data-create-file] [name=replace]").checked) {
                const existing = await api(`/api/file?app=${encodeURIComponent(app)}&path=${encodeURIComponent(nextPath)}`);
                body.version = existing.version;
            }
        }
        await api("/api/file", body);
        savedText = source.value;
        path = nextPath;
        fileDialog.close();
        await sync();
    } catch (error) { $("[data-file-error]").textContent = error.message; }
    finally { submit.disabled = false; }
});
const events = new EventSource("/events");
events.onmessage = ({ data }) => {
    const event = JSON.parse(data);
    if (event.type === "reload" || event.type === "apps") void sync();
};
void sync();
