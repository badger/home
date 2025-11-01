import sys
import os

sys.path.insert(0, "/system/apps/gallery")
os.chdir("/system/apps/gallery")

from badgeware import PixelFont, Image, screen, run, io, brushes, shapes
import jpegdec
import pngdec

screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
screen.antialias = Image.X2

# Create decoders
jpeg = jpegdec.JPEG(screen)
png = pngdec.PNG(screen)

# Build list of image files
files = []
try:
    for file in os.listdir("images"):
        if file.startswith("."):
            continue
        name, ext = file.rsplit(".", 1)
        if ext.lower() in ["png", "jpg", "jpeg"]:
            files.append({
                "name": file,
                "title": name.replace("-", " ").replace("_", " ")
            })
except OSError:
    pass

# Ensure we have at least one entry
if not files:
    files.append({"name": None, "title": "No images found"})

index = 0
error = None
ui_hidden = False
image_changed_at = None


def clamp_index(i):
    return i % len(files)


def load_image(i):
    global error
    i = clamp_index(i)
    
    if files[i]["name"] is None:
        error = "No images in images/"
        return
    
    filename = files[i]["name"]
    filepath = f"images/{filename}"
    
    try:
        # Clear screen first
        screen.brush = brushes.color(0, 0, 0)
        screen.clear()
        
        if filename.lower().endswith('.png'):
            # Handle PNG files
            png.open_file(filepath)
            png.decode(0, 0)
        else:
            # Handle JPEG files
            jpeg.open_file(filepath)
            
            # Get dimensions and center
            img_width = jpeg.get_width()
            img_height = jpeg.get_height()
            x = max(0, (160 - img_width) // 2)
            y = max(0, (120 - img_height) // 2)
            
            jpeg.decode(x, y)
        
        error = None
    except OSError as e:
        error = f"File error: {e}"
    except Exception as e:
        error = f"Load failed: {e}"


# Load first image
load_image(index)


def update():
    global index, ui_hidden, image_changed_at
    
    # Initialize timer on first frame
    if image_changed_at is None and not error:
        image_changed_at = io.ticks
    
    # Navigation
    navigated = False
    if io.BUTTON_UP in io.pressed:
        index -= 1
        navigated = True
        ui_hidden = False
        image_changed_at = io.ticks
    
    if io.BUTTON_DOWN in io.pressed:
        index += 1
        navigated = True
        ui_hidden = False
        image_changed_at = io.ticks
    
    # Auto-hide UI after 3 seconds
    if image_changed_at and (io.ticks - image_changed_at) > 3000:
        ui_hidden = True
    
    # Load/redraw image when navigating or when UI visibility changes
    if navigated:
        load_image(index)
    elif not error:
        # Redraw to clear old title overlay when hiding
        screen.brush = brushes.color(0, 0, 0)
        screen.clear()
        
        # Redecode the current image
        filename = files[clamp_index(index)]["name"]
        if filename:
            filepath = f"images/{filename}"
            try:
                if filename.lower().endswith('.png'):
                    png.open_file(filepath)
                    png.decode(0, 0)
                else:
                    jpeg.open_file(filepath)
                    img_width = jpeg.get_width()
                    img_height = jpeg.get_height()
                    x = max(0, (160 - img_width) // 2)
                    y = max(0, (120 - img_height) // 2)
                    jpeg.decode(x, y)
            except:
                pass
    
    # Draw error if present
    if error:
        screen.brush = brushes.color(0, 0, 0)
        screen.clear()
        
        # Simple error display
        screen.brush = brushes.color(255, 100, 100)
        screen.text("Error:", 10, 40)
        screen.brush = brushes.color(255, 255, 255)
        
        # Word wrap error message
        words = error.split()
        line = ""
        y = 55
        for word in words:
            test = line + (" " if line else "") + word
            if len(test) > 20:
                screen.text(line, 10, y)
                line = word
                y += 12
                if y > 100:
                    break
            else:
                line = test
        if line and y <= 100:
            screen.text(line, 10, y)
    
    # Draw title overlay (only if not hidden)
    if not ui_hidden:
        title = files[clamp_index(index)]["title"]
        width, _ = screen.measure_text(title)
        
        screen.brush = brushes.color(0, 0, 0, 150)
        screen.draw(shapes.rounded_rectangle(
            80 - (width / 2) - 8, -6, width + 16, 22, 6))
        
        screen.brush = brushes.color(255, 255, 255)
        screen.text(title, 80 - (width / 2), 0)



if __name__ == "__main__":
    run(update)
