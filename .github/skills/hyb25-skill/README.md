# Universe 2025 badge skill

This skill helps Copilot build and install apps for the GitHub Universe 2025 badge without using incompatible 2026 tools.

Use `/hyb25-skill` in a Copilot session with this repository. For example:
"Use hyb25-skill to inspect my connected badge" or "Use hyb25-skill to make a
2025 badge counter controlled by button B."

The skill is instructions and references, not a new command-line toolkit.
It uses standard `mpremote` commands and the existing `badge25/` sources.
Physical access needs `mpremote` and a data-capable USB-C cable. The optional
2025 simulator needs Python 3.10+ and Pygame.

## Why it is separate

The older badge uses A/B/C buttons, imports its graphics from `badgeware`,
and lets its launcher start the app loop. Its stock menu does not discover
new apps automatically. The 2026 skill's badge detection, app template, and
menu patch do not fit this firmware.

The 2025 skill checks the connected firmware before writing, keeps apps under
`badge25/apps/`, and leaves the existing 2026 skill unchanged. It does not
automatically upgrade the menu or flash firmware.

## Evidence and limits

Read-only inspection on November 2, 2026 found:

- USB identity `2e8a:0005`, `GitHub Badger MicroPython`.
- Firmware `MicroPython v1.14-5485.gddae88e91.dirty on 2025-10-20`.
- A 160x120 drawing surface and the older Badgeware input and graphics tools.
- An installed launcher matching `badge25/main.py`'s startup sequence.
- A stock six-entry menu that loads each listed app's PNG icon, unlike the
  repo's updated, paginated 2025 menu.
- No `powman.reset_into_msc` export on that firmware.

These observations describe one firmware build, not every 2025 badge.
Detection must check the actual connected device. The USB guide records
the import and raw-REPL issues seen during inspection.

See [SKILL.md](SKILL.md), the [app contract](references/app-contract.md),
[USB guide](references/usb.md), and [acceptance checks](TEST.md).
