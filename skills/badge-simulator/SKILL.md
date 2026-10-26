---
name: badge-simulator
description: Run, test, and debug GitHub Universe 2026 badge apps in the Copilot Badge Simulator canvas. Use for simulator previews, scripted input, live MicroPython inspection, tracebacks, and screenshots.
---

# Badge Simulator

Use only the **2026** canvas, `badge-simulator`. The preserved `badge25/`
simulator is not compatible with the 2026 firmware APIs.

## Project and capabilities

Apps belong to the user's workspace at `badge/apps/<name>/`, not the plugin
installation. Each needs `__init__.py`, a 24x24 `icon.png`, and a README whose
first paragraph is a one-sentence description. Use the companion
`hyb26-skill` to scaffold or fix an app, or click **New app** in the canvas.

The canvas is a **Copilot-specific extension**, not part of the portable Agent
Plugins core. If the client has no canvas support, say so and use the browser
simulator at <https://badger.github.io/editor>; do not pretend canvas tools exist.

## Preview and debug

1. Discover the schema with `list_canvas_capabilities` for `badge-simulator`.
2. Open it with `open_canvas`, a stable caller-chosen `instanceId`, and
   `input: {"app":"<name>"}`. Omit `app` to start in a blank workspace and use
   **New app** (Python 3.10+ is required for the bundled scaffolder).
   It finds `badge/apps` in the session's working
   directory or its ancestors. For another project, add
   `"project_root":"<absolute project directory>"` to the input.
3. Call `check_app`, then `wait_for` with `frames` and `timeout_ms` to confirm
   the app actually renders. Keep the canvas visible; hidden panels pause it.
4. Exercise controls using `run_script`. For example:
   `{"steps":[{"press":"select"},{"wait_for":{"frames":30}},{"exec":"(screen.width, screen.height)"},{"screenshot":"after-select"}]}`.
5. Inspect `get_output` for `crashed`, `error.location`, output, and frame
   statistics. Read screenshot files using the image/file viewing tool.
6. Fix failures in the user's app and repeat. Files reload automatically;
   `reload` with `restart_runtime:true` also resets the MicroPython runtime.

Actions use `invoke_canvas_action` with the **instanceId**, not the canvasId.
Buttons are `up`, `down`, `left`, `right`, `select`, `back`, `menu`, `home`;
combine them with `+`. HOME calls `on_exit` and restarts the app, not a menu.
`rotate` tests upside-down input. `exec` inspects live app globals.
Discover the full action reference through `list_canvas_capabilities`.

## Editing in the canvas

The workspace editor is not limited to preinstalled apps. Use **New file** for
Python modules or text, and **Add asset** to upload files (4 MiB maximum).
Images are previewed in the editor. To replace an icon or another existing
asset, specify its app-relative path and explicitly enable replacement.
Hidden files, `secrets.py`, and paths outside the app cannot be edited.

**Save** or Ctrl/Cmd+S writes to the workspace and reloads the simulator.
Unsaved text is marked with `*`. External updates preserve drafts, and a stale
save reports a conflict; **Reload file** discards a draft only after confirmation.
Use the **Editor** toggle to give the simulator the whole panel while playing.

## Deployment boundary

The simulator approximates firmware. It does not prove physical hardware,
networking, Bluetooth, IR, or camera behavior. Do not connect to a physical
badge merely to preview an app.

Finish an app preview by saying it is running in the Badge Simulator and that
the user can press **Deploy** when happy. A Deploy-button request authorizes
the hardware workflow in the companion `hyb26-skill`; use USB
mass-storage mode, preview copies, preserve backups, and reset to the menu.
