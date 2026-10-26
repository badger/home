"""Host-side tests for The Octocat Trail (badge/apps/octocat_trail).

The app's modules load under unique names (octocat_trail_<module>) so they
never collide with other apps' modules in one test process. Every
sys.modules entry touched while loading is restored afterwards, and badge
runtime globals are patched onto the app modules, never onto builtins.
"""

import ast
import importlib.util
import io
import re
import sys
import tokenize
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "octocat_trail"
MODULES = ("trail_map", "trail_logic")
_MISSING = object()


def load_modules(prefix="octocat_trail_", extra=None, names=MODULES):
    """Load app modules as prefix + name. While loading, the plain names
    point at the new modules so the app's own `import trail_logic as tl`
    lines resolve; afterwards sys.modules is restored exactly."""
    patch = {"aye_arr": None}
    if extra:
        patch.update(extra)
    saved = {}
    loaded = {}
    flag = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for key, value in patch.items():
            saved.setdefault(key, sys.modules.get(key, _MISSING))
            sys.modules[key] = value
        for name in names:
            spec = importlib.util.spec_from_file_location(prefix + name, APP / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            saved.setdefault(name, sys.modules.get(name, _MISSING))
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
    finally:
        for key, value in saved.items():
            if value is _MISSING:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
        sys.dont_write_bytecode = flag
    return loaded


_APP = load_modules()
tl = _APP["trail_logic"]


class LoaderTests(unittest.TestCase):
    def test_modules_load_under_unique_names_without_leaking(self):
        for name in MODULES:
            self.assertEqual(_APP[name].__name__, "octocat_trail_" + name)
            self.assertIsNot(sys.modules.get(name), _APP[name])
            self.assertIsNot(sys.modules.get("octocat_trail_" + name), _APP[name])


class QuietRng(tl.Rng):
    """Deterministic test RNG. chance() follows a script, then answers False;
    randint() follows a script, then returns low; choice() takes the first
    item; uniform() returns low. Every chance() probability is recorded."""

    def __init__(self, chances=(), randints=()):
        tl.Rng.__init__(self, 99)
        self.chances = list(chances)
        self.randints = list(randints)
        self.asked = []

    def chance(self, probability):
        self.asked.append(probability)
        return self.chances.pop(0) if self.chances else False

    def randint(self, low, high):
        if self.randints:
            value = self.randints.pop(0)
            if not low <= value <= high:
                raise AssertionError("scripted randint %r outside %r..%r" % (value, low, high))
            return value
        return low

    def uniform(self, low, high):
        return low

    def choice(self, items):
        return items[0]


def stocked(role=0, rng=None, brew=200.0, lgtm=50, patches=0):
    trail = tl.Trail(role, rng or QuietRng())
    trail.supplies["brew"] = brew
    trail.supplies["lgtm"] = lgtm
    trail.supplies["patches"] = patches
    return trail


class HelperTests(unittest.TestCase):

    def test_number_formatting(self):
        self.assertEqual(tl.commas(0), "0")
        self.assertEqual(tl.commas(999), "999")
        self.assertEqual(tl.commas(1000), "1,000")
        self.assertEqual(tl.commas(1234567), "1,234,567")
        self.assertEqual(tl.commas(-1234), "-1,234")
        self.assertEqual(tl.tenths(35), "3.5")
        self.assertEqual(tl.tenths(140), "14.0")
        self.assertEqual(tl.plural(1, "day"), "1 day")
        self.assertEqual(tl.plural(0, "keg"), "0 kegs")
        self.assertEqual(tl.plural(2, "patch", "es"), "2 patches")

    def test_clamps(self):
        self.assertEqual(tl.clamp(5, 0, 3), 3)
        self.assertEqual(tl.clamp(-1, 0, 3), 0)
        self.assertEqual(tl.clamp(2, 0, 3), 2)
        self.assertEqual(tl.clamp_int("7", 0, 5), 5)
        self.assertEqual(tl.clamp_int(3.9, 0, 9), 3)
        self.assertEqual(tl.clamp_int(None, 1, 9), 1)
        self.assertEqual(tl.clamp_int("x", 1, 9, 4), 4)
        self.assertEqual(tl.clamp_int(float("inf"), 0, 9), 0)

    def test_fnv1a_is_deterministic(self):
        self.assertEqual(tl.fnv1a(""), 0x811C9DC5)
        self.assertEqual(tl.fnv1a("a"), 0xE40C292C)
        self.assertEqual(tl.fnv1a(12), tl.fnv1a("12"))
        self.assertNotEqual(tl.fnv1a("wx1"), tl.fnv1a("wx2"))

    def test_wrap(self):
        self.assertEqual(tl.wrap("aa bb cc", 5, len), ["aa bb", "cc"])
        self.assertEqual(tl.wrap("a\n\nb", 10, len), ["a", "", "b"])
        self.assertEqual(tl.wrap("superlongword x", 4, len), ["superlongword", "x"])
        self.assertEqual(tl.wrap("  a  b ", 10, len), ["a b"])
        self.assertEqual(tl.wrap("", 10, len), [""])

    def test_store_items(self):
        self.assertEqual(tl.store_item("brew")[1], 4)
        self.assertEqual(tl.carry_limit("patches"), 9)
        with self.assertRaises(KeyError):
            tl.store_item("credits")


class RngTests(unittest.TestCase):
    def test_xorshift_sequence_is_portable(self):
        # Pure masked integer arithmetic, so the badge draws the same values.
        rng = tl.Rng(1)
        self.assertEqual([rng.next32() for _ in range(3)], [270369, 67634689, 2647435461])
        self.assertEqual(tl.Rng(0).state, 0x6D2B79F5)
        self.assertEqual(tl.Rng(1 << 32).state, 0x6D2B79F5)

    def test_same_seed_same_draws(self):
        a = tl.Rng(42)
        b = tl.Rng(42)
        self.assertEqual([a.randint(0, 9) for _ in range(50)], [b.randint(0, 9) for _ in range(50)])

    def test_ranges(self):
        rng = tl.Rng(7)
        seen = set()
        for _ in range(2000):
            value = rng.randint(3, 6)
            self.assertTrue(3 <= value <= 6)
            seen.add(value)
            self.assertTrue(0.0 <= rng.random() < 1.0)
            self.assertTrue(2.0 <= rng.uniform(2.0, 4.0) <= 4.0)
            self.assertIn(rng.choice("abc"), "abc")
        self.assertEqual(seen, {3, 4, 5, 6})
        self.assertFalse(any(rng.chance(0.0) for _ in range(200)))
        self.assertTrue(all(rng.chance(1.0) for _ in range(200)))

    def test_weighted(self):
        rng = tl.Rng(3)
        self.assertIsNone(rng.weighted(((0, "a"),)))
        self.assertIsNone(rng.weighted(()))
        for _ in range(100):
            self.assertEqual(rng.weighted(((0, "a"), (2, "b"))), "b")
        self.assertEqual(set(rng.weighted(((1, "a"), (1, "b"))) for _ in range(200)), {"a", "b"})


class TrailTests(unittest.TestCase):

    def test_calendar(self):
        trail = tl.Trail(0, QuietRng())
        expected = ((1, "September 1, 2026", "Tue"), (4, "September 4, 2026", "Fri"),
                    (122, "December 31, 2026", "Thu"), (123, "January 1, 2027", "Fri"),
                    (366, "September 1, 2027", "Wed"))
        for day, text, weekday in expected:
            trail.day = day
            self.assertEqual(trail.date_text(), text)
            self.assertEqual(trail.weekday(), weekday)
            self.assertIn(trail.weather(), tl.WEATHER)
            self.assertEqual(trail.weather(), trail.weather())


class TrailShopRiverTests(unittest.TestCase):
    def test_store_prices(self):
        trail = stocked()
        for stop, prices in ((0, (4, 1, 25)), (1, (5, 2, 32)), (9, (6, 2, 38))):
            trail.at = stop
            self.assertTrue(trail.at_store())
            self.assertEqual(trail.store_keys(), ("brew", "lgtm", "patches"))
            self.assertEqual(tuple(trail.price(key) for key in ("brew", "lgtm", "patches")), prices)
        trail.at = 2
        self.assertEqual((trail.at_store(), trail.markup(), trail.price("brew")), (False, 0, 4))


class FakeDevice:
    """Stands in for the runtime `badge` object's sensor and light calls."""

    def __init__(self, imu=(0, 16384, 0, 0, 0, 0), light=40000, lights_error=None):
        self.imu_value = imu
        self.light_value = light
        self.lights_error = lights_error
        self.lights = []

    def imu(self):
        if isinstance(self.imu_value, Exception):
            raise self.imu_value
        return self.imu_value

    def light_level(self):
        if isinstance(self.light_value, Exception):
            raise self.light_value
        return self.light_value

    def caselights(self, *values):
        if self.lights_error:
            raise self.lights_error
        self.lights.append(values)
        return list(values)


# ----- the renderer, through strict fakes of the badge drawing globals --------------------------

def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class DrawLog:
    """Misuse of the badge drawing API seen by the fakes below."""

    def __init__(self):
        self.problems = []
        self.images = []
        self.colors = 0

    def bad(self, message):
        if len(self.problems) < 20:
            self.problems.append(message)


class FakePen:
    def __init__(self, r, g, b):
        self.rgb = (r, g, b)


class FakeShape:
    def __init__(self, log, kind, args):
        self.log = log
        self.kind = kind
        if not all(is_int(value) for value in args):
            log.bad("%s%r: non-integer argument" % (kind, args))

    def stroke(self, width):
        if not is_int(width) or width <= 0:
            self.log.bad("%s.stroke(%r)" % (self.kind, width))
        return self


class FakeBox:
    """What the rect() and vec2() globals return."""

    def __init__(self, log, kind, args):
        self.kind = kind
        self.args = args
        if not all(is_int(value) for value in args):
            log.bad("%s%r: non-integer argument" % (kind, args))


def text_width(text):
    """Rough pixel-font metrics: spaces are 2 px, everything else 7 px."""
    width = 0
    for char in text:
        width += 2 if char == " " else 7
    return width


class FakeSurface:
    """The screen or an offscreen image, checking every drawing call."""

    def __init__(self, log, width, height, is_screen=False):
        self.log = log
        self.width = width
        self.height = height
        self.is_screen = is_screen
        self.font = None
        self.antialias = None
        self.fill_rule = None
        self.calls = 0
        self.texts = []
        self.off_screen = []
        self._pen = None

    @property
    def pen(self):
        return self._pen

    @pen.setter
    def pen(self, value):
        if not isinstance(value, FakePen):
            self.log.bad("pen = %r" % (value,))
        self._pen = value

    def inked(self, what):
        self.calls += 1
        if self._pen is None:
            self.log.bad(what + " without a pen")

    def clear(self):
        self.inked("clear")

    def rectangle(self, *args):
        self.inked("rectangle")
        if len(args) != 4 or not all(is_int(value) for value in args):
            self.log.bad("rectangle%r" % (args,))
        elif args[2] <= 0 or args[3] <= 0:
            self.log.bad("empty rectangle%r" % (args,))

    def shape(self, value):
        self.inked("shape")
        if not isinstance(value, FakeShape):
            self.log.bad("shape(%r)" % (value,))

    def text(self, text, x, y):
        self.inked("text")
        if not isinstance(text, str) or not is_int(x) or not is_int(y):
            self.log.bad("text(%r, %r, %r)" % (text, x, y))
            return
        if self.font is None:
            self.log.bad("text without a font")
        words = " ".join(text.split())
        if self.is_screen and len(words) > 1:
            self.texts.append(words)
            right = x + text_width(text)
            if x < -1 or right > self.width + 1 or y < -2 or y + 12 > self.height + 2:
                self.off_screen.append((words, x, y))

    def measure_text(self, text):
        if not isinstance(text, str):
            self.log.bad("measure_text(%r)" % (text,))
        return (text_width(text), 12)

    def blit(self, source, target):
        self.calls += 1
        if not isinstance(source, FakeSurface) or source.is_screen:
            self.log.bad("blit source %r" % (source,))
        if not isinstance(target, FakeBox):
            self.log.bad("blit target %r" % (target,))


# ----- the launcher (__init__.py), run against fake runtime globals -----------------------------

class LauncherBadge(FakeDevice):
    """The runtime `badge` object as the launcher uses it."""

    def __init__(self, **kw):
        FakeDevice.__init__(self, **kw)
        self.ticks = 5000
        self.default_clear = "default-clear"
        self.modes = []
        self.down = set()
        self.holding = set()
        self.key_error = None

    def mode(self, value):
        self.modes.append(value)

    def pressed(self, button):
        if self.key_error:
            raise self.key_error
        return button in self.down

    def held(self, button):
        if self.key_error:
            raise self.key_error
        return button in self.holding


# ---------------------------------------------------------------------------
# Source scan: a CPython stand-in for the badge's MicroPython 1.29, so CI
# catches APIs and syntax that pass unittest but crash on the badge.
# ---------------------------------------------------------------------------

# Missing on the badge, or avoided here: datetime, abc and pathlib are unverified on the
# device, and re silently differs (no \b, {m,n} or .span()).
FORBIDDEN_MODULES = frozenset((
    "__future__", "abc", "bisect", "colorsys", "contextlib", "dataclasses", "datetime", "decimal",
    "enum", "fractions", "numbers", "pathlib", "re", "shutil", "statistics", "subprocess",
    "textwrap", "threading", "traceback", "typing", "typing_extensions", "urllib", "uuid", "warnings",
))
# Port modules the simulator lacks, plus hardware this app only reaches through a fallback.
GUARDED_MODULES = frozenset((
    "_thread", "aye_arr", "badgelink", "badgeware.ir", "badgeware.link", "cryptolib", "machine",
    "network", "powman", "rp2", "socket", "ssl", "urequests", "usocket", "ussl",
))
IMPORT_GUARDS = ("ImportError", "Exception", "BaseException")
MISSING_ATTRS = {
    "collections": ("Counter", "ChainMap"),
    "functools": ("lru_cache", "cache", "cmp_to_key", "total_ordering", "cached_property", "singledispatch"),
    "hashlib": ("md5", "sha1"),
    "itertools": ("product", "permutations", "combinations", "combinations_with_replacement", "groupby",
                  "zip_longest", "takewhile", "dropwhile", "compress", "pairwise", "batched", "filterfalse"),
    "json": ("JSONDecodeError",),
    "math": ("hypot", "dist", "prod", "gcd", "lcm", "isqrt", "comb", "perm", "fsum", "cbrt", "exp2"),
    "micropython": ("native", "viper"),
    "operator": ("itemgetter", "methodcaller"),
    "os": ("makedirs", "environ", "walk", "scandir", "replace", "fsync", "getenv", "urandom", "sync"),
    "os.path": ("splitext", "getsize", "getmtime", "realpath", "expanduser", "isabs"),
    "random": ("Random", "SystemRandom", "shuffle", "sample", "choices", "gauss", "triangular", "expovariate"),
    "struct": ("iter_unpack",),
    "sys": ("exc_info", "getsizeof", "setrecursionlimit"),
    "time": ("monotonic", "perf_counter", "process_time", "strftime"),
}
MISSING_NAMES = frozenset((
    "BlockingIOError", "BrokenPipeError", "BufferError", "ChildProcessError", "ConnectionAbortedError",
    "ConnectionError", "ConnectionRefusedError", "ConnectionResetError", "EnvironmentError",
    "ExceptionGroup", "FileExistsError", "FileNotFoundError", "FloatingPointError", "IOError",
    "InterruptedError", "IsADirectoryError", "ModuleNotFoundError", "NotADirectoryError",
    "PermissionError", "ProcessLookupError", "RecursionError", "ReferenceError", "TabError",
    "TimeoutError", "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError",
    "__builtins__", "__doc__", "__qualname__", "aiter", "anext", "ascii", "breakpoint", "exit",
    "format", "quit", "vars",
))
MISSING_METHODS = frozenset((
    "_asdict", "_replace", "bit_count", "bit_length", "capitalize", "casefold", "expandtabs",
    "format_map", "from_iterable", "groupdict", "groups", "hexdigest", "is_integer", "isalnum",
    "isascii", "isdecimal", "isidentifier", "isnumeric", "isprintable", "ljust", "move_to_end",
    "removeprefix", "removesuffix", "rjust", "span", "swapcase", "title", "zfill",
))
MISSING_OBJECT_ATTRS = frozenset(("__doc__", "__qualname__", "__traceback__", "maxlen"))
BAD_KEYWORDS = {"int": ("base",), "open": ("newline", "errors"), "print": ("flush",), "range": None,
                "round": ("ndigits",), "sum": ("start",), "zip": ("strict",)}
ALLOWED_KEYWORDS = {("collections", "deque"): (), ("collections", "namedtuple"): (),
                    ("json", "dump"): ("separators",), ("json", "dumps"): ("separators",),
                    ("json", "load"): (), ("json", "loads"): ()}


def within(name, table):
    parts = name.split(".")
    return any(".".join(parts[:end]) in table for end in range(1, len(parts) + 1))


def catches_imports(handler):
    if handler.type is None:
        return True
    kinds = handler.type.elts if isinstance(handler.type, ast.Tuple) else (handler.type,)
    return any(isinstance(kind, ast.Name) and kind.id in IMPORT_GUARDS for kind in kinds)


def bound_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


def is_text(node):
    return isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)))


