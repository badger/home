import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

// Keep the optional marketplace validator outside the runtime extension's dependencies.
const modulePath = process.argv[2];
if (!modulePath) throw new Error("Pass the installed @microsoft/vally/dist/index.js path.");
const { runLint, LintConsoleReporter } = await import(pathToFileURL(resolve(modulePath)).href);
for (const skill of ["hyb26-skill", "badge-simulator"]) {
    const result = await runLint({ rootPath: join(process.cwd(), "skills", skill) });
    await new LintConsoleReporter({ verbose: true }).report(result);
    if (!result.passed) process.exitCode = 1;
}
