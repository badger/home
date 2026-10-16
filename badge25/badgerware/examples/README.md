# Badge examples

| Example | Firmware | Description |
| --- | --- | --- |
| [Basic screen drawing](screen-basic.py) | 2025 Badgeware | Drawing and text primitives |
| [Wi-Fi camera](../../../badge/apps/camera/README.md) | October 2026 Badgeware | ESP32-CAM live viewfinder, full-resolution SD photos, a persistent last-15 gallery, and rotation controls |

The camera app's canonical source is in
[`badge/apps/camera/`](../../../badge/apps/camera/); copy that complete app to the
2026 badge rather than duplicating it here. Its companion
[`esp32-cam/`](../../../esp32-cam/README.md) project contains the ESP32 firmware source,
build/flash scripts, board and purchase information, and setup instructions.
The 2025 simulator does not implement the camera example's 2026 APIs.