def names_trail_address(node):
    return (isinstance(node, ast.Name) and node.id == "IR_ADDRESS") or (
        isinstance(node, ast.Attribute) and node.attr == "IR_ADDRESS")


def field_access(text):
    from string import Formatter
    try:
        fields = [field for _literal, field, _spec, _conversion in Formatter().parse(text) if field]
    except ValueError:
        return False
    return any("." in field or "[" in field for field in fields)


class BadgeScan(ast.NodeVisitor):
    """Flags code that CPython accepts but the badge's MicroPython 1.29 rejects."""

    def __init__(self, tree):
        self.problems = []
        self.aliases = {}
        self.bound = bound_names(tree)
        self.guarded = [False]

    def flag(self, node, message):
        self.problems.append("line %d: %s" % (getattr(node, "lineno", 0), message))

    def resolve(self, node):
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self.resolve(node.value)
            if base and ":" not in base:
                return base + "." + node.attr
        return None

    def call_target(self, func):
        if isinstance(func, ast.Attribute):
            base = self.resolve(func.value)
            if base and ":" not in base:
                return base, func.attr
        elif isinstance(func, ast.Name):
            alias = self.aliases.get(func.id, "")
            if ":" in alias:
                return tuple(alias.split(":", 1))
        return None

    # Only a try body whose handlers catch ImportError guards an import, and a function
    # body runs later, outside any try around its def.
    def visit_Try(self, node):
        self.guarded.append(self.guarded[-1] or any(catches_imports(handler) for handler in node.handlers))
        for statement in node.body:
            self.visit(statement)
        self.guarded.pop()
        for part in node.handlers + node.orelse + node.finalbody:
            self.visit(part)

    def visit_TryStar(self, node):
        self.flag(node, "except* is a SyntaxError on the badge")
        self.visit_Try(node)

    def visit_FunctionDef(self, node):
        if node.args.posonlyargs:
            self.flag(node, "positional-only parameters are a SyntaxError on the badge")
        if getattr(node, "type_params", None):
            self.flag(node, "type parameters are a SyntaxError on the badge")
        if node.name == "__init_subclass__":
            self.flag(node, "__init_subclass__ is never called on the badge")
        for decorator in node.decorator_list:
            self.check_decorator(decorator)
        self.guarded.append(False)
        self.generic_visit(node)
        self.guarded.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        if node.args.posonlyargs:
            self.flag(node, "positional-only parameters are a SyntaxError on the badge")
        self.guarded.append(False)
        self.generic_visit(node)
        self.guarded.pop()

    def visit_ClassDef(self, node):
        if node.keywords:
            self.flag(node, "class keywords such as metaclass= raise TypeError on the badge")
        if getattr(node, "type_params", None):
            self.flag(node, "type parameters are a SyntaxError on the badge")
        for decorator in node.decorator_list:
            self.check_decorator(decorator)
        self.generic_visit(node)

    def check_decorator(self, decorator):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        while isinstance(target, ast.Attribute):
            target = target.value
        if not isinstance(target, ast.Name):
            self.flag(decorator, "relaxed decorator expressions are a SyntaxError on the badge")

    def visit_Match(self, node):
        self.flag(node, "match statements are a SyntaxError on the badge")
        self.generic_visit(node)

    def visit_TypeAlias(self, node):
        self.flag(node, "type aliases are a SyntaxError on the badge")
        self.generic_visit(node)

    def check_module(self, name, node):
        if name == "badge" or name.startswith("badge."):
            self.flag(node, "imports badge, which is a runtime global")
        elif within(name, FORBIDDEN_MODULES):
            self.flag(node, "imports %s, which the badge lacks or this app avoids" % name)
        elif within(name, GUARDED_MODULES) and not self.guarded[-1]:
            self.flag(node, "imports %s without a try/except ImportError fallback" % name)

    def visit_Import(self, node):
        for alias in node.names:
            self.check_module(alias.name, node)
            if alias.asname:
                self.aliases[alias.asname] = alias.name
            else:
                top = alias.name.split(".")[0]
                self.aliases[top] = top

    def visit_ImportFrom(self, node):
        base = node.module or ""
        count = len(self.problems)
        self.check_module(base, node)
        for alias in node.names:
            if len(self.problems) == count:
                self.check_module(base + "." + alias.name, node)
            if alias.name in MISSING_ATTRS.get(base, ()):
                self.flag(node, "%s.%s is missing on the badge" % (base, alias.name))
            local = alias.asname or alias.name
            self.aliases[local] = "os.path" if (base, alias.name) == ("os", "path") else base + ":" + alias.name

    def visit_Attribute(self, node):
        base = self.resolve(node.value)
        if base and ":" not in base and node.attr in MISSING_ATTRS.get(base, ()):
            self.flag(node, "%s.%s is missing on the badge" % (base, node.attr))
        if node.attr in MISSING_OBJECT_ATTRS or node.attr.startswith("tm_"):
            self.flag(node, ".%s is missing on the badge" % node.attr)
        if isinstance(node.value, ast.Name) and (node.value.id, node.attr) == ("str", "maketrans"):
            self.flag(node, "str.maketrans is missing on the badge")
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id not in self.bound and (
                node.id in MISSING_NAMES or node.id.endswith("Warning")):
            self.flag(node, "%s is undefined on the badge" % node.id)

    def visit_Call(self, node):
        func = node.func
        keywords = [keyword.arg for keyword in node.keywords if keyword.arg]
        if isinstance(func, ast.Name) and func.id not in self.bound:
            self.check_builtin(func.id, node, keywords)
        target = self.call_target(func)
        if target:
            allowed = ALLOWED_KEYWORDS.get(target)
            for key in keywords if allowed is not None else ():
                if key not in allowed:
                    self.flag(node, "%s.%s(%s=) raises TypeError on the badge" % (target + (key,)))
            if target == ("collections", "deque") and len(node.args) != 2:
                self.flag(node, "deque() needs (iterable, maxlen) positionally on the badge")
            if target == ("random", "seed") and node.args and is_text(node.args[0]):
                self.flag(node, "random.seed() takes an int on the badge")
        if isinstance(func, ast.Attribute):
            self.check_method(func, node, keywords)
        self.generic_visit(node)

    def check_builtin(self, name, node, keywords):
        bad = BAD_KEYWORDS.get(name, ())
        for key in keywords:
            if bad is None or key in bad:
                self.flag(node, "%s(%s=) raises TypeError on the badge" % (name, key))
        if name == "hash":
            self.flag(node, "hash() differs between CPython and the badge")
        elif name == "iter" and len(node.args) == 2:
            self.flag(node, "iter(callable, sentinel) raises TypeError on the badge")
        elif name in ("isinstance", "issubclass") and len(node.args) > 1 and isinstance(
                node.args[1], ast.BinOp) and isinstance(node.args[1].op, ast.BitOr):
            self.flag(node, "%s() with A | B raises TypeError on the badge" % name)

    def check_method(self, func, node, keywords):
        name, args = func.attr, node.args
        if name in MISSING_METHODS:
            self.flag(node, ".%s() is missing on the badge" % name)
        elif name == "group" and len(args) != 1:
            self.flag(node, ".group() needs exactly one index on the badge")
        elif name == "center" and len(args) > 1:
            self.flag(node, ".center() takes no fill character on the badge")
        elif name in ("split", "rsplit") and keywords:
            self.flag(node, ".%s() takes no keywords on the badge" % name)
        elif name == "rsplit" and args and isinstance(args[0], ast.Constant) and args[0].value is None:
            self.flag(node, ".rsplit(None, n) is not implemented on the badge")
        elif name == "decode" and "errors" in keywords:
            self.flag(node, ".decode(errors=) raises TypeError on the badge")
        elif name == "from_bytes" and "signed" in keywords:
            self.flag(node, ".from_bytes(signed=) raises TypeError on the badge")
        elif name == "union" and len(args) > 1:
            self.flag(node, ".union() takes one argument on the badge")
        elif name == "translate" and len(args) == 1 and isinstance(args[0], (ast.Dict, ast.DictComp)):
            self.flag(node, "str.translate() with a table is missing on the badge")
        elif name == "format" and isinstance(func.value, ast.Constant) and isinstance(
                func.value.value, str) and field_access(func.value.value):
            self.flag(node, "format fields cannot use . or [] access on the badge")
        elif name == "send_addr_cmd" and not (args and names_trail_address(args[0])):
            self.flag(node, "beams must use the trail's IR_ADDRESS (0x54)")

    def check_display(self, node):
        if not isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del)) and any(
                isinstance(item, ast.Starred) for item in node.elts):
            self.flag(node, "starred items in a display are a SyntaxError on the badge")
        self.generic_visit(node)

    visit_List = visit_Tuple = visit_Set = check_display

    def visit_Dict(self, node):
        if None in node.keys:
            self.flag(node, "{**d} displays are a SyntaxError on the badge")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice) and node.slice.step is not None:
            self.flag(node, "step slices fail on str, tuple and bytes on the badge")
        self.generic_visit(node)


