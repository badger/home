# Play the cinematic on a normal power-on, but not on the watchdog reset used
# to return to the launcher after an app exits.
import powman

wake_reason = powman.get_wake_reason()

if wake_reason == powman.WAKE_DOUBLETAP:
    import _msc
elif wake_reason != powman.WAKE_WATCHDOG:
    launch("/system/apps/startup")

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
