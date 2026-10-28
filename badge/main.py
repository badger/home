# Play the cinematic on a normal power-on, but not on the watchdog reset used
# to return to the launcher after an app exits.
import powman
import sys

# Automatically invert directional controls when the badge is flipped upside down
try:
    _badge_mod = sys.modules.get(".frozen/badgeware/badge")
    if _badge_mod is None:
        try:
            import badgeware.badge as _badge_mod
        except ImportError:
            _badge_mod = None

    if _badge_mod is not None:
        _Badge = getattr(_badge_mod, "Badge", None)
        _opp = getattr(_badge_mod, "OPPOSITE_ACTION", None)
        if _Badge is not None and _opp is not None:
            _orig_poll = _Badge.poll

            def _inverted_poll(self):
                _res = _orig_poll(self)
                if self.upside_down():
                    for _ctrl in (self.buttons, self.pad, self.all):
                        _ctrl._held = tuple(_opp.get(_a, _a) for _a in _ctrl._held)
                        _ctrl._pressed = tuple(
                            _opp.get(_a, _a) for _a in _ctrl._pressed
                        )
                        _ctrl._released = tuple(
                            _opp.get(_a, _a) for _a in _ctrl._released
                        )
                        _ctrl._changed = tuple(
                            _opp.get(_a, _a) for _a in _ctrl._changed
                        )
                return _res

            _Badge.poll = _inverted_poll
except Exception as error:  # noqa: BLE001
    print("orientation patch error:", error)

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
