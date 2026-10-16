---
name: hyb26-skill
description: Build, debug, validate, and deploy Universe 2026 badge apps using verified firmware examples, safe copying, and physical hardware checks. Explain current custom menu icon limits.
compatibility: Requires Python 3.10+ for bundled tools. Physical deployment requires a mounted BADGER USB volume. Advanced API verification may require GitHub access.
license: MIT
metadata:
  summary: Turn an app idea into a checked Universe 2026 badge app.
  status: active
---

# HYB26-skill

Help the user create an app for the GitHub Universe 2026 badge. Use plain
language. Both host editions provide the same badge features; only computer
setup and commands differ. The current event firmware is the target.

## Custom app menu icons are not supported yet

**Changing `icon.png` will not change the icon on the current event badge menu.**
The menu uses built-in icons selected by app folder name, with a generic icon
for new names. Explain this before doing work for a custom menu icon request.
Do not promise an icon upload, rename an app to borrow another icon, or change
the badge menu or firmware as a workaround.

The starter tool still makes a 24x24 `icon.png` for previews. It is optional,
not proof of menu integration. Graphics and images drawn inside an app remain
supported. Older firmware and repository examples can behave differently;
follow the version-specific evidence in [references/sources.md](references/sources.md).

## Host commands

<!-- platform:start -->
On Windows, use PowerShell and `python`. Open the user's badge project folder
first. It can be an ordinary folder; Git is not required. For a personal install:

```powershell
$scripts = "$HOME\.copilot\skills\hyb26-skill\scripts"
python "$scripts\scaffold_app.py" my-app --title "My App"
python "$scripts\validate_app.py" "badge\apps\my-app"
python "$scripts\inventory_badge_apps.py" --mount "E:\"
python "$scripts\deploy_app.py" "badge\apps\my-app"
python "$scripts\deploy_app.py" "badge\apps\my-app" --write
python "$scripts\deploy_app.py" "badge\apps\my-app" --write --replace
```

For a repository-local install, set `$scripts = ".github\skills\hyb26-skill\scripts"`.
For an unpacked skill, use its actual scripts folder. Replace `E:\` with the
real BADGER drive letter in File Explorer. Eject BADGER in File Explorer and
wait for confirmation before pressing RESET once.
<!-- platform:end -->

The deploy command previews by default. Only use `--write` after reviewing
the file list. Use `--replace` only for an intended update; it keeps a backup.
For a personal or unpacked install, tools use the current project folder.
Repository-local tools use their containing repository. Use `--repo-root`
with validation/deployment or `--apps-dir` with app creation to choose another
project explicitly. Never use the installed skill folder as the app project.

## Start with evidence

1. Read [references/capabilities.md](references/capabilities.md) to classify
   the request and identify checks that require hardware.
2. Read [references/app-contract.md](references/app-contract.md) and the relevant
   sections of [references/badgeware-api.md](references/badgeware-api.md).
3. Select a small pattern from [references/patterns.md](references/patterns.md)
   and an example from [references/examples.md](references/examples.md).
4. Prefer readable source from the target badge, as described in
   [references/device-app-inventory.md](references/device-app-inventory.md).
   Refresh its file list with the inventory command when a badge is available.
5. Consult [references/sources.md](references/sources.md) before resolving
   disagreements. `badger/home` and `badger/badgerfactory` can lag the event
   firmware or contain legacy examples. Do not copy their APIs blindly.
6. Verify missing or changed APIs in matching first-party source. If no matching
   evidence is available, state the uncertainty instead of inventing behavior.

## Design and build

Reduce the request to screens/states, controls, assets, saved data, timing,
memory needs, and feature-specific acceptance checks. Include networking,
Bluetooth, IR, motion, lights, battery, or expansion hardware only as needed.
Ask about assumptions that would change the requested behavior substantially.

Create apps under `badge/apps/<app-name>/`. Use lowercase path-safe folder
names and the requested title inside the app. Then:

1. Use the U26 runtime globals and verified imports, not legacy 2025 APIs.
2. Define `update()` and call `run(update)` at module level, not behind a
   `__main__` guard. Keep frames short and use `badge.ticks`/`badge.ticks_delta`.
3. Use logical UP, DOWN, LEFT, RIGHT, SELECT, BACK, and MENU actions. HOME
   belongs to the launcher.
4. Use `screen.width` and `screen.height`; most simple apps use 160x120,
   but verified apps can request HIRES. Do not reject HIRES automatically.
5. Keep app assets relative to the app. Use `/system/...` only for intentional
   shared system files. Do not add desktop dependencies to badge code.
6. Bound images, lists, queues, cached responses, and per-frame work.
7. Load small saved values with `State`, then validate their types and ranges.
   Save after meaningful changes and check persistence on the badge.
8. Filter motion readings and use thresholds and cooldowns. Keep Bluetooth
   interrupt handlers minimal and process queued messages in `update()`.
9. Never embed credentials or deploy `secrets.py`. Do not rewrite unrelated
   apps, menu files, or system configuration.

## Validate and deploy

Run the validator and resolve its errors. The default target is `hardware`.
`--target emulator` and `--target both` add static compatibility warnings;
they do not run a simulator or supply missing badge APIs.

The validator checks selected syntax, imports, callbacks, paths, and PNGs.
It does not prove every API, drawing result, memory limit, timing, or hardware
feature works. Add focused mock behavior checks when practical. A desktop
preview is not physical badge proof; the archived 2025 simulator is not a U26
compatibility test.

Put the badge in USB Disk Mode, identify BADGER, preview the selected app,
then copy it. Never copy apps to the RP2350 firmware drive. Both `BADGER/apps`
and `BADGER/system/apps` are supported; stop and resolve ambiguous layouts.
Follow [references/physical-badge.md](references/physical-badge.md) for backups,
safe eject, reset, tests, and recovery boundaries.

## Definition of done

Report which checks actually ran: file validation, focused behavior checks,
deployment, and physical feature checks. If no badge is available, give a
concrete hardware checklist and say that physical verification is incomplete.
Never call an app hardware-verified because static checks passed. Explain any
unverified API, firmware assumption, or custom-icon limitation that affects
the result.
