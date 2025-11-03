import sys

if "/system" not in sys.path:
    sys.path.insert(0, "/system")

try:
    from badge_app_runtime import ensure_app_path
except ImportError:
    from badge_app_runtime import prepare_app_path as ensure_app_path

APP_DIR = ensure_app_path(globals(), "/system/apps/copilot-loop")

from badgeware import io, run, screen, Image, PixelFont, SpriteSheet


frame_index = 1
last_frame_time = 0
FRAME_DURATION = 33  # ~1/30th of a second in milliseconds (33.33ms)
LAST_FRAME_PAUSE = 10000  # 10 seconds in milliseconds
TOTAL_FRAMES = 39

def update():
    global frame_index, last_frame_time
    
    is_last_frame = (frame_index == TOTAL_FRAMES)
    pause_duration = LAST_FRAME_PAUSE if is_last_frame else FRAME_DURATION
    
    # Update frame with appropriate timing
    if io.ticks - last_frame_time >= pause_duration:
        frame_index = (frame_index % TOTAL_FRAMES) + 1
        last_frame_time = io.ticks
        
    # Draw the current frame
    screen.blit(Image.load(f"frames/frame_{frame_index:04d}.png"), 0, 0)
    
if __name__ == "__main__":
    run(update)