def token_problems(text):
    problems = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return ["the tokenizer failed"]
    for index, token in enumerate(tokens):
        line = token.start[0]
        if token.type == tokenize.NUMBER and token.string.lower() == "0x45":
            problems.append("line %d: 0x45 is the menu's event-beacon address" % line)
        elif token.type == tokenize.STRING and "\\N{" in token.string and "r" not in re.match(
                r"[A-Za-z]*", token.string).group(0).lower():
            problems.append("line %d: \\N{} escapes are not implemented on the badge" % line)
        elif token.type == tokenize.NAME and token.string == "with" and tokens[index + 1].string == "(":
            depth = 0
            for later in tokens[index + 1:]:
                if later.type == tokenize.OP and later.string in ("(", "[", "{"):
                    depth += 1
                elif later.type == tokenize.OP and later.string in (")", "]", "}"):
                    depth -= 1
                    if not depth:
                        break
                elif depth == 1 and later.type == tokenize.NAME and later.string == "as":
                    problems.append("line %d: parenthesized with ... as is a SyntaxError on the badge" % line)
                    break
    return problems


def scan_source(text, name="snippet"):
    try:
        tree = ast.parse(text, filename=name)
    except SyntaxError as error:
        return ["line %s: CPython SyntaxError %s" % (error.lineno, error.msg)]
    scan = BadgeScan(tree)
    scan.visit(tree)
    return scan.problems + token_problems(text)


