import sys
import os

from badgeware import screen, PixelFont, shapes, brushes, run

# Load a cool font
font = PixelFont.load("/system/assets/fonts/absolute.ppf")

def update():
    # Clear the screen with black background
    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Set up white text
    screen.brush = brushes.color(255, 255, 255)
    screen.font = font
    
    # Draw "hello world" centered on screen
    text = "hello world"
    w, h = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), 60 - (h / 2))
    
    return None

if __name__ == "__main__":
    run(update)
