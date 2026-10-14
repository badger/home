# Camera (2026 firmware only)

Live Wi-Fi viewfinder and shutter for a diymore ESP32-CAM with OV2640.
Select takes a full-resolution photo on the camera SD card and freezes its
preview; Select again resumes live view. Up/Down browses the last 15 compact
photo copies stored on the badge.
The camera's white flash LED illuminates new full-resolution captures only;
it stays off during live preview and review.
Left/Right changes rotation in 90-degree steps; the setting persists and new
SD photos carry matching EXIF orientation metadata.

The new companion uses BLE for first-use pairing and Wi-Fi credential refresh.
Enter the camera's six-digit code from its SD card `PAIRING.TXT` or USB serial
output once. The app then maintains its private `/camera_config.json` itself.
Install all four Python files plus `icon.png`.

Hardware verification covers first-use BLE pairing, incorrect-code rejection,
automatic reconnection after camera restart, live preview, full-resolution SD
captures, frozen review, and the badge gallery. Pairing is application-level SRP,
not native Bluetooth bonding; its security design remains unaudited.
The pre-BLE Wi-Fi implementation is preserved in commit `7032183`.
See [setup, power requirements, controls, and recovery](../../../esp32-cam/README.md).
This app uses the October 2026 `badge`, `screen`, `image`, `rect`, and logical
button APIs supplied by Badgeware, not the older 2025 simulator.

## Agent handoff: app and UX iteration

The app directory is **`badge/apps/camera/`**, installed as
**`/system/apps/camera/`**. **`esp32-cam/`** is the separate companion firmware
project, not the badge app name. Do not rename either when deploying.

| File | Responsibility |
| --- | --- |
| `__init__.py` | `CameraApp` state machine, buttons, rendering, BLE-to-Wi-Fi handoff |
| `camera_core.py` | Bounded nonblocking HTTP, JPEG validation/EXIF, atomic last-15 cache |
| `camera_ble.py` | BLE discovery and paginated RPC; copies callback data before queuing |
| `camera_pairing.py` | SRP authentication, credential verification/decryption, config persistence |
| `icon.png` | 24 x 24 launcher icon |
| `screenshot.png` | Documentation photo only; do not copy to the badge |

For presentation-only changes, edit `__init__.py`; normally no ESP32 rebuild or
reflash is required. Preserve Select capture/resume, Up/Down gallery, Left/Right
rotation, Back exit, pending-capture retry IDs, and stored photo orientation.
Do not erase `/camera_config.json` or `/state/camera/` to test a layout change.
The camera and badge may already be paired; first-use setup is not an upgrade step.

### Verified firmware APIs and pitfalls

- The attached device uses October 2026 Badgeware, not the older 2025 API
  documented elsewhere on this branch. `badge`, `screen`, `image`, `rect`,
  `mat3`, `brush`, `color`, `font`, `run`, and logical button constants are
  provided by the runtime. **Do not `import badge`.**
- `badge.mode(HIRES | VSYNC)` selects 320 x 240. The current photo area is below
  the 22-pixel title and above the footer at y=217. `run(app.update)` performs
  display updates and button polling; returning `False` exits the app.
- `image.load(jpeg_bytes, 320, 240)` decodes from memory. Use
  `screen.blit(frame, rect(...))`, not the old multi-coordinate blit signature.
- Preserve the image-brush transform order in `prepare_frame`: translate to
  display centre, scale, rotate, then translate by negative half-image size.
  Reversing it previously produced a split/wrapped image. Keep the source image
  alive while its brush is used. Run `rotation_hardware_probe.py` after changes.
- **Copy every BLE callback tuple before returning**, not just memoryviews.
  This build frees synchronous callback argument tuples on return. Queuing
  numeric-only tuples by reference caused native crashes and USB disappearance.
  `tuple(data)` may return the original tuple; construct a fresh tuple explicitly.
- Close BLE before joining camera Wi-Fi. Do not replace SRP with unauthenticated
  credential reads or assume this firmware supports native Bluetooth bonding.
- Real hardware is required for display, BLE, and JPEG-decoder verification;
  the 2025 simulator and desktop unit tests cannot establish those behaviors.

### Deploy and check

Follow the [exact macOS deployment commands](../../../esp32-cam/README.md#agent-deployment-checklist-macos).
Only the four Python files and icon belong on the badge. `/system` is read-only
through the normal REPL: use mass storage for persistent app updates, then eject.
Host-mounted files and `/camera_app_test.py` are test scaffolding, not installation.

From the repository root:

```sh
.venv/bin/python -m unittest discover -s esp32-cam/tests -p 'test_*.py'
mpremote connect <badge-port> run esp32-cam/tests/rotation_hardware_probe.py
mpremote connect <badge-port> run esp32-cam/tests/real_hardware_probe.py
```

The real hardware probe takes two actual SD photos and adds them to the badge
gallery; it is not read-only. It checks preview, capture dimensions, saved
thumbnail equality, frozen review, idempotent retries, and gallery navigation.
After testing, hard-reset the badge and confirm USB reappears; leave it in the
normal launcher, not a stopped development REPL. For native-risk changes use
the watchdog-protected BLE probes described in the companion README.

![Camera example displaying an upright saved photo](screenshot.png)
