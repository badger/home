import sys
import os

sys.path.insert(0, "/system/apps/menu")
os.chdir("/system/apps/menu")

from badgeware import screen, PixelFont, SpriteSheet, is_dir, file_exists, shapes, brushes, io, run
from icon import Icon, sprite_for
import ui

mona = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 11, 1)
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")
# screen.antialias = Image.X2

ROOT = "/system/apps"
current_path = ROOT
path_stack = []
current_entries = []
current_page = 0
total_pages = 1
icons = []
active = 0


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


# Pagination constants
APPS_PER_PAGE = 6


def current_dir():
    if not path_stack:
        return ROOT
    return path_stack[-1]


def rebuild_entries(reset_page):
    global current_entries, current_page, total_pages, icons, active, current_path
    current_path = current_dir()
    entries = scan_entries(current_path)
    if current_path == ROOT:
        filtered = []
        for entry in entries:
            if entry["name"] in ("menu", "startup"):
                continue
            filtered.append(entry)
        entries = filtered
    if path_stack:
        entries.insert(0, {"name": "..", "path": current_path, "kind": "back"})
    current_entries = entries
    total_pages = (len(current_entries) + APPS_PER_PAGE - 1) // APPS_PER_PAGE
    if total_pages < 1:
        total_pages = 1
    if reset_page:
        current_page = 0
    elif current_page >= total_pages:
        current_page = total_pages - 1
    start_idx = current_page * APPS_PER_PAGE
    page_len = len(current_entries) - start_idx
    if page_len < 0:
        page_len = 0
    if page_len > APPS_PER_PAGE:
        page_len = APPS_PER_PAGE
    if page_len == 0:
        active = 0
    elif active >= page_len:
        active = page_len - 1
    icons = load_page_icons(current_page)


def load_page_icons(page):
    result = []
    start_idx = page * APPS_PER_PAGE
    end_idx = min(start_idx + APPS_PER_PAGE, len(current_entries))
    for offset in range(start_idx, end_idx):
        entry = current_entries[offset]
        slot = offset - start_idx
        x = slot % 3
        y = slot // 3
        pos = (x * 48 + 33, y * 48 + 42)
        try:
            sprite = sprite_for(entry)
            result.append(Icon(pos, entry["name"], slot % APPS_PER_PAGE, sprite))
        except Exception as e:
            print("Error loading icon for {}: {}".format(entry.get("path", ""), e))
    return result


def selected_entry():
    index = current_page * APPS_PER_PAGE + active
    if 0 <= index < len(current_entries):
        return current_entries[index]
    return None


def enter_folder(entry):
    if not is_dir(entry["path"]):
        return
    path_stack.append(entry["path"])
    rebuild_entries(True)


def leave_folder():
    if path_stack:
        path_stack.pop()
    rebuild_entries(True)

MAX_ALPHA = 255
alpha = 30


rebuild_entries(True)


def update():
    global active, icons, alpha, current_page, total_pages

    # process button inputs to switch between icons
    if io.BUTTON_HOME in io.pressed:
        if path_stack:
            path_stack[:] = []
        rebuild_entries(True)
        return None

    move_delta = 0

    if io.BUTTON_C in io.pressed:
        move_delta += 1
    if io.BUTTON_UP in io.pressed:
        move_delta -= 3
    if io.BUTTON_DOWN in io.pressed:
        move_delta += 3

    if io.BUTTON_A in io.pressed:
        move_delta -= 1

    if move_delta:
        active += move_delta
    
    # Handle wrapping and page changes
    page_len = len(icons)
    if page_len == 0:
        active = 0
    else:
        if active >= page_len:
            if current_page < total_pages - 1:
                current_page += 1
                icons = load_page_icons(current_page)
                active = 0
                page_len = len(icons)
            else:
                active = 0
        elif active < 0:
            if current_page > 0:
                current_page -= 1
                icons = load_page_icons(current_page)
                page_len = len(icons)
                active = page_len - 1 if page_len else 0
            else:
                active = page_len - 1

    entry = selected_entry()

    # Launch app or navigate with B
    if io.BUTTON_B in io.pressed:
        if entry:
            if entry["kind"] == "folder":
                enter_folder(entry)
                return None
            if entry["kind"] == "back":
                leave_folder()
                return None
            if entry["kind"] == "app":
                app_path = entry["path"]
                try:
                    if is_dir(app_path) and file_exists("{}/__init__.py".format(app_path)):
                        return app_path
                    print("Error: App {} not found or missing __init__.py".format(entry["name"]))
                except Exception as exc:
                    print("Error launching app {}: {}".format(entry["name"], exc))

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
