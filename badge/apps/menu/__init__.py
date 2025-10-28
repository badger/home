import sys
import os

sys.path.insert(0, "/system/apps/menu")
os.chdir("/system/apps/menu")

import math
from badgeware import screen, PixelFont, Image, SpriteSheet, is_dir, file_exists, shapes, brushes, io, run
from icon import Icon
import ui

mona = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 11, 1)
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")
# screen.antialias = Image.X2

# Auto-discover apps with __init__.py
apps = []
try:
    for entry in os.listdir("/system/apps"):
        app_path = f"/system/apps/{entry}"
        if is_dir(app_path):
            has_init = file_exists(f"{app_path}/__init__.py")
            if has_init:
                # Skip menu and startup apps
                if entry not in ("menu", "startup"):
                    # Use directory name as display name
                    apps.append((entry, entry))
except Exception as e:
    print(f"Error discovering apps: {e}")

# Pagination constants
APPS_PER_PAGE = 6
current_page = 0
total_pages = max(1, math.ceil(len(apps) / APPS_PER_PAGE))

# find installed apps and create icons for current page
def load_page_icons(page):
    icons = []
    start_idx = page * APPS_PER_PAGE
    end_idx = min(start_idx + APPS_PER_PAGE, len(apps))
    
    for i in range(start_idx, end_idx):
        app = apps[i]
        name, path = app[0], app[1]
        
        if is_dir(f"/system/apps/{path}"):
            icon_idx = i - start_idx
            x = icon_idx % 3
            y = math.floor(icon_idx / 3)
            pos = (x * 48 + 33, y * 48 + 42)
            try:
                # Try to load app-specific icon, fall back to default
                icon_path = f"/system/apps/{path}/icon.png"
                if not file_exists(icon_path):
                    icon_path = "/system/apps/menu/default_icon.png"
                sprite = Image.load(icon_path)
                icons.append(Icon(pos, name, icon_idx % APPS_PER_PAGE, sprite))
            except Exception as e:
                print(f"Error loading icon for {path}: {e}")
    return icons

icons = load_page_icons(current_page)

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
            icons = load_page_icons(current_page)
            active = 0
        else:
            # Wrap to beginning
            active = 0
    elif active < 0:
        if current_page > 0:
            # Move to previous page
            current_page -= 1
            icons = load_page_icons(current_page)
            active = len(icons) - 1
        else:
            # Wrap to end
            active = len(icons) - 1
    
    # Launch app with error handling
    if io.BUTTON_B in io.pressed:
        app_idx = current_page * APPS_PER_PAGE + active
        if app_idx < len(apps):
            app_path = f"/system/apps/{apps[app_idx][1]}"
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
