"""Flash a packaged image to an explicitly selected ESP32-CAM serial port."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Camera CH340 serial port, NOT the badge port")
    parser.add_argument("--backup", type=Path, help="Read original 4 MB flash to a NEW file first")
    args = parser.parse_args()
    image = ROOT / "firmware" / "esp32-cam.bin"
    manifest_path = ROOT / "firmware" / "manifest.json"
    if not image.is_file() or not manifest_path.is_file():
        raise SystemExit("Run build.py first to generate firmware/esp32-cam.bin and its manifest.")
    manifest = json.loads(manifest_path.read_text())
    if (manifest["chip"] != "esp32" or manifest["flash_offset"] != "0x0"
            or hashlib.sha256(image.read_bytes()).hexdigest() != manifest["sha256"][image.name]):
        raise SystemExit("Firmware identity/checksum mismatch: rebuild before flashing.")
    components = manifest.get("flash_images")
    if not components:
        raise SystemExit("Rebuild with build.py: component manifest required to preserve pairing NVS.")
    expected = {"bootloader.bin": 0x1000, "partitions.bin": 0x8000,
                "boot_app0.bin": 0xe000, "firmware.bin": 0x10000}
    if len(components) != len(expected):
        raise SystemExit("Invalid flash component manifest.")
    flash_args = []
    seen = set()
    for entry in components:
        name = entry["file"]
        offset = int(str(entry["offset"]), 0)
        if name not in expected or name in seen or offset != expected[name]:
            raise SystemExit("Invalid flash component offset.")
        seen.add(name)
        component = ROOT / "firmware" / name
        limits = {"bootloader.bin": 0x7000, "partitions.bin": 0x1000,
                  "boot_app0.bin": 0x2000, "firmware.bin": 0x300000}
        if (not component.is_file() or not 0 < component.stat().st_size <= limits[name]
                or hashlib.sha256(component.read_bytes()).hexdigest() != manifest["sha256"].get(name)):
            raise SystemExit("Component checksum/size mismatch: rebuild before flashing.")
        flash_args.extend([hex(offset), str(component)])
    esptool = [sys.executable, "-m", "esptool", "--chip", "esp32",
               "--port", args.port, "--baud", "115200"]
    if args.backup is not None:
        if args.backup.exists():
            raise SystemExit("Backup already exists; choose a new path to preserve the old backup.")
        subprocess.run(esptool + ["read-flash", "0", "ALL", str(args.backup)], check=True)
    subprocess.run(esptool + ["write-flash"] + flash_args, check=True)


if __name__ == "__main__":
    main()
