import sys
import os

sys.path.insert(0, "/system/apps/copilot-cli-loop")
os.chdir("/system/apps/copilot-cli-loop")

from badgeware import Image, screen, run, io



frame_index = 0
last_frame_time = 0
FRAME_DURATION = 33  # ~1/30th of a second in milliseconds (33.33ms)

def update():
    global frame_index, last_frame_time
    
    # Update frame every ~33ms (30 fps)
    if io.ticks - last_frame_time >= FRAME_DURATION:
        frame_index = (frame_index + 1) % 119
        if frame_index == 0:
            frame_index = 1 
        last_frame_time = io.ticks
        
    # Draw the current frame
    screen.blit(Image.load(f"frames/frame_{frame_index:04d}.png"), 0, 0)
    
if __name__ == "__main__":
    run(update)

