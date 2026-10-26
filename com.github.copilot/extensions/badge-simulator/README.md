# Badge Simulator canvas

A [GitHub Copilot app](https://docs.github.com/copilot) canvas that runs a
Universe 2026 app from `badge/apps/<app>` on the 3D badge simulator from
[badger.github.io](https://badger.github.io). It ships in the repository's
[Agent Plugin](../../../README.md#agent-plugin), and a thin project loader
also makes it available to anyone working in this checkout. Both use this
implementation; only the 2026 simulator is registered.

- **Live reload**: the canvas watches `badge/apps/<app>` and reruns the app
  whenever a file changes, so it always shows the latest code.
- **Workspace editor**: create a starter app with **New app**, edit Python or
  text files, add modules with **New file**, and upload images with **Add asset**.
  **Save** (Ctrl/Cmd+S) writes to `badge/apps/` and reloads the running app.
  Unsaved changes are marked with `*`; external changes preserve the draft
  and stale saves fail with a conflict. **Reload file** explicitly discards a
  draft after confirmation. Binary assets show a preview or file information;
  replacing an existing asset is opt-in and version-checked.
- **Badge controls**: zoom (+/−), **Screen**/**Full** views (starts in
  Full) and **Rotate** to turn the badge upside down. You can click the 3D
  buttons, use the on-screen keys, or use the keyboard (arrows, Space/Enter =
  Select, Esc = Home, WASD/J/K/U for the gamepad).
- **Deploy**: asks Copilot to install the selected app on a badge connected
  over USB. It always uses USB mass-storage mode (entered over serial, so no
  button presses are needed) and follows "Installing an app" in
  [`hardware/USB_SERIAL.md`](../../../hardware/USB_SERIAL.md), including
  copying the patched menu `app.py` if the badge's menu doesn't show app
  `icon.png` files yet, plus [`badge/AGENTS.md`](../../../badge/AGENTS.md).
  It finishes by rebooting the badge so it leaves mass-storage, REPL and test
  modes and returns to the menu.
- **Theme**: follows the Copilot app's light or dark theme.
- **HOME** runs the app's `on_exit` and restarts it, because there is no menu.
- **Output** shows `print()` output and tracebacks from MicroPython.

## Using it

Ask Copilot to "open the Badge Simulator for flappy_mona", or have the agent
call `open_canvas` with `canvasId: "badge-simulator"` and
`input: { "app": "<folder under badge/apps>" }`. You can also choose an app
from the drop-down in the canvas.

Apps are read from the **session's working project**, not the extension or
plugin installation. The canvas searches the working directory and its
ancestors for `badge/apps/`. Pass
`input: { "app": "my_app", "project_root": "<absolute project directory>" }`
to choose another project explicitly. In a blank workspace, **New app**
creates the first `badge/apps/<name>` with a starter program, icon and README.
It reuses the bundled Python scaffolder, so Python 3.10+ must be on PATH
(`python` on Windows; `python3` on macOS/Linux).
A panel stays attached to its project; use a new `instanceId`
for a different project.

The **Editor** toggle gives the preview the full panel when you are playing.
Typing in the editor does not press badge buttons. Files are limited to 4 MiB
each. Hidden files, `secrets.py`, bytecode, traversal paths, and links outside
the project are excluded. The editor writes only inside the selected app;
it does not expose an arbitrary filesystem editor or delete existing files.

The repository's Copilot instructions make the simulator the default: when
you ask Copilot to build, run or deploy an app, it opens the app here first,
checks it, and reminds you to press **Deploy** when you're ready to install it
on your badge.

The agent can drive the canvas with `invoke_canvas_action`:

| Action | Input | Purpose |
| --- | --- | --- |
| `load_app` | `{ "app": "snake" }` | Switch to another app |
| `reload` | `{ "restart_runtime"?: true }` | Rerun now (normally automatic) |
| `get_output` | `{ "lines"?: 80, "since"?: cursor }` | Status (running, crashed, fps, frames, resolution, orientation, backlight), recent output and the last error mapped to `badge/apps/...:line` |
| `press` | `{ "button": "select", "duration_ms"?: 120 }` | Press `up`, `down`, `left`, `right`, `select`, `home`, `back`, `menu` (or `a`/`b`/`c`); combine with `"a+b"` |
| `screenshot` | `{ "label"?: "title" }` | Save the badge screen as a PNG and return its path |
| `exec` | `{ "code": "score", "timeout_ms"?: 5000 }` | Run MicroPython in the running app's globals (a REPL); expressions return their repr |
| `wait_for` | `{ "pattern"?: "regex", "frames"?: 30, "until_crash"?: true, "timeout_ms"?: 5000, "since"?: cursor }` | Wait for output, rendered frames or a crash instead of sleeping |
| `run_script` | `{ "steps": [...], "restart"?: true }` | Scripted test: `press`, `wait_ms`, `screenshot`, `exec`, `wait_for` and `rotate` steps, stopping on a crash |
| `rotate` | `{ "upside_down"?: true }` | Turn the badge upside down (or toggle) |
| `check_app` | `{ "app"?: "snake" }` | Pre-flight checks: `__init__.py`, 24x24 `icon.png`, README rules from CI, 2025 API usage and committed secrets |

A good debugging loop is `check_app`, then `run_script` (or `wait_for`) to
exercise the app, then `error.location` from the result to find the failing
line, fix it, and repeat; the canvas reloads on save. Keep the canvas visible
while testing: a hidden panel pauses the simulator.

The simulator approximates the badge firmware, so test on real hardware before
you open a pull request.

## How it works

`extension.mjs` starts a loopback HTTP server for each canvas. The server
hosts `web/`, sends the app's files to the page, and pushes reload events when
they change. `workspace.mjs` handles contained, version-checked writes and
reuses the packaged scaffolder for new apps. The editor (`web/editor.js`) is a
plain ES module; it does not need rebuilding. The page (`web/simulator.js`)
runs the badge's MicroPython WASM runtime in a web worker and draws frames
on the 3D model.

The runtime (about 6 MB: WASM, simulator filesystem and badge model) is
downloaded from the badger.github.io revision in `web/BUILD_INFO.json` the
first time you open the canvas. It is cached in
`~/.copilot/cache/badge-simulator/<revision>/` (or under `$COPILOT_HOME`), so
the canvas works offline after that.

## Updating the simulator

`web/simulator.js` is generated. Edit `src/entry.ts`, `web/index.html` or
`web/simulator.css`, then rebuild against the site's simulator modules:

```bash
node com.github.copilot/extensions/badge-simulator/build.mjs            # latest main
node com.github.copilot/extensions/badge-simulator/build.mjs --ref <sha> # specific revision
```

The script clones `badger/badger.github.io`, installs its dependencies, bundles
`src/entry.ts` with esbuild and records the revision in `web/BUILD_INFO.json`,
which also selects the matching runtime. Pass `--site <checkout>` to reuse a
local clone. Reload extensions in Copilot (or restart the app) to pick up
changes to `extension.mjs`.
