# This file is copied from /system/main.py to /main.py on first run

import sys
import os
from badgeware import run, io
import machine
import gc
import powman


def _default_app_fallback(module_globals, fallback):
    if fallback:
        return fallback
    module_name = module_globals.get("__name__", "")
    if module_name:
        module_name = module_name.rsplit(".", 1)[-1]
        if module_name and module_name != "__main__":
            return "/system/apps/{}".format(module_name)
    return None


def _prepare_app_path(module_globals, fallback=None):
    app_file = module_globals.get("__file__")
    app_dir = None

    if app_file:
        separator = "/" if "/" in app_file else ("\\" if "\\" in app_file else None)
        if separator:
            app_dir = app_file.rsplit(separator, 1)[0]

    if not app_dir:
        try:
            app_dir = os.getcwd()
        except OSError:
            app_dir = None

    if not app_dir:
        app_dir = _default_app_fallback(module_globals, fallback)

    if app_dir and app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    if app_dir:
        try:
            os.chdir(app_dir)
        except OSError:
            pass

    return app_dir


class _AppRuntimeModule:
    """Runtime helper exposed to apps for path bootstrapping."""


badge_app_runtime = _AppRuntimeModule()
badge_app_runtime.__name__ = "badge_app_runtime"
badge_app_runtime.prepare_app_path = _prepare_app_path
badge_app_runtime.active_path = None

sys.modules["badge_app_runtime"] = badge_app_runtime

SKIP_CINEMATIC = powman.get_wake_reason() == powman.WAKE_WATCHDOG

running_app = None


def quit_to_launcher(pin):
    global running_app
    getattr(running_app, "on_exit", lambda: None)()
    # If we reset while boot is low, bad times
    while not pin.value():
        pass
    machine.reset()


if not SKIP_CINEMATIC:
    startup = __import__("/system/apps/startup")

    run(startup.update)

    if sys.path[0].startswith("/system/apps"):
        sys.path.pop(0)

    del startup

    gc.collect()

menu = __import__("/system/apps/menu")

app = run(menu.update)

if sys.path[0].startswith("/system/apps"):
    sys.path.pop(0)

del menu

# make sure these can be re-imported by the app
del sys.modules["ui"]
del sys.modules["icon"]

gc.collect()

# Don't pass the b press into the app
while io.held:
    io.poll()

machine.Pin.board.BUTTON_HOME.irq(
    trigger=machine.Pin.IRQ_FALLING, handler=quit_to_launcher
)

sys.path.insert(0, app)
os.chdir(app)
badge_app_runtime.active_path = app

running_app = __import__(app)

getattr(running_app, "init", lambda: None)()

run(running_app.update)

# Unreachable, in theory!
machine.reset()

