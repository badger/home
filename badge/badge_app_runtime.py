import os
import sys


_CACHE_KEY = "__badge_app_runtime_dir"


def _normalize_path(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    value = str(value)
    value = value.replace("\\", "/")
    if value.endswith("/") and value != "/":
        value = value[:-1]
    return value or None


def _parent_dir(path):
    path = _normalize_path(path)
    if not path:
        return None
    slash = path.rfind("/")
    if slash == -1:
        return None
    if slash == 0:
        return "/"
    return path[:slash]


def _dir_exists(path):
    if not path:
        return False
    try:
        os.listdir(path)
        return True
    except OSError:
        return False


def _default_app_dir(module_globals, fallback):
    module_name = module_globals.get("__name__", "")
    if not module_name or module_name == "__main__":
        return _normalize_path(fallback)
    tail = module_name.rsplit(".", 1)[-1]
    base = _normalize_path(fallback)
    if base and base.endswith(tail):
        return base
    if base:
        return base
    return "/system/apps/{}".format(tail)


def ensure_app_path(module_globals, fallback=None):
    cached = module_globals.get(_CACHE_KEY)
    if cached:
        return cached

    candidates = []

    def add_candidate(path):
        path = _normalize_path(path)
        if path and path not in candidates:
            candidates.append(path)

    add_candidate(_parent_dir(module_globals.get("__file__")))

    module_spec = module_globals.get("__spec__")
    if module_spec is not None:
        add_candidate(_parent_dir(getattr(module_spec, "origin", None)))

    if sys.path:
        add_candidate(sys.path[0])

    add_candidate(_default_app_dir(module_globals, fallback))

    app_dir = None
    for candidate in candidates:
        if not candidate:
            continue
        if _dir_exists(candidate):
            app_dir = candidate
            break
        if app_dir is None:
            app_dir = candidate

    if app_dir and app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    if app_dir:
        try:
            os.chdir(app_dir)
        except OSError:
            # It is safe to ignore errors when changing directory; app_dir may not exist or be accessible,
            # but we still want to proceed with app path setup for compatibility.
            pass

    module_globals[_CACHE_KEY] = app_dir
    return app_dir


def prepare_app_path(module_globals, fallback=None):
    """Backward-compatible wrapper for older apps."""
    return ensure_app_path(module_globals, fallback)


active_path = None
