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

**These generated files are git-ignored because the application and merged
images contain your private Wi-Fi pairing.** They are created locally rather
than checked in as a shared, credential-bearing binary. Firmware source,
the pinned PlatformIO build definition, and packaging scripts are in the parent
directory. Rebuilding preserves the existing pairing in `../local/`.

Use `python esp32-cam/flash.py --port <camera-port>` to verify the merged image's
checksum and flash it. Pass `--backup /path/to/new-backup.bin` to preserve the
camera's original flash first. Read the [project guide](../README.md) before
flashing; this firmware is for an ESP32-CAM with an OV2640, not the badge.
