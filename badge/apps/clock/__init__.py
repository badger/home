import sys
import os

sys.path.insert(0, "/system/apps/clock")
os.chdir("/system/apps/clock")

from badgeware import PixelFont, screen, brushes, shapes, run, io, network
from urllib.urequest import urlopen
import json

# Fonts and colors
font = PixelFont.load("/system/assets/fonts/absolute.ppf")
try:
    small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
except Exception:
    small_font = font
white = brushes.color(255, 255, 255)
faded = brushes.color(235, 245, 255, 120)
black = brushes.color(0, 0, 0)
phosphor = brushes.color(211, 250, 55)


def draw_background():
    screen.brush = black
    screen.draw(shapes.rectangle(0, 0, 160, 120))


def update():
    global network
    
    # Clear background
    draw_background()
    
    # Check Wi-Fi status
    try:
        wlan = network.WLAN(network.STA_IF)
        wifi_connected = wlan.isconnected()
        status = "wifi connected" if wifi_connected else "no wifi"
    except Exception as e:
        status = f"error: {e}"
    
    # Draw status at bottom
    screen.font = small_font
    screen.brush = phosphor
    w, _ = screen.measure_text(status)
    screen.text(status, 80 - (w / 2), 60)
    
    return None


if __name__ == "__main__":
    run(update)
