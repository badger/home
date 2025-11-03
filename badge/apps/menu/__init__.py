import sys
import os

sys.path.insert(0, "/system/apps/menu")
os.chdir("/system/apps/menu")

import math
from badgeware import screen, PixelFont, Image, SpriteSheet, is_dir, file_exists, shapes, brushes, io, run
from icon import Icon, sprite_for
import ui

mona = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 11, 1)
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")
# screen.antialias = Image.X2

ROOT = "/system/apps"
current_path = ROOT
current_depth = 0


def scan_entries(root):
    entries = []
    try:
        for name in os.listdir(root):
            if name.startswith("."):
                continue
            full_path = "{}/{}".format(root, name)
            if is_dir(full_path):
                has_module = file_exists("{}/__init__.py".format(full_path))
                kind = "app" if has_module else "folder"
                entry = {"name": name, "path": full_path, "kind": kind}
                if kind == "app":
                    icon_path = "{}/icon.png".format(full_path)
                    if file_exists(icon_path):
                        entry["icon"] = icon_path
                entries.append(entry)
    except OSError as exc:
        print("scan_entries failed for {}: {}".format(root, exc))
    folders = [item for item in entries if item["kind"] == "folder"]
    apps_only = [item for item in entries if item["kind"] == "app"]
    folders.sort(key=lambda item: item["name"])
    apps_only.sort(key=lambda item: item["name"])
    return folders + apps_only


# Auto-discover apps with __init__.py
apps = [
    (entry["name"], entry["name"])
    for entry in scan_entries(ROOT)
    if entry["kind"] == "app" and entry["name"] not in ("menu", "startup")
]

# Pagination constants
APPS_PER_PAGE = 6
current_page = 0
total_pages = max(1, math.ceil(len(apps) / APPS_PER_PAGE))

# find installed apps and create icons for current page
def load_page_icons(page, depth=0, active_path=ROOT):
    icons = []
    page_size = APPS_PER_PAGE - 1 if depth > 0 else APPS_PER_PAGE
    if page_size <= 0:
        page_size = 1

    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(apps))

    entries = []

    if depth > 0:
        entries.append({"name": "..", "path": active_path, "kind": "back"})

    for i in range(start_idx, end_idx):
        app = apps[i]
        entry = {
            "name": app[0],
            "path": "{}/{}".format(ROOT, app[1]),
            "kind": "app",
        }
        icon_path = "{}/icon.png".format(entry["path"])
        if file_exists(icon_path):
            entry["icon"] = icon_path
        entries.append(entry)

    for slot, entry in enumerate(entries):
        x = slot % 3
        y = slot // 3
        pos = (x * 48 + 33, y * 48 + 42)
        try:
            sprite = sprite_for(entry)
            icons.append(Icon(pos, entry["name"], slot % APPS_PER_PAGE, sprite))
        except Exception as e:
            print("Error loading icon for {}: {}".format(entry["path"], e))
    return icons

icons = load_page_icons(current_page, current_depth, current_path)

active = 0

MAX_ALPHA = 255
alpha = 30


def update():
    global active, icons, alpha, current_page, total_pages

    # process button inputs to switch between icons
    if io.BUTTON_C in io.pressed:
        active += 1
    if io.BUTTON_A in io.pressed:
        active -= 1
    if io.BUTTON_UP in io.pressed:
        active -= 3
    if io.BUTTON_DOWN in io.pressed:
        active += 3
    
    # Handle wrapping and page changes
    if active >= len(icons):
        if current_page < total_pages - 1:
            # Move to next page
            current_page += 1
            icons = load_page_icons(current_page, current_depth, current_path)
            active = 0
        else:
            # Wrap to beginning
            active = 0
    elif active < 0:
        if current_page > 0:
            # Move to previous page
            current_page -= 1
            icons = load_page_icons(current_page, current_depth, current_path)
            active = len(icons) - 1
        else:
            # Wrap to end
            active = len(icons) - 1
    
    # Launch app with error handling
    if io.BUTTON_B in io.pressed:
        app_idx = current_page * APPS_PER_PAGE + active
        if app_idx < len(apps):
            app_path = "{}/{}".format(ROOT, apps[app_idx][1])
            try:
                # Verify the app still exists before launching
                if is_dir(app_path) and file_exists(f"{app_path}/__init__.py"):
                    return app_path
                else:
                    print(f"Error: App {apps[app_idx][1]} not found or missing __init__.py")
            except Exception as e:
                print(f"Error launching app {apps[app_idx][1]}: {e}")

    ui.draw_background()
    ui.draw_header()

    # draw menu icons
    for i in range(len(icons)):
        icons[i].activate(active == i)
        icons[i].draw()

    # draw label for active menu icon
    if Icon.active_icon:
        label = f"{Icon.active_icon.name}"
        w, _ = screen.measure_text(label)
        screen.brush = brushes.color(211, 250, 55)
        screen.draw(shapes.rounded_rectangle(80 - (w / 2) - 4, 100, w + 8, 15, 4))
        screen.brush = brushes.color(0, 0, 0, 150)
        screen.text(label, 80 - (w / 2), 101)
    
    # draw page indicator if multiple pages
    if total_pages > 1:
        page_label = f"{current_page + 1}/{total_pages}"
        w, _ = screen.measure_text(page_label)
        screen.brush = brushes.color(211, 250, 55, 150)
        screen.text(page_label, 160 - w - 5, 112)

    if alpha <= MAX_ALPHA:
        screen.brush = brushes.color(0, 0, 0, 255 - alpha)
        screen.clear()
        alpha += 30

    return None

if __name__ == "__main__":
    run(update)