BAD_SNIPPETS = (
    ("runtime global", "import badge"),
    ("lacks", "import textwrap"),
    ("lacks", "from typing import List"),
    ("lacks", "from __future__ import annotations"),
    ("lacks", "import datetime"),
    ("lacks", "import re"),
    ("lacks", "import urllib.request"),
    ("fallback", "from aye_arr.nec import NECSender"),
    ("fallback", "from badgeware import ir"),
    ("fallback", "import machine"),
    ("fallback", "def listen():\n    from badgeware.ir import ir\n    return ir\n"),
    ("fallback", "try:\n    import powman\nexcept ValueError:\n    powman = None\n"),
    ("fallback", "try:\n    pass\nexcept ImportError:\n    import network\n"),
    ("fallback", "try:\n    def connect():\n        import socket\nexcept ImportError:\n    pass\n"),
    ("random.shuffle", "import random\nrandom.shuffle(xs)"),
    ("random.choices", "from random import choices"),
    ("math.hypot", "import math as m\nd = m.hypot(1, 2)"),
    ("os.path.splitext", "import os\nstem = os.path.splitext(p)"),
    ("os.path.getsize", "from os import path\nn = path.getsize(p)"),
    ("time.monotonic", "import time\nnow = time.monotonic()"),
    ("collections.Counter", "from collections import Counter"),
    ("json.JSONDecodeError", "import json\ntry:\n    json.loads(s)\nexcept json.JSONDecodeError:\n    pass\n"),
    ("hashlib.md5", "import hashlib\ndigest = hashlib.md5(b'x')"),
    ("micropython.native", "import micropython\n@micropython.native\ndef f():\n    pass\n"),
    ("FileNotFoundError", "try:\n    open(p)\nexcept FileNotFoundError:\n    pass\n"),
    ("TimeoutError", "try:\n    pass\nexcept (OSError, TimeoutError):\n    pass\n"),
    ("UnicodeDecodeError", "error = UnicodeDecodeError"),
    ("UserWarning", "raise UserWarning('x')"),
    ("vars", "print(vars(x))"),
    ("format", "y = format(1, 'x')"),
    ("__builtins__", "b = __builtins__"),
    ("__doc__", "d = x.__doc__"),
    ("__qualname__", "q = f.__qualname__"),
    ("__traceback__", "t = e.__traceback__"),
    ("tm_year", "import time\nyear = time.localtime().tm_year"),
    ("maxlen", "n = buf.maxlen"),
    ("__init_subclass__", "class A:\n    def __init_subclass__(cls):\n        pass\n"),
    (".ljust", "s.ljust(8)"),
    (".zfill", "s.zfill(3)"),
    (".title", "s.title()"),
    (".isalnum", "s.isalnum()"),
    (".bit_length", "n.bit_length()"),
    (".hexdigest", "h.hexdigest()"),
    ("._replace", "p._replace(x=1)"),
    (".span", "m.span()"),
    (".groups", "m.groups()"),
    (".group", "m.group()"),
    (".group", "m.group(1, 2)"),
    (".center", "s.center(9, '*')"),
    (".split", "s.split(sep=' ')"),
    (".rsplit", "s.rsplit(None, 1)"),
    (".decode", "b.decode('utf-8', errors='ignore')"),
    (".from_bytes", "int.from_bytes(b, 'big', signed=True)"),
    (".union", "a.union(b, c)"),
    ("translate", "s.translate({1: 2})"),
    ("maketrans", "table = str.maketrans('a', 'b')"),
    ("format fields", "'{0.x}'.format(p)"),
    ("format fields", "'{a[0]}'.format(a=xs)"),
    ("hash()", "h = hash('mona')"),
    ("A | B", "isinstance(x, int | float)"),
    ("iter(", "it = iter(f, None)"),
    ("print(flush=", "print('x', flush=True)"),
    ("int(base=", "n = int('7', base=8)"),
    ("zip(strict=", "pairs = zip(a, b, strict=True)"),
    ("round(ndigits=", "r = round(x, ndigits=2)"),
    ("range(stop=", "r = range(stop=3)"),
    ("sum(start=", "total = sum(xs, start=1)"),
    ("open(newline=", "fh = open(p, newline='')"),
    ("json.dumps(indent=", "import json\ntext = json.dumps(d, indent=2)"),
    ("json.loads(strict=", "import json\ndata = json.loads(s, strict=False)"),
    ("deque()", "from collections import deque\nq = deque()"),
    ("deque(maxlen=", "from collections import deque\nq = deque((), maxlen=4)"),
    ("namedtuple(defaults=", "from collections import namedtuple\nP = namedtuple('P', 'x', defaults=(0,))"),
    ("random.seed", "import random\nrandom.seed('mona')"),
    ("IR_ADDRESS", "tx.send_addr_cmd(0x54, 1)"),
    ("IR_ADDRESS", "tx.send_addr_cmd(ADDRESS, 1)"),
    ("0x45", "beacon = 0x45"),
    ("SyntaxError", "with (open(a) as f, open(b) as g):\n    pass\n"),
    ("\\N{}", "s = '\\N{BULLET}'"),
    ("SyntaxError", "xs = [*a, *b]"),
    ("SyntaxError", "t = (*a, b)"),
    ("SyntaxError", "def f():\n    return *a, b\n"),
    ("SyntaxError", "s = {*a}"),
    ("SyntaxError", "d = {**a, 'k': 1}"),
    ("step slices", "s = name[::-1]"),
    ("step slices", "del xs[::2]"),
    ("metaclass", "class A(B, metaclass=M):\n    pass\n"),
    ("SyntaxError", "def f(a, /, b):\n    pass\n"),
    ("SyntaxError", "@buttons[0].handler\ndef f():\n    pass\n"),
    ("SyntaxError", "match x:\n    case 1:\n        pass\n"),
    ("SyntaxError", "try:\n    pass\nexcept* ValueError:\n    pass\n"),
    ("SyntaxError", "type Point = tuple\n"),
    ("SyntaxError", "def first[T](xs):\n    return xs[0]\n"),
    ("SyntaxError", "if True:\n  x = ("),
)

