# ESP32-CAM companion for the Universe 2026 badge

This pairs a diymore/AI Thinker **ESP32-CAM + OV2640 + ESP32-CAM-MB**
with the October 2026 Badgeware firmware. It does not use the 2025 APIs
documented elsewhere on this checkout.

The [badge camera example](../badge/apps/camera/README.md) provides a live
viewfinder, a Select-button shutter, frozen review of the saved photo, and a
persistent last-15 gallery. The ESP32 does the camera capture and SD-card work;
the badge handles the display and controls. Real-board testing achieved about
two live frames per second, with 1600 x 1200 originals and 200 x 150 badge copies.

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
| Wireless | 2.4 GHz Wi-Fi; Bluetooth is not used by this project |
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
  platformio.ini           Pinned AI Thinker ESP32-CAM build target
  requirements.txt         Host build-tool versions
  provision.py             Generate a private camera/badge Wi-Fi pairing
  build.py                 Build and package complete flashable firmware
  flash.py                 Check and flash a selected camera, optional backup
  firmware/                Generated binaries/checksums (git-ignored)
  local/                   Private pairing files (git-ignored)
  tests/                   Host tests, synthetic server, physical-badge probes
badge/apps/camera/          The installable 2026 badge example
```

## Connections and controls

The camera creates a private WPA2 Wi-Fi access point; the badge joins it
directly. No router, Internet service, Bluetooth pairing, or Mac is needed
after installation.

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

`build.py` creates a pairing on the first build, compiles the firmware, and
packages a complete flashable image at **`firmware/esp32-cam.bin`** with a
SHA-256 manifest. It obtains flash offsets and component locations from
PlatformIO's build metadata. Building does not connect to or reflash hardware.
The [firmware directory guide](firmware/README.md) explains all generated files.

`provision.py` creates a unique SSID and random password in `local/`; you can
also run it separately before the first build.
That directory is git-ignored. Keep `local/camera_config.h` and
`local/camera_config.json` together: they contain the same private pairing.
The firmware image also contains the pairing; do not publish a provisioned
image. The provisioner refuses to overwrite existing pairing files, and
rebuilding reuses your pairing rather than disconnecting an installed badge.

Before replacing firmware, back up the camera's flash. Substitute the
**camera's CH340 port**, not the badge port:

```sh
.venv/bin/python esp32-cam/flash.py --port /dev/cu.usbserial-EXAMPLE \
  --backup /path/outside/repo/esp32-original.bin
```

`flash.py` validates the merged image checksum, optionally backs up the original
flash, then writes the merged image at offset `0x0`. It refuses to overwrite an
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

1. Copy `local/camera_config.json` to the badge's writable root:
   `mpremote connect <badge-port> fs cp esp32-cam/local/camera_config.json :/camera_config.json`.
2. Enter the badge's **Mass Storage** app, or use
   `mpremote connect <badge-port> exec "import powman; powman.reset_into_msc()"`.
   A serial-disconnect error is normal as it changes USB mode.
3. Copy only `__init__.py`, `camera_core.py`, and `icon.png` from
   `badge/apps/camera/` into the USB volume's `apps/camera/` directory.
   On the tested firmware the volume root maps to `/system`, so do **not**
   create an extra `system/` directory.
4. Eject the badge USB volume cleanly; the badge reboots automatically.
5. Power the camera and open **Camera**.

Photo thumbnails and a recovery record live in `/state/camera/`.
Live frames stay in RAM: streaming does not continuously write badge flash.
Wi-Fi requests use a bounded nonblocking socket state machine, allowing
navigation and exit while connecting/receiving. Captures wait up to 30 seconds;
other requests wait up to 12 seconds.

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

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No camera serial port on the Mac | Use the USB-A-to-C data cable; look for the CH340 `1a86:7523` device, not the badge's USB CDC device |
| `Camera initialization failed: 261` / `0x105` | Sensor not detected: unplug power, check the ribbon/latch, and verify it is an AI Thinker-compatible OV2640 board; a spare worked when the first tested sensor did not |
| SD unavailable | Check FAT32 format, seating, capacity, and free space; the firmware deliberately never formats the card |
| Badge cannot find camera Wi-Fi | Power the camera independently and check that badge config and camera binary use the same pairing |
| Sideways picture | Press Left/Right on the badge; the tested side-mounted arrangement needed 270 degrees clockwise (90 degrees counterclockwise) |
| Badge left in a development REPL | Reboot normally and open Camera from the launcher before unplugging; installed apps do not need a host-mounted directory |

Hardware reference:
[Universe 2026 schematic and power documentation](https://github.com/badger/home/blob/main/hardware/README.md).
