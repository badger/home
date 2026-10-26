# Sources and how to resolve disagreements

## Source order

1. **The user's badge.** Its installed firmware and `/system` tree decide what
   actually runs. Read files over USB serial (`mpremote connect PORT fs cat
   :/system/apps/menu/app.py`) or from the mounted BADGER volume. Do not read,
   copy, or print `secrets.py` or personal saved data.
2. **`badger/home`** (https://github.com/badger/home), the source for the
   2026 badge firmware apps:
   - `badge/AGENTS.md`: app structure, runtime globals, lifecycle, input,
     timing, graphics, state, and porting rules.
   - `hardware/USB_SERIAL.md`: tested `mpremote`, REPL, filesystem, and
     install workflow.
   - `hardware/README.md` and the schematic: pins, buses, power, IR, touch.
   - `badge/apps/`: reference apps (see [examples.md](examples.md)).
   - `.github/scripts/validate_app_readmes.py`: the README rule.
3. **`badger/badger.github.io`** (https://badger.github.io): the browser
   simulator at `/editor`, the app store and USB disk tools at `/apps`, and
   the menu demo at `/about-badge`. See [simulator.md](simulator.md).
4. Upstream Pimoroni projects (`pimoroni/tufty2350`, `pimoroni/badgeware-docs`,
   `pimoroni/badgeware-web-simulator`) for shared platform details only. They
   do not model the 2026 badge's custom wiring, touch controls, or IR.

A newer repository commit does not prove the badge runs that code; event
firmware can lag `badger/home`. When they disagree, describe the difference
and prefer what the badge actually does. Known example: the stock event firmware
menu ignores app `icon.png` files; see [menu-icons.md](menu-icons.md).

## Do not use

- `badge25/` and its simulator or `badgerware/` docs: Universe 2025 API.
- Stock Tufty 2350 wiring for touch, IMU, IR, or expansion pins.
- Code that imports `badge`, `io`, `PixelFont`, `Image`, `brushes`, or
  `shapes` from `badgeware` (2025 API) without translating it.

Static validation is not an API allow-list or a runtime guarantee. If an API is
not demonstrated in `badger/home` or confirmed on the badge's REPL, say so
instead of inventing behavior.