CLEAN_SNIPPETS = (
    "try:\n    from aye_arr.nec import NECSender\nexcept ImportError:\n    NECSender = None\n",
    "def listen():\n    try:\n        from badgeware.ir import ir\n    except Exception:\n        return None\n    return ir\n",
    "try:\n    import machine\nexcept (ValueError, ImportError):\n    machine = None\n",
    "try:\n    import network\nexcept:\n    network = None\n",
    "from badgeware import State",
    "import math\nd = math.sqrt(x * x + y * y)",
    "import os\nok = os.path.exists(p)",
    "import time\nnow = time.ticks_ms()",
    "a, *rest = xs",
    "[a, *rest] = xs",
    "for a, *rest in rows:\n    pass\n",
    "f(*args, **kw)",
    "head, tail = s.split(' ', 1)",
    "s.center(20)",
    "m.group(1)",
    "from collections import deque\nq = deque((), 8)",
    "try:\n    pass\nexcept (ValueError, OSError) as error:\n    pass\n",
    "xs.sort(key=lambda x: x[0])",
    "import trail_logic as tl\ntx.send_addr_cmd(tl.IR_ADDRESS, 1)",
    "tx.send_addr_cmd(IR_ADDRESS, 7)",
    "part = xs[1:3]",
    "y = 69",
    "sender.start()",
    "import json\ntext = json.dumps(d, separators=(',', ':'))",
    "def f(format):\n    return format\n",
    "with open(p) as fh:\n    pass\n",
    "with (lock):\n    pass\n",
    "s = r'\\N{x}'",
    "class A:\n    BUTTON_CODES = {}\n",
    "matrix.rotate(0.5)",
    "text = '{0} {1}'.format(a, b)",
    "d = dict(a)\nd.update(b)",
)


