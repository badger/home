# Menu

The badge's home screen: a launcher that lists every installed app and starts the one you pick.

## Usage

Use the LEFT, RIGHT, UP, and DOWN buttons to move between app icons and SELECT to launch the highlighted app. Apps appear automatically when they contain an `__init__.py` and a 24x24 `icon.png`.

Photo widgets, including the supplied temple-square photo, appear among the app tiles. Highlight a photo and press SELECT to open it full-screen; press any button to return to the menu.

## Photo assets

Photo widgets are listed in `gallery.py`. Each has a 320x240 full-screen PNG in `photos/` and a matching thumbnail in `photos/tiles/` (166x87 for a two-column, one-row widget). The temple-square photo is used with the user's confirmed permission, retains its supplied watermark, and is fitted without stretching in the full-screen view.
