# badger.github.io simulator

`badger/badger.github.io` hosts a browser simulator built on
`pimoroni/badgeware-web-simulator` with MicroPython compiled to WebAssembly.
Use it for quick layout and logic checks; always finish on a physical badge.

## Pages

- https://badger.github.io/editor: code editor plus a live 320x240 badge.
  Paste or open an app's `__init__.py` and assets and run it.
- https://badger.github.io/apps: app store and USB disk tools. In a
  Chromium-based browser it can open the mounted BADGER volume (choose the
  folder that contains `apps`) to install, update, or remove apps.
- https://badger.github.io/about-badge: boots the menu in the simulator.

## What it models

- 160x120 and HIRES 320x240 drawing with the 2026 globals and fonts.
- The six main buttons from the keyboard and on-screen controls.
- IMU from device motion on phones, otherwise an upright badge.
- Wi-Fi always "connected"; HTTP through browser fetch (subject to CORS).
- `powman.reset_into_msc()` shows a message instead of rebooting.

## What it does not prove

- No raw sockets: Camera, Copilot, and similar socket apps need hardware.
- Bluetooth is an inert stub; IR does nothing.
- Cannot load `.mpy` files; native/viper code is adapted, not real.
- Speed, memory, battery, display timing, touch feel, and real network
  failures differ from the RP2350.

`validate_app.py --target emulator` warns about some of these limits.
