import os
import sys


def _default_app_fallback(module_globals, fallback):
    if fallback:
        return fallback
    module_name = module_globals.get("__name__", "")
    if module_name:
        module_name = module_name.rsplit(".", 1)[-1]
        if module_name and module_name != "__main__":
            return "/system/apps/{}".format(module_name)
    return None


def prepare_app_path(module_globals, fallback=None):
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


active_path = None