class SourceScanTests(unittest.TestCase):
    """CI runs CPython, so these scans stand in for the badge's MicroPython."""

    def test_the_scan_catches_badge_incompatible_code(self):
        for keyword, snippet in BAD_SNIPPETS:
            with self.subTest(snippet=snippet):
                problems = scan_source(snippet)
                self.assertTrue(any(keyword in problem for problem in problems), problems)

    def test_the_scan_accepts_badge_safe_code(self):
        for snippet in CLEAN_SNIPPETS:
            with self.subTest(snippet=snippet):
                self.assertEqual(scan_source(snippet), [])


class PackagingTests(unittest.TestCase):
    """The folder, icon and README that the menu, CI and badgerfactory rely on."""

    def test_the_icon_is_a_square_png_of_at_least_24_pixels(self):
        data = (APP / "icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(data[12:16], b"IHDR")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 24)

    def test_the_readme_passes_the_repository_validator(self):
        path = ROOT / ".github" / "scripts" / "validate_app_readmes.py"
        spec = importlib.util.spec_from_file_location("octocat_trail_readme_validator", path)
        validator = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "dont_write_bytecode", True):
            spec.loader.exec_module(validator)
        self.assertIsNone(validator.check_app(APP))
        sentence = validator.first_sentence(validator.first_paragraph(APP / "README.md"))
        self.assertTrue(sentence.startswith("Lead the Studio party"), sentence)


if __name__ == "__main__":
    unittest.main()
