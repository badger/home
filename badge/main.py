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
        _Controls = getattr(_badge_mod, "Controls", None)
        _opp = getattr(_badge_mod, "OPPOSITE_ACTION", None)

        if _Badge is not None and _opp is not None:
            def _make_inverter(orig_fn):
                def _inverted(self, button=None):
                    if button is not None:
                        if self.rotate_180() and button in _opp:
                            button = _opp[button]
                        return orig_fn(self, button)
                    res = orig_fn(self)
                    if self.rotate_180():
                        return tuple(_opp.get(_b, _b) for _b in res)
                    return res
                return _inverted

            for _method in ("pressed", "held", "released", "changed"):
                if hasattr(_Badge, _method):
                    setattr(_Badge, _method, _make_inverter(getattr(_Badge, _method)))

        if _Controls is not None and _opp is not None:
            def _make_ctrl_inverter(orig_fn):
                def _ctrl_inverted(self, button=None):
                    if button is not None:
                        if badge.rotate_180() and button in _opp:
                            button = _opp[button]
                        return orig_fn(self, button)
                    res = orig_fn(self)
                    if badge.rotate_180():
                        return tuple(_opp.get(_b, _b) for _b in res)
                    return res
                return _ctrl_inverted

            for _method in ("pressed", "held", "released", "changed"):
                if hasattr(_Controls, _method):
                    setattr(_Controls, _method, _make_ctrl_inverter(getattr(_Controls, _method)))

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
