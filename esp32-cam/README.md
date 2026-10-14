# ESP32-CAM companion for the Universe 2026 badge

This pairs a diymore/AI Thinker **ESP32-CAM + OV2640 + ESP32-CAM-MB**
with the October 2026 Badgeware firmware. It does not use the 2025 APIs
documented elsewhere on this checkout.

The [badge camera example](../badge/apps/camera/README.md) provides a live
viewfinder, a Select-button shutter, frozen review of the saved photo, and a
persistent last-15 gallery. The ESP32 does the camera capture and SD-card work;
the badge handles the display and controls. Real-board testing achieved about
two live frames per second, with 1600 x 1200 originals and 200 x 150 badge copies.

**Verified on the attached October 2026 badge and ESP32-CAM:** first-use BLE
pairing, wrong-code rejection, live preview, SD capture/review/gallery, and
automatic reconnection with a fresh Wi-Fi password after camera restart.
The latest run delivered 75 frames in 30 seconds with stable free memory.
The earlier native crash was fixed by copying every queued BLE callback tuple:
this MicroPython build frees synchronous callback arguments when the handler
returns. The hardware-tested Wi-Fi-only baseline is preserved in `7032183`.
The application-level cryptographic integration remains unaudited.

## Board and purchasing

- [Purchase the ESP32-CAM kit on Amazon](https://link.amazon/B0hhCS55I)
- [diymore ESP32-CAM / OV2640 product page](https://www.diymore.cc/products/esp32-cam-wifi-wireless-module-esp32-serial-to-wifi-esp32-cam-spi-flash-bluetooth-development-board-with-ov2640-camera-module)

Choose the **full kit with the OV2640 camera and ESP32-CAM-MB USB-C programming
carrier**, not just a bare ESP32 module. The tested boards have:

| Component | Details |
| --- | --- |
| MCU | ESP32-D0WD-V3, dual-core up to 240 MHz |
| Flash | 4 MB (32 Mbit), confirmed on both tested boards |
| Camera memory | External PSRAM, required by this firmware |
| Sensor | OV2640, maximum 1600 x 1200 JPEG capture |
| Wireless | 2.4 GHz Wi-Fi for photos; Bluetooth LE for provisioning |
| Removable storage | microSD/TF card slot; FAT32, within the vendor's stated 4 GB capacity limit |
| Programmer | ESP32-CAM-MB carrier with CH340 USB-to-UART and Type-C connector |
| Power | Regulated 5 V USB input; vendor specifies 4.75-5.25 V |

The carrier's USB port is a serial programming/power connection, not a USB
webcam interface. Also obtain a USB-A-to-C data cable and a suitable microSD card.
The badge is the separate Universe 2026 device; ESP32 firmware must never be
flashed onto it.

## Project layout

```text
esp32-cam/
  src/main.cpp             Camera, Wi-Fi HTTP protocol, SD saves, JPEG/EXIF
  src/pairing.cpp           BLE RPC, SRP authentication, encrypted credentials, NVS
  platformio.ini           Pinned AI Thinker ESP32-CAM build target
  requirements.txt         Host build-tool versions
  provision.py             Legacy Wi-Fi-only provisioning (unused by BLE builds)
  build.py                 Build and package complete flashable firmware
  flash.py                 Check and flash a selected camera, optional backup
  firmware/                Generated binaries/checksums (git-ignored)
  local/                   Private pairing files (git-ignored)
  tests/                   Host tests, synthetic server, physical-badge probes
badge/apps/camera/          The installable 2026 badge example
```

## Connections and controls

The camera creates its own unique WPA2 Wi-Fi access point; the badge joins it
directly. BLE establishes a remembered relationship and retrieves a fresh
Wi-Fi password after camera restarts. No router, Internet service, or Mac is
needed after installation and initial pairing.

**Power the camera separately with a regulated 5 V USB supply or power bank.**
The badge's documented USB-C circuitry is a power input, not a 5 V host
power output. Connecting these two USB ports together is not a supported
way to power the camera. Keep both plugged into the Mac during development.
A USB-A-to-C **data** cable works with the camera's CH340 programmer;
some of these carrier boards do not enumerate with C-to-C cables.
Do not feed 5 V into badge GPIO or its 3.3 V Qw/ST connector.

Open **Camera** from the badge launcher:

- **Select** in the live view captures an OV2640 maximum-resolution
  **1600 x 1200 JPEG** onto the camera's SD card.
- The displayed image then freezes on a thumbnail decoded from that
  **saved JPEG**, not a later live frame.
- **Select** again returns to the live view.
- **Up/Down** opens the last-15 gallery and browses older/newer photos.
  **Select** returns to the camera. The gallery works without camera power.
- **Left/Right** rotates the view in 90-degree steps and remembers the setting.
  The image is fitted without cropping or stretching. Each new SD original and
  thumbnail carries an EXIF orientation tag, so compatible photo viewers also
  display it upright without recompressing the full-resolution image. The badge
  gallery honors each photo's own orientation.
- **Back/Home** leaves the app.
- On an error, **Select** reconnects/retries. A pending capture keeps the same
  ID across retries and badge restarts, so a lost response does not take a
  second photo.

The badge retains the last **15 compact 200 x 150 JPEG copies**, not 15
full-resolution originals: its writable data partition is only about 1 MiB.
Originals remain on the camera SD card indefinitely. The app never deletes
originals from the SD card. Files are named `/photos/<capture-id>.jpg`, with
matching `.thumb.jpg` files. A FAT32 SD card is required; firmware never formats
the card. An SD error does not prevent live preview.

## Build and flash the camera

Run these commands from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r esp32-cam/requirements.txt
.venv/bin/python esp32-cam/build.py
.venv/bin/python -m serial.tools.list_ports -v
```

`build.py` compiles generic firmware without embedded pairing secrets and
packages a complete flashable image at **`firmware/esp32-cam.bin`** with a
SHA-256 manifest. It obtains flash offsets and component locations from
PlatformIO's build metadata. Building does not connect to or reflash hardware.
The [firmware directory guide](firmware/README.md) explains all generated files.

The same new binary can be installed on multiple cameras. Each generates its
own identity-based SSID, first-use pairing code, and random Wi-Fi password at
runtime. The older `provision.py` and ignored `local/` files are retained only
for rollback to the Wi-Fi-only baseline; BLE builds do not read them.

Before replacing firmware, back up the camera's flash. Substitute the
**camera's CH340 port**, not the badge port:

```sh
.venv/bin/python esp32-cam/flash.py --port /dev/cu.usbserial-EXAMPLE \
  --backup /path/outside/repo/esp32-original.bin
```

`flash.py` validates the merged image and component checksums, optionally backs
up the original flash, then writes the four components at their proper offsets.
This preserves pairing NVS at `0x9000`; writing a whole merged image at `0x0`
would erase it. The script refuses to overwrite an
existing backup. A full 4 MB backup takes about six minutes at the reliable
115200 baud setting. For later reflashes, omit `--backup` once you have a safe
original backup. `--port` is always required; the script never guesses a device.

For a source-only PlatformIO workflow, use
`python -m platformio run -d esp32-cam` and add `--target upload --upload-port
<camera-port>` when you deliberately want to reflash.

The ESP32-CAM-MB carrier normally controls boot/reset automatically.
If it cannot connect, hold IO0/BOOT while resetting the camera, then retry.
Release BOOT and reset after flashing. Use 115200 for unreliable USB bridges.
The target is **ESP32**, not ESP32-S3; the pinned platform includes the camera,
JPEG conversion, Wi-Fi, web-server, and SD_MMC libraries.

## Install on the badge

Do not replace badge firmware, its launcher, or Wi-Fi settings.
Install `mpremote` with `python -m pip install mpremote` if it is not available.

1. For a new install, no config file is needed. When migrating the old manually
   provisioned app, privately back up `/camera_config.json` and replace its
   contents with `{"pairing":"srp-v1"}`. Do not overwrite an established BLE
   config: it contains the remembered pairing key.
2. Enter the badge's **Mass Storage** app, or use
   `mpremote connect <badge-port> exec "import powman; powman.reset_into_msc()"`.
   A serial-disconnect error is normal as it changes USB mode.
3. Copy `__init__.py`, `camera_core.py`, `camera_pairing.py`, `camera_ble.py`,
   and `icon.png` from
   `badge/apps/camera/` into the USB volume's `apps/camera/` directory.
   On the tested firmware the volume root maps to `/system`, so do **not**
   create an extra `system/` directory.
4. Eject the badge USB volume cleanly; the badge reboots automatically.
5. Power the camera and open **Camera**. Use Up/Down to select its
   `BadgeCam-<identity>` advertisement, then Select.
6. On first use, enter the six-digit code from `/PAIRING.TXT` on the camera SD
   card, or its 115200-baud USB serial startup output. Left/Right chooses a
   digit, Up/Down changes it, and Select submits. Keep the code private.
   Subsequent starts reconnect automatically and refresh credentials over BLE.

Photo thumbnails and a recovery record live in `/state/camera/`.
Live frames stay in RAM: streaming does not continuously write badge flash.
Wi-Fi requests use a bounded nonblocking socket state machine, allowing
navigation and exit while connecting/receiving. Captures wait up to 30 seconds;
other requests wait up to 12 seconds.

### Agent deployment checklist (macOS)

Work from the repository root. Keep **two distinct targets**: `esp32-cam/` builds
for the ESP32-CAM; `badge/apps/camera/` installs on the badge. The badge itself
does not need new firmware. Use the existing virtual environment when available;
`mpremote` may already be installed globally even when absent from `.venv`.

1. Discover current serial ports with
   `.venv/bin/python -m serial.tools.list_ports -v`. The tested camera's CH340
   is VID/PID `1a86:7523`; the badge is `2e8a:1101`. Previously they appeared as
   `/dev/cu.usbserial-111240` and `/dev/cu.usbmodem101`, but rediscover rather than
   assuming those names. Only one process may own each port.
2. Build camera changes with `.venv/bin/python esp32-cam/build.py`, then use
   `.venv/bin/python esp32-cam/flash.py --port <camera-port>`. Preserve an original
   flash backup before the first replacement. Do not use `erase-flash` or flash
   the merged binary over an existing pairing; use the component-aware script.
   A badge-only UX change does not require rebuilding/flashing the camera.
3. Preserve `/camera_config.json` privately before changing pairing logic:
   `mpremote connect <badge-port> fs cp :/camera_config.json <private-backup-path>`.
   Skip this only for a genuinely new, unconfigured badge. Never commit or print
   this file: it contains the pairing key and current Wi-Fi password.
4. Enter mass storage:
   `mpremote connect <badge-port> exec "import powman; powman.reset_into_msc()"`.
   Serial will disappear and the command may report an error. Confirm the
   **BADGER** volume appears before proceeding; the error alone is not success.
5. On the verified BADGER volume, install only the runtime files:

   ```sh
   (
   set -e
   mkdir -p /Volumes/BADGER/apps/camera
   cp badge/apps/camera/{__init__.py,camera_core.py,camera_ble.py,camera_pairing.py,icon.png} \
     /Volumes/BADGER/apps/camera/
   for name in __init__.py camera_core.py camera_ble.py camera_pairing.py icon.png; do
     cmp "badge/apps/camera/$name" "/Volumes/BADGER/apps/camera/$name"
   done
   sync
   diskutil eject /Volumes/BADGER
   )
   ```

   Stop and correct any copy/comparison failure before treating deployment as
   complete. Do not copy screenshots, READMEs, tests, or `__pycache__`; the writable
   storage budget is small. The volume root is `/system`, not `/`.
6. Wait for serial to reappear. Open Camera normally, or run the hardware probes
   below. Preserve the existing pairing and photo cache during updates.
7. Clean up only known temporary test files, including any
   `/camera_test_code.json` used for automated pairing. Then use
   `mpremote connect <badge-port> exec "import machine; machine.reset()"` and
   verify USB re-enumeration and normal startup. This reset also disconnects
   serial, so an expected transport error is not itself a failure.

For native-risk experiments, enable `machine.WDT(timeout=8000)` **before**
starting the app and feed it in the test loop. The watchdog cannot be disabled
without resetting. BLE SRP calculations need time, so do not shorten it blindly.
`ble_hardware_probe.py` already supplies this protection and hard-resets on
completion; inspect its PASS/FAIL output, not merely the host process exit code.
If USB is absent after waiting for watchdog recovery, physical RESET is required;
the host cannot send a software reset to a device that is no longer enumerated.

The first failed camera's sensor returned `0x105`; the spare camera worked with
the same pin map and firmware. Do not change wiring definitions to hide a sensor
failure. Never format the SD card or discard existing originals while debugging.

## BLE pairing and security

The tested badge exposes BLE central/GATT APIs but **not native BLE bonding**:
`gap_pair` and the security config options are absent. This project therefore
uses an application-level relationship, not an OS Bluetooth bond. SRP-6a uses
the RFC 5054 2048-bit group, SHA-256, and a per-camera six-digit code. The code
is never transmitted over BLE. Initial authentication is limited to five
attempts per camera boot, at least five seconds apart. Proximity is not proof
of ownership.

Both sides retain a 256-bit pairing key: camera NVS and the badge's private
`/camera_config.json`. Config writes are atomic. The prospective key is saved
before first pairing is confirmed so a lost confirmation is recoverable.
The camera refuses replacement pairing while owned. Reconnection uses
HMAC-SHA256 over fresh camera/badge nonces. Credentials use AES-256-CBC with
random IVs and encrypt-then-HMAC authentication, with separately derived keys.
The badge authenticates before decrypting. This custom integration is
experimental and has not had an independent audit.

The app closes BLE before opening Wi-Fi. Each camera has a different SSID and
password, but nearby cameras still share 2.4 GHz airtime.

To deliberately replace the owner, send `UNPAIR` and a newline over camera USB
serial. This clears pairing, generates a new setup code on reboot, and leaves
SD photos intact. Back up and remove the badge's old `/camera_config.json`
before pairing again. Protect the setup code, camera SD card, and USB access.

For development, USB serial also accepts `RPC <hex-message>` and returns
`RPC <hex-response>` using the same authenticated protocol handler. It is
disabled while a BLE client is connected. This tests ESP32 cryptography
without claiming to test its BLE radio or the badge driver.

### Provisioning wire format

Service UUID: `b9a10001-9c45-4ec2-867d-9ae58d13a001`; write characteristic
`b9a10002-9c45-4ec2-867d-9ae58d13a001`; read characteristic
`b9a10003-9c45-4ec2-867d-9ae58d13a001`. Requests and responses are at most 512
bytes. Each BLE fragment has a two-byte big-endian offset, two-byte total length,
and up to 16 data bytes, so no negotiated MTU is required. Write `ff` followed
by a two-byte offset to request a response page. A one-byte `00` read means
the response is not yet ready.

| Opcode | Request payload | Response payload |
| --- | --- | --- |
| 1 | Random 16-byte badge nonce | Camera ID (6), salt (16), camera nonce (16), owned flag (1) |
| 2 | SRP client public value A (256 bytes, big-endian) | Server public value B (256 bytes) |
| 3 | Client proof (32 bytes) | Server proof (32 bytes); ownership has been saved |
| 4 | Reconnect proof (32 bytes) | IV (16), AES-CBC ciphertext, HMAC (32) |
| 255 | Not a request | UTF-8 error text |

All responses start with their opcode. SRP integers are padded to 256 bytes;
the username is the 12-character lowercase hexadecimal camera ID. Hashing uses
SHA-256, including `k = H(PAD(N) || PAD(2))`, `u = H(PAD(A) || PAD(B))`,
and `x = H(salt || H(username || ":" || code))`.
The context is ASCII `BadgeCam-v1`, camera ID bytes, badge nonce, camera nonce.
The transcript hash is `H(context || salt || PAD(A) || PAD(B))`.
The pairing key is `HMAC(H(PAD(S)), "pair" || transcript)`. Client/server
proofs are `HMAC(pairing_key, "client"/"server" || transcript)`.
Reconnect proof is `HMAC(pairing_key, "resume" || context)`.
The session key is `HMAC(pairing_key, "session" || context)`, with encryption
and MAC keys derived using HMAC labels `"enc"` and `"mac"`. JSON credentials
use PKCS#7 padding; the MAC covers IV followed by ciphertext.

## Local protocol

All endpoints use HTTP with `Content-Length`, inside the private camera AP.
Capture IDs are exactly 16 lowercase hexadecimal characters.

| Request | Result |
| --- | --- |
| `GET /status` | Protocol version, camera/SD availability, native dimensions |
| `GET /preview` | Fresh QVGA (320 x 240) JPEG, at most 64 KiB |
| `POST /capture?id=<id>&rotation=270` | Idempotent SD save and thumbnail; clockwise rotation in degrees (0/90/180/270) |
| `GET /thumbnail?id=<id>` | Saved 200 x 150 JPEG, at most 32 KiB |
| `GET /photo?id=<id>` | Full-resolution JPEG read from the SD card |

The sensor starts with UXGA buffers in PSRAM, switches to QVGA for live view,
and discards stale frames after changing resolution. SD runs in one-bit mode
to avoid driving the bright white flash LED on GPIO4. Full saves and thumbnail
saves use temporary files followed by rename. Sensor/PSRAM/SD failures are
reported, not converted into a successful capture.

Rotation tags do not change the sensor's encoded 1600 x 1200 pixel dimensions;
a 90-degree-rotated original displays as 1200 x 1600 in EXIF-aware viewers.
Retrying an existing capture ID retains that original shot and its orientation,
even if a later request specifies a different rotation.

## Checks

```sh
.venv/bin/python -m pip install -r esp32-cam/tests/requirements.txt
.venv/bin/python -m unittest discover -s esp32-cam/tests -p 'test_*.py'
.venv/bin/python esp32-cam/build.py
```

`tests/mock_camera.py --directory <scratch-directory>` serves **synthetic**
JPEGs for protocol development. Never mistake a mock result for sensor
verification. `tests/hardware_probe.py` exercises the real badge UI/cache
against that server, including 17 captures, retention, gallery, and SD-error
recovery. It uses `/camera-test/` and `/state/camera-test/`, separate from real
photos. Its optional `CAMERA_OFFLINE_TEST=True` mode uses local JPEG fixtures
and mocks only the network, explicitly labelling the result.
`tests/real_hardware_probe.py` instead uses the installed app and real private
camera AP, checks live frame delivery, reads back full-resolution SD originals,
checks EXIF and thumbnail bytes, and verifies idempotent captures and gallery.
`tests/rotation_hardware_probe.py` checks all four rotations against exact
framebuffer pixel colors, catching transform-order and image-wrapping mistakes.

`tests/ble_scan_probe.py` checks the badge's native scan in isolation.
`tests/ble_isolation_probe.py` compares display and WLAN lifecycle variants
with watchdog recovery and a diagnostic `/ble_probe_stage.txt` checkpoint.
`tests/ble_hardware_probe.py` exercises the actual BLE app; a private
`/camera_test_code.json` containing `camera_id` and `code` enables automated
first-use entry. Remove that test file afterwards.
The full probe enables an eight-second hardware watchdog to recover from native
hangs and reboots to the standalone launcher on completion. A dropped USB
connection alone is not a passing result; check the probe's explicit PASS lines.
`tests/ble_reconnect_probe.py` executes the installed app through the normal
Badgeware run loop after a camera restart, verifies the pairing key is unchanged,
the Wi-Fi password is refreshed, and live frames continue for ten seconds.
`tests/real_hardware_probe.py` accepts an optional `CAMERA_WATCHDOG` object;
probes using a watchdog will reboot once feeding stops.
`tests/ble_host_probe.py` tests the actual BLE GATT protocol from a Mac with
Bluetooth permission and a Python host declaring
`NSBluetoothAlwaysUsageDescription`. Its `--serial-port` alternative verifies
only the ESP32 protocol/cryptography over USB, **not BLE**. Its `--check-rekey`
flag checks that a camera restart changes the Wi-Fi password without changing
the remembered pairing. Host tests cross-check SRP against `srptools`, AES
against `cryptography`, and HMAC against the standard library.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No camera serial port on the Mac | Use the USB-A-to-C data cable; look for the CH340 `1a86:7523` device, not the badge's USB CDC device |
| `Camera initialization failed: 261` / `0x105` | Sensor not detected: unplug power, check the ribbon/latch, and verify it is an AI Thinker-compatible OV2640 board; a spare worked when the first tested sensor did not |
| SD unavailable | Check FAT32 format, seating, capacity, and free space; the firmware deliberately never formats the card |
| Badge cannot find camera Wi-Fi | Power the camera independently; reconnect so BLE can refresh credentials |
| Camera paired elsewhere | Restore the private badge config or deliberately reset ownership with USB `UNPAIR` |
| Incorrect pairing code | Use this camera's current `PAIRING.TXT` or USB startup code |
| Old BLE build disappears from USB | Install the version that copies all callback event tuples; physically RESET first if needed |
| Sideways picture | Press Left/Right on the badge; the tested side-mounted arrangement needed 270 degrees clockwise (90 degrees counterclockwise) |
| Badge left in a development REPL | Reboot normally and open Camera from the launcher before unplugging; installed apps do not need a host-mounted directory |

Hardware reference:
[Universe 2026 schematic and power documentation](https://github.com/badger/home/blob/main/hardware/README.md).
