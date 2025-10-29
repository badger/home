import sys
import os

sys.path.insert(0, "/system/apps/startup")
os.chdir("/system/apps/startup")

from badgeware import io, screen, run, brushes, shapes, display, Image

# animation settings
animation_duration = 3
fade_duration = 0.75
frame_count = 159
hold_frame = 113

# image display phase
image_phase = False
startup_image = None

# render the specified frame from the animation
current_frame = None
current_frame_filename = None

ticks_start = None

CLEAR = shapes.rectangle(0, 0, screen.width, screen.height)


def show_frame(i, alpha=255):
    # check if this frame needs loading
    global current_frame, current_frame_filename
    filename = f"frames/intro_{i:05d}.png"
    screen.load_into(filename)

    screen.brush = brushes.color(0, 0, 0, 255 - alpha)
    screen.draw(CLEAR)

    # render the frame
    current_frame_filename = filename


button_pressed_at = None


def load_startup_image():
    global startup_image
    if startup_image is None:
        try:
            startup_image = Image.load("assets/thorin-megabot.png")
        except OSError:
            # If image doesn't exist, we'll skip the image phase
            pass


def update():
    global button_pressed_at, ticks_start, image_phase

    if ticks_start is None:
        ticks_start = io.ticks

    time = (io.ticks - ticks_start) / 1000  # execution time in seconds

    frame, alpha = hold_frame, 255

    # determine which phase we're in
    if time < animation_duration:
        # Animation phase: calculate which frame we're on and display it
        frame = round((time / animation_duration) * hold_frame)
        show_frame(frame, alpha)
    elif not image_phase:
        # Animation completed, start image phase
        image_phase = True
        load_startup_image()
        
        # Clear screen and show the image
        screen.brush = brushes.color(0, 0, 0)
        screen.draw(CLEAR)
        
        if startup_image:
            # Center the image on screen
            x = (screen.width - startup_image.width) // 2
            y = (screen.height - startup_image.height) // 2
            screen.blit(startup_image, x, y)
    elif image_phase:
        # Image phase: wait for button press
        if io.pressed:
            button_pressed_at = time
        
        # Keep displaying the image
        screen.brush = brushes.color(0, 0, 0)
        screen.draw(CLEAR)
        
        if startup_image:
            # Center the image on screen
            x = (screen.width - startup_image.width) // 2
            y = (screen.height - startup_image.height) // 2
            screen.blit(startup_image, x, y)

    # Handle fadeout after button press
    if button_pressed_at:
        time_since_pressed = time - button_pressed_at
        if time_since_pressed < fade_duration:
            # Fade out effect
            alpha = 255 - ((time_since_pressed / fade_duration) * 255)
            screen.brush = brushes.color(0, 0, 0, 255 - alpha)
            screen.draw(CLEAR)
        else:
            # Return control to the menu
            screen.brush = brushes.color(0, 0, 0)
            screen.draw(CLEAR)
            display.update()
            return False

    return None


if __name__ == "__main__":
    run(update)
