import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import vm from "node:vm";

// Exercise the real provider without starting another agent or requiring an SDK install.
export async function loadProvider(entry, cwd, artifacts, cacheHome) {
    let declaration;
    const prompts = [];
    const context = vm.createContext({
        Buffer, URL, fetch, setTimeout, clearTimeout, setInterval, clearInterval,
        process: { env: { COPILOT_HOME: cacheHome }, pid: process.pid, cwd: () => cwd },
    });
    const module = new vm.SourceTextModule(readFileSync(entry, "utf8"), {
        context,
        identifier: pathToFileURL(entry).href,
        initializeImportMeta: (meta) => { meta.url = pathToFileURL(entry).href; },
    });
    await module.link(async (specifier, parent) => {
        const exports = specifier === "@github/copilot-sdk/extension" ? {
            createCanvas: (value) => value,
            joinSession: async (config) => {
                declaration = config.canvases[0];
                return {
                    workspacePath: artifacts,
                    send: async (message) => { prompts.push(message.prompt); },
                    log: () => {},
                };
            },
        } : await import(specifier.startsWith(".") ? new URL(specifier, parent.identifier).href : specifier);
        const names = Object.keys(exports);
        return new vm.SyntheticModule(names, function () {
            for (const name of names) this.setExport(name, exports[name]);
        }, { context });
    });
    await module.evaluate();
    const panels = new Set();
    return {
        canvas: declaration, prompts,
        open: async (instanceId, input = {}) => {
            panels.add(instanceId);
            return declaration.open({ instanceId, input });
        },
        action: (instanceId, name, input = {}) => declaration.actions.find((action) => action.name === name).handler({ instanceId, input }),
        close: async () => {
            for (const instanceId of panels) await declaration.onClose({ instanceId });
            panels.clear();
        },
    };
}
