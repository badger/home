"""Build and package generic BLE-provisioned ESP32-CAM firmware."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    pio = [sys.executable, "-m", "platformio"]
    subprocess.run(pio + ["run", "--project-dir", str(ROOT)], check=True)
    metadata = json.loads(subprocess.check_output(
        pio + ["project", "metadata", "--project-dir", str(ROOT), "--json-output"],
        text=True,
    ))["esp32cam"]
    images = metadata["extra"]["flash_images"] + [{
        "offset": metadata["extra"]["application_offset"],
        "path": str(Path(metadata["prog_path"]).with_suffix(".bin")),
    }]
    output = ROOT / "firmware"
    output.mkdir(exist_ok=True)
    merge = [sys.executable, "-m", "esptool", "--chip", "esp32", "merge-bin",
             "--output", str(output / "esp32-cam.bin")]
    files = {}
    for entry in images:
        source = Path(entry["path"])
        destination = output / source.name
        shutil.copyfile(source, destination)
        destination.chmod(0o600)
        merge.extend([str(entry["offset"]), str(destination)])
        files[destination.name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    subprocess.run(merge, check=True)
    (output / "esp32-cam.bin").chmod(0o600)
    files["esp32-cam.bin"] = hashlib.sha256((output / "esp32-cam.bin").read_bytes()).hexdigest()
    manifest = {
        "chip": "esp32",
        "board": "esp32cam",
        "flash_offset": "0x0",
        "contains_private_pairing": False,
        "flash_images": [{"offset": entry["offset"], "file": Path(entry["path"]).name}
                         for entry in images],
        "sha256": files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Ready:", output / "esp32-cam.bin")
    print("Generic firmware: pairing and Wi-Fi credentials are generated on the camera.")


if __name__ == "__main__":
    main()
