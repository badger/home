# Menu

The badge's home screen: a launcher that lists every installed app and starts the one you pick.

## Usage

Use the LEFT, RIGHT, UP, and DOWN buttons to move between app icons and SELECT to launch the highlighted app. Apps appear automatically when they contain an `__init__.py` and a 24x24 `icon.png`.

Photo widgets, including the supplied temple-square photo, appear among the app tiles. Highlight a photo and press SELECT to open it full-screen; press any button to return to the menu.

The top status widget shows the IMU's step count beside the battery, refreshed
once per second. It displays the hardware's current 16-bit counter, not a daily
total: it wraps after 65,535 steps and resets when the firmware reinitializes
the IMU. The menu only reads it; it does not reset or save it. Firmware without
the IMU step API, or a sensor read failure, displays `-- steps` and prints a
diagnostic.

The menu imports the shipped `ui.mpy`, built from `src/ui.py`. After changing
that source, rebuild it from the repository root:

```powershell
python -m mpy_cross -o badge\apps\menu\ui.mpy badge\apps\menu\src\ui.py
```

## Photo assets

Photo widgets are listed in `gallery.py`. Each has a 320x240 full-screen PNG in `photos/` and a matching thumbnail in `photos/tiles/` (166x87 for a two-column, one-row widget). The temple-square photo was supplied by @rayraycodes with confirmed permission for redistribution under the project's MIT license, retains its supplied watermark, and is fitted without stretching in the full-screen view.
