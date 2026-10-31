# Badge Simulator canvas

A [GitHub Copilot app](https://docs.github.com/copilot) canvas that runs a
Universe 2026 app from `badge/apps/<app>` on the 3D badge simulator from
[badger.github.io](https://badger.github.io). It is a project extension, so
Copilot loads it automatically for anyone who clones this repository.

- **Live reload**: the canvas watches `badge/apps/<app>` and reruns the app
  whenever a file changes, so it always shows the latest code.
- **Badge controls**: zoom (+/−), **Screen**/**Full** views (starts in
  Full) and **Rotate** to turn the badge upside down. You can click the 3D
  buttons, use the on-screen keys, or use the keyboard (arrows, Space/Enter =
  Select, Esc = Home, WASD/J/K/U for the gamepad).
- **Motion**: drag the 3D badge to tilt it, and the running app's
  `badge.imu()` follows. Drag up or down to tip the badge back or forward
  (all the way up lays it flat, face up). Drag left or right to lean it. A
  small label shows the current tilt, and **Level** (or **Screen**/**Full**)
  puts it back upright. On a phone, the real motion sensor still works
  whenever the badge is level in the canvas. Agents use the `tilt` action.
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
| `record` | `{ "duration_ms"?: 3000, "fps"?: 15, "steps"?: [...], "restart"?: true, "video"?: true, "save_frames"?: true }` | Record the screen while optional `run_script` steps run. Writes an animated GIF, a labelled contact-sheet PNG of evenly spaced frames, and optionally MP4/WebM video and per-frame PNGs. Returns their paths, `distinct_frames` and `longest_static_ms` |
| `exec` | `{ "code": "score", "timeout_ms"?: 5000 }` | Run MicroPython in the running app's globals (a REPL); expressions return their repr |
| `wait_for` | `{ "pattern"?: "regex", "frames"?: 30, "until_crash"?: true, "timeout_ms"?: 5000, "since"?: cursor }` | Wait for output, rendered frames or a crash instead of sleeping |
| `run_script` | `{ "steps": [...], "restart"?: true }` | Scripted test: `press`, `wait_ms`, `screenshot`, `exec`, `wait_for`, `rotate` and `tilt` steps, stopping on a crash |
| `rotate` | `{ "upside_down"?: true }` | Turn the badge upside down (or toggle) |
| `tilt` | `{ "pitch"?: 30, "roll"?: -20, "duration_ms"?: 300 }` or `{ "preset": "flat" }` | Tilt the badge so `badge.imu()` reports that pose. `pitch` tips the top back (90 = flat, face up), `roll` leans right. Angles are absolute from upright. Returns the raw IMU values sent to the app |
| `check_app` | `{ "app"?: "snake" }` | Pre-flight checks: `__init__.py`, 24x24 `icon.png`, README rules from CI, 2025 API usage and committed secrets |

A good debugging loop is `check_app`, then `run_script` (or `wait_for`) to
exercise the app, then `error.location` from the result to find the failing
line, fix it, and repeat; the canvas reloads on save. To check motion or
animation, `record` the interaction and view the contact sheet; the GIF or
video is ready to attach to a pull request. Keep the canvas visible
while testing: a hidden panel pauses the simulator.

Only one `record` action can run per canvas at a time, including its optional
restart and export. An explicit `scale` must be an integer from 1 to 4.
Capture waits for a real app frame rather than recording the initial placeholder,
includes the latest screen when stopped, and excludes export time from its
reported capture duration and GIF timing.

The simulator approximates the badge firmware, so test on real hardware before
you open a pull request.

## How it works

`extension.mjs` starts a loopback HTTP server for each canvas. The server
hosts `web/`, sends the app's files to the page, and pushes reload events when
they change. The page (`web/simulator.js`) runs the badge's MicroPython WASM
runtime in a web worker and draws frames on the 3D model. Recordings stream
changed frames from the page to the extension, and `media.mjs` encodes the GIF
and PNGs without dependencies. Video comes from the browser's `MediaRecorder`.
Screenshots and recordings are written to the session's
`files/badge-simulator/` folder.

The runtime (about 6 MB: WASM, simulator filesystem and badge model) is
downloaded from the badger.github.io revision in `web/BUILD_INFO.json` the
first time you open the canvas. It is cached in
`~/.copilot/cache/badge-simulator/<revision>/` (or under `$COPILOT_HOME`), so
the canvas works offline after that.

## Updating the simulator

`web/simulator.js` is generated. Edit `src/entry.ts`, `web/index.html` or
`web/simulator.css`, then rebuild against the site's simulator modules:

```bash
node .github/extensions/badge-simulator/build.mjs            # latest main
node .github/extensions/badge-simulator/build.mjs --ref <sha> # specific revision
```

The script clones `badger/badger.github.io`, installs its dependencies, bundles
`src/entry.ts` with esbuild and records the revision in `web/BUILD_INFO.json`,
which also selects the matching runtime. Pass `--site <checkout>` to reuse a
local clone. Reload extensions in Copilot (or restart the app) to pick up
changes to `extension.mjs`.

Run the dependency-free recording regression tests with Node.js 24 or newer:

```powershell
node --test .github\extensions\badge-simulator\recording.test.mjs
```
