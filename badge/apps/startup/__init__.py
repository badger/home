import sys
import os

sys.path.insert(0, "/system/apps/startup")
os.chdir("/system/apps/startup")

from badgeware import io, screen, run, brushes, shapes, display

# animation settings
animation_duration = 3
fade_duration = 0.75
frame_count = 159
hold_frame = 113

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


def update():
    global button_pressed_at, ticks_start

    if ticks_start is None:
        ticks_start = io.ticks

    time = (io.ticks - ticks_start) / 1000  # execution time in seconds

    frame, alpha = hold_frame, 255

    # determine which phase of the animation we're in (animation, hold, or fadeout)
    if time < animation_duration:
        # calculate which frame we're on and display it
        frame = round((time / animation_duration) * hold_frame)
    else:
        # if the startup animation has completed then check if the user has pressed a button
        if io.pressed:
            button_pressed_at = time

    if button_pressed_at:
        time_since_pressed = time - button_pressed_at
        if time_since_pressed < fade_duration:
            # calculate which frame we're on and display it
            frame = (
                round((time_since_pressed / fade_duration) * (frame_count - hold_frame))
                + hold_frame
            )
            alpha = 255 - ((time_since_pressed / fade_duration) * 255)
        else:
            # Return control to the menu
            screen.brush = brushes.color(0, 0, 0)
            screen.draw(CLEAR)
            display.update()
            return False

    show_frame(frame, alpha)
    return None


if __name__ == "__main__":
    run(update)
