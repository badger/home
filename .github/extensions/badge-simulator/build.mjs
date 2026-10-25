#!/usr/bin/env node
// Rebuilds the Badge Simulator canvas assets from badger/badger.github.io.
//
//   node .github/extensions/badge-simulator/build.mjs [--ref <git-ref>] [--site <checkout>]
//
// It bundles src/entry.ts with the site's simulator modules into
// web/simulator.js and records the site revision in web/BUILD_INFO.json. At
// runtime the extension downloads (and caches) the MicroPython WASM runtime,
// simulator filesystem and 3D model from that same revision, so the bundle and
// runtime never drift apart. Requires git, npm and network access.
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const here = dirname(fileURLToPath(import.meta.url));
const { values } = parseArgs({ options: { ref: { type: "string", default: "main" }, site: { type: "string" } } });

const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, stdio: ["ignore", "inherit", "inherit"] });
const capture = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, encoding: "utf8" }).trim();

let site = values.site;
let cleanup = false;
if (!site) {
    site = mkdtempSync(join(tmpdir(), "badge-simulator-site-"));
    cleanup = true;
    run("git", ["clone", "--quiet", "--filter=blob:none", "https://github.com/badger/badger.github.io.git", site]);
    run("git", ["checkout", "--quiet", values.ref], site);
}
try {
    if (!existsSync(join(site, "node_modules", "esbuild"))) run("npm", ["ci", "--no-audit", "--no-fund", "--ignore-scripts"], site);
    const revision = capture("git", ["rev-parse", "HEAD"], site);

    const esbuild = await import(pathToFileURL(join(site, "node_modules", "esbuild", "lib", "main.js")).href);
    await esbuild.build({
        entryPoints: [join(here, "src", "entry.ts")],
        outfile: join(here, "web", "simulator.js"),
        bundle: true,
        format: "esm",
        target: "es2022",
        minify: true,
        legalComments: "eof",
        alias: { "@site": join(site, "src") },
        nodePaths: [join(site, "node_modules")],
        define: { "import.meta.env": JSON.stringify({ BASE_URL: "/" }) },
        banner: { js: `// Built from badger/badger.github.io@${revision} by build.mjs. Do not edit.` },
        logLevel: "info",
    });

    writeFileSync(join(here, "web", "BUILD_INFO.json"), JSON.stringify({ source: "https://github.com/badger/badger.github.io", revision, builtAt: new Date().toISOString() }, null, 2) + "\n");
    process.stderr.write(`Built Badge Simulator from badger.github.io@${revision}\n`);
} finally {
    if (cleanup) rmSync(site, { recursive: true, force: true });
}
