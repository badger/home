# HYB26-skill

A Copilot skill for building, testing, and installing apps on the GitHub
Universe 2026 badge. It works on macOS, Linux, and Windows.

## What it helps with

- Turning an idea into an app under `badge/apps/<name>` with `__init__.py`,
  `icon.png`, and a `README.md` that passes the repository's README check.
- Using the 2026 firmware API, reference apps, and hardware notes from
  `badger/home`.
- Talking to the badge with `mpremote`: REPL, running code, reading files.
- Switching the badge into USB Disk Mode from the computer and copying one app
  safely (dry run first, backups on replace, `secrets.py` never copied).
- Patching a stock badge menu so apps show their own `icon.png`
  ([Gadgetoid's patch](https://gist.github.com/Gadgetoid/f72b85e6efe603bd02b2b730bbc40356)).
- Quick checks in the [badger.github.io simulator](https://badger.github.io/editor),
  followed by testing on a real badge.

## Use it in this repository

Copilot discovers skills in `.github/skills/` automatically. Open a session in
a `badger/home` checkout and ask, for example:

> Use hyb26-skill to make a dice app and install it on my badge.

## Install it for your own projects

Requires Python 3.10+. From this folder:

```bash
sh ./install-skill.sh            # macOS / Linux
```

```powershell
.\install-skill.ps1              # Windows PowerShell
```

This copies the skill to `~/.copilot/skills/hyb26-skill` without deleting
unrelated files there. Rerun it to update. Check with `copilot skill list`, and
use `/skills reload` in an open session. For other Copilot clients, check
their documented skill locations. See [INSTALL.txt](INSTALL.txt).

## Tools

| Script | Purpose |
| --- | --- |
| `scaffold_app.py` | Create a starter app with icon and README |
| `validate_app.py` | Static checks: syntax, imports, lifecycle, assets, icon, README |
| `badge_serial.py` | Find the badge port, show info, open the REPL, enter USB Disk Mode |
| `deploy_app.py` | Copy one app to the BADGER volume (dry run by default) |
| `patch_menu_icons.py` | Let the badge menu show app `icon.png` files (dry run by default) |
| `inventory_badge_apps.py` | List readable app files on a mounted badge |

Commands for each host are in [SKILL.md](SKILL.md).

## Maintenance

Run `python3 -m unittest discover -s tests -v` from this folder after
changes. [TEST.md](TEST.md) lists prompts for checking the assistant's
behavior. Keep the skill aligned with `badge/AGENTS.md` and
`hardware/USB_SERIAL.md`.
