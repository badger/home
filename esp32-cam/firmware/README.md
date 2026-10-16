# Generated camera firmware

Run `python esp32-cam/build.py` using the environment containing
`esp32-cam/requirements.txt`. It generates:

| File | Purpose |
| --- | --- |
| `esp32-cam.bin` | Complete merged image; flash at offset `0x0` |
| `firmware.bin` | Application only; flash at `0x10000`, not `0x0` |
| `bootloader.bin` | ESP32 bootloader |
| `partitions.bin` | Partition table |
| `boot_app0.bin` | Initial OTA selection data |
| `manifest.json` | Target information and SHA-256 checksums |

These generated files are git-ignored build artifacts. New BLE builds are
generic: credentials and pairing keys are generated on the camera, not embedded
in the binary. Older Wi-Fi-only builds do contain private credentials and must
not be published. Firmware source, the pinned build definition, and packaging
scripts are in the parent directory.

New cameras pair by holding the badge against the camera during the first three
minutes of power-on and selecting it in the app. No `PAIRING.TXT` or setup PIN
is generated. A faint flash-LED blink every two seconds indicates that this
first-pairing window is open; it stops on pairing or timeout and never appears
on already-paired boots. Upgrade both camera firmware and badge app for first-use pairing.
Existing remembered keys survive component-aware reflashing and keep working.
Proximity uses RSSI as a heuristic, not cryptographic distance verification;
see the [pairing threat model](../README.md#ble-pairing-and-security).

Use `python esp32-cam/flash.py --port <camera-port>` to verify the merged image's
checksums and flash the four separate components. This leaves NVS pairing data
at `0x9000` intact. Writing the entire merged image at `0x0` erases that data and
requires pairing again. The manifest records component offsets and hashes.
Pass `--backup /path/to/new-backup.bin` to preserve the
camera's original flash first. Read the [project guide](../README.md) before
flashing; this firmware is for an ESP32-CAM with an OV2640, not the badge.
