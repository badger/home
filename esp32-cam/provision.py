"""Generate a private Wi-Fi pairing shared by the camera and badge."""

import json
import secrets
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent / "local"
    directory.mkdir(exist_ok=True)
    header = directory / "camera_config.h"
    config = directory / "camera_config.json"
    if header.exists() or config.exists():
        raise SystemExit("Pairing files already exist; reuse them, do not overwrite.")
    ssid = "BadgeCamera-" + secrets.token_hex(3)
    password = secrets.token_urlsafe(18)
    header.write_text(
        '#pragma once\n#define CAMERA_SSID "' + ssid
        + '"\n#define CAMERA_PASSWORD "' + password + '"\n'
    )
    config.write_text(json.dumps({
        "ssid": ssid, "password": password, "host": "192.168.4.1", "port": 80,
    }) + "\n")
    header.chmod(0o600)
    config.chmod(0o600)
    print("Created private pairing files in esp32-cam/local/ (git-ignored).")


if __name__ == "__main__":
    main()
