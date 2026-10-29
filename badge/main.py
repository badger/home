# Play the cinematic on a normal power-on, but not on the watchdog reset used
# to return to the launcher after an app exits.
import powman

_opposite = {
    BUTTON_UP: BUTTON_DOWN,
    BUTTON_DOWN: BUTTON_UP,
    BUTTON_LEFT: BUTTON_RIGHT,
    BUTTON_RIGHT: BUTTON_LEFT,
}

_poll = badge.poll
_held = set(badge.all.held())


def poll_controls():
    global _held
    result = _poll()
    buttons = badge.buttons.held()
    # Touch controls already follow the display rotation; edge switches do not.
    if badge.rotate_180():
        buttons = (_opposite.get(action, action) for action in buttons)
    held = set(buttons) | set(badge.pad.held())
    badge.all.set_state(held, held - _held, _held - held, held ^ _held)
    _held = held
    return result


badge.poll = poll_controls

wake_reason = powman.get_wake_reason()

if wake_reason == powman.WAKE_DOUBLETAP:
    import _msc
elif wake_reason != powman.WAKE_WATCHDOG:
    # Try /system/startup (standard firmware location) or /system/apps/startup
    _startup_path = None
    for _path in ("/system/startup", "/system/apps/startup"):
        try:
            if file_exists(_path):
                _startup_path = _path
                break
        except Exception:
            pass

    if _startup_path is not None:
        try:
            launch(_startup_path)
        except Exception as error:
            print("startup cinematic error:", error)

# Eat the wakeup button press to prevent it leaking into the menu
badge.poll()
while badge.pressed() or badge.held() or badge.released():
    badge.poll()

# We expect a launcher menu to be at /system/apps/menu
# (temporarily auto-launching the world app for rasteriser testing)
app_to_launch = launch("/system/apps/menu")

# Stopping in Thonny can cause launch("/system/apps/menu") to return None
if app_to_launch is not None:

    # Don't pass menu button presses into the newly launched app
    while badge.pressed() or badge.held() or badge.released():
        badge.poll()

    launch(app_to_launch)

# Catch any exit and reset back to the launcher
reset()
