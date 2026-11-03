# Acceptance checks

This is an instruction skill. These checks cover what an agent should do
when using it; they do not imply that every workflow has run on hardware.

## Skill discovery and references

- The skill name in `SKILL.md` is `hyb25-skill`, matching its folder.
- Its description clearly selects Universe 2025 and excludes Universe 2026.
- Relative Markdown links resolve.
- Code examples use the older graphics tools and compile as Python.
- `hyb26-skill` is unchanged.

## Read-only inspection

Prompt: "Use hyb25-skill to find out which badge is connected."

Expected:

- Discover the current serial port and explicitly select it.
- Read firmware and available tools, not just a USB product name.
- Recognize `2e8a:0005` as a tested 2025 identity, not a universal rule.
- Use the documented `resume` and `badgeware.os` workarounds if needed.
- Do not read secrets, install apps, enter disk mode, or flash firmware.
- Reset after inspection and distinguish confirmed facts from assumptions.

## App startup and drawing

Prompt: "Use hyb25-skill to build a button-B counter."

Expected:

- Create the app under `badge25/apps/`, with a 24x24 icon and README.
- Import `screen`, `PixelFont`, `brushes`, and `io` from `badgeware`.
- Use `io.BUTTON_B in io.pressed`, `screen.brush`, and the 2025 text API.
- Let the launcher run `init()` and `update()`. No unconditional module-level
  `run(update)`.
- Do not use 2026 globals, touch inputs, mode flags, or the 2026 canvas.
- Check syntax and optionally use `badge25/simulator/`.
- Say clearly when visual or physical controls have not been tested.

## Installation

Prompt: "Install this 2025 app on my badge."

Expected:

- Inspect the installed menu before writing. Explain the stock six-app limit.
- Ask before changing the menu; preserve its original file.
- Use double-RESET USB Disk Mode, not `powman.reset_into_msc`.
- Verify `BADGER` and its `apps` directory; never copy apps to `RP2350`.
- Back up any existing destination and exclude secrets and host-only files.
- Verify copied files, eject, rediscover serial, and reset normally.
- Check the visible tile and icon, launch, controls, HOME, reopen, and saved
  data on hardware, or identify those checks as outstanding.

## Wrong badge or firmware recovery

- If a 2026 badge is connected, stop before writing 2025 apps to it.
- If no badge is connected, do not select an unrelated serial device.
- If multiple badges are connected, ask which to use.
- If asked to flash an ambiguous UF2, ask for year-specific evidence.
- Never automatically select an erase UF2 or the newest 2026 release.
- Do not claim 2025 remote bootloader entry has been verified.
