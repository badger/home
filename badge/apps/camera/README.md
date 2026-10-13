# Camera (2026 firmware only)

Live Wi-Fi viewfinder and shutter for a diymore ESP32-CAM with OV2640.
Select takes a full-resolution photo on the camera SD card and freezes its
preview; Select again resumes live view. Up/Down browses the last 15 compact
photo copies stored on the badge.
Left/Right changes rotation in 90-degree steps; the setting persists and new
SD photos carry matching EXIF orientation metadata.

Requires the companion firmware and private `/camera_config.json`.
See [setup, power requirements, controls, and recovery](../../../esp32-cam/README.md).
This app uses the October 2026 `badge`, `screen`, `image`, `rect`, and logical
button APIs supplied by Badgeware, not the older 2025 simulator.

![Camera example displaying an upright saved photo](screenshot.png)
