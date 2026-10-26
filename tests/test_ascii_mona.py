"""Tests for the ASCII Mona badge app (badge/apps/ascii_mona).

The app's modules import each other by plain name (mona_dna, mona_octo, ...).
They are loaded here under unique ``ascii_mona_*`` names, and the plain names
only sit in sys.modules while loading, so other apps' tests in the same
process never see them. Badge runtime globals (image, shape, color, ...) are
injected into these private module objects rather than builtins, and fake
runtime modules (badgeware.ir, aye_arr.nec, ...) are removed after each test.
"""

import ast
import binascii
import importlib.util
import json
import os
import re
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "badge" / "apps" / "ascii_mona"
PREFIX = "ascii_mona_"
MODULE_ORDER = (
    "mona_parts",
    "mona_octo",
    "mona_dna",
    "mona_wheel",
    "mona_ir",
    "mona_link",
    "mona_net",
    "mona_ascii",
)
_MISSING = object()
M = {}


def load_app_modules():
    """Load the app modules once, without leaving plain names in sys.modules."""
    if M:
        return M
    names = list(MODULE_ORDER) + [PREFIX + name for name in MODULE_ORDER]
    saved_modules = dict((name, sys.modules.get(name, _MISSING)) for name in names)
    saved_path = list(sys.path)
    saved_flag = sys.dont_write_bytecode
    # CPython bytecode is useless on the badge; keep it out of the app folder
    sys.dont_write_bytecode = True
    loaded = {}
    try:
        for name in MODULE_ORDER:
            path = str(APP_DIR / (name + ".py"))
            spec = importlib.util.spec_from_file_location(PREFIX + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            sys.modules[PREFIX + name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
    finally:
        for name, old in saved_modules.items():
            if old is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        sys.path[:] = saved_path
        sys.dont_write_bytecode = saved_flag
    M.update(loaded)
    return M


def setUpModule():
    load_app_modules()


def _restore_module(name, old):
    if old is _MISSING:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = old


def install_modules(test, modules):
    """Put fake runtime modules (or None, to make an import fail) in sys.modules."""
    for name, module in modules.items():
        old = sys.modules.get(name, _MISSING)
        sys.modules[name] = module
        test.addCleanup(_restore_module, name, old)


def _restore_attr(module, name, old):
    if old is _MISSING:
        if name in module.__dict__:
            delattr(module, name)
    else:
        setattr(module, name, old)


def inject(test, module, **names):
    """Give one private app module runtime globals or constants for one test."""
    for name, value in names.items():
        old = module.__dict__.get(name, _MISSING)
        setattr(module, name, value)
        test.addCleanup(_restore_attr, module, name, old)


# Badge runtime fakes ---------------------------------------------------------


class FakeShape:
    def __init__(self, kind, args):
        self.kind = kind
        self.args = args
        self.transform = None


class FakeShapes:
    @staticmethod
    def custom(*contours):
        if not contours:
            raise ValueError("no contours")
        for contour in contours:
            if len(contour) < 2 or len(contour) % 2:
                raise ValueError("contours need x, y pairs")
        return FakeShape("custom", contours)

    @staticmethod
    def rectangle(x, y, w, h):
        return FakeShape("rectangle", (x, y, w, h))


class FakeMat3:
    def __init__(self):
        self.ops = []

    def translate(self, x, y):
        self.ops.append(("translate", x, y))
        return self

    def scale(self, x, y=None):
        self.ops.append(("scale", x, y))
        return self


class FakeColor:
    @staticmethod
    def rgb(r, g, b, a=255):
        for value in (r, g, b, a):
            if not 0 <= value <= 255:
                raise ValueError("colour component out of range: %r" % (value,))
        return (r, g, b, a)


class FakeImage:
    X2 = "X2"
    X4 = "X4"
    NON_ZERO = "NON_ZERO"
    EVEN_ODD = "EVEN_ODD"
    BILINEAR = "BILINEAR"
    NEAREST = "NEAREST"

    def __init__(self, width=320, height=240):
        self.width = width
        self.height = height
        self.raw = bytearray(width * height * 4)
        self.pen = None
        self.font = None
        self.antialias = None
        self.fill_rule = None
        self.calls = []

    def clear(self, *args):
        self.calls.append(("clear",) + args)

    def blit(self, *args):
        self.calls.append(("blit",) + args)

    def shape(self, made):
        self.calls.append(("shape", made, self.pen))

    def text(self, *args):
        self.calls.append(("text",) + args)

    def count(self, kind):
        return len([call for call in self.calls if call[0] == kind])


class BrokenImage(FakeImage):
    def __init__(self, width=320, height=240):
        raise MemoryError("no room for an image")


def fake_vec2(x, y):
    return ("vec2", x, y)


def fake_rect(x, y, w, h):
    return ("rect", x, y, w, h)


FAKE_FONT = types.SimpleNamespace(teatime="teatime", sins="sins")


class FakeState:
    """badgeware.State: load() fills the given dict, save() stores a copy."""

    def __init__(self, stored=None, fail_save=False):
        self.stored = stored or {}
        self.fail_save = fail_save

    def load(self, key, target):
        if key not in self.stored:
            return False
        target.update(json.loads(json.dumps(self.stored[key])))
        return True

    def save(self, key, value):
        if self.fail_save:
            raise OSError(28, "No space left on device")
        self.stored[key] = json.loads(json.dumps(value))


class FakeIr:
    """badgeware.ir.ir: one descriptor per 8-bit address."""

    def __init__(self, busy=()):
        self.bound = {}
        self.busy = busy
        self.closed = False

    def bind(self, remote, force=False):
        if remote.ADDRESS in self.busy and not force:
            raise ValueError("address 0x%02X already bound" % remote.ADDRESS)
        self.bound[remote.ADDRESS] = remote
        return remote

    def close(self):
        self.closed = True

    def deliver(self, address, command):
        self.bound[address].on_any(command)


def install_ir(test, busy=()):
    ir = FakeIr(busy)
    package = types.ModuleType("badgeware")
    sub = types.ModuleType("badgeware.ir")
    sub.ir = ir
    package.ir = sub
    install_modules(test, {"badgeware": package, "badgeware.ir": sub})
    return ir


def sender_class(fail_construct=(), fail_start=(), fail_send=False):
    """An aye_arr.nec.NECSender stand-in that records every frame."""

    class Sender:
        made = []

        def __init__(self, pin, pio, sm):
            if (pio, sm) in fail_construct:
                raise OSError("state machine in use")
            self.pin = pin
            self.pio = pio
            self.sm = sm
            self.started = False
            self.stopped = False
            self.sent = []
            Sender.made.append(self)

        def start(self):
            if (self.pio, self.sm) in fail_start:
                raise OSError("could not start")
            self.started = True

        def stop(self):
            self.stopped = True

        def send_addr_cmd(self, address, command):
            if fail_send:
                raise OSError("pio stalled")
            self.sent.append((address, command))

    Sender.made = []
    return Sender


def install_sender(test, sender):
    package = types.ModuleType("aye_arr")
    nec = types.ModuleType("aye_arr.nec")
    nec.NECSender = sender
    package.nec = nec
    install_modules(test, {"aye_arr": package, "aye_arr.nec": nec})


class FakePartner:
    def __init__(self, ident, name):
        self.id = ident
        self.name = name


class FakeProximity:
    def __init__(self, link):
        self.link = link
        self.updates = 0
        self.rested = []
        self.cleared = 0

    def update(self, now):
        self.updates += 1

    def rest(self, partner_id, now):
        self.rested.append(partner_id)

    def clear(self):
        self.cleared += 1

    def lights(self, now):
        return (0.25,)

    def syncing(self):
        return None

    def progress(self, now):
        return 0

    def cooling(self, now):
        return None


class FakeLink:
    """badgeware.link.Link: messages sent go straight into the peer's queue."""

    def __init__(self, capacity=48):
        self.games = []
        self.peer = None
        self.linked = False
        self.partner = None
        self.queue = []
        self.cap = capacity
        self.sent = []
        self.left = 0
        self.closed = False

    def pump(self):
        pass

    def update(self):
        pass

    def capacity(self):
        return self.cap

    def send(self, message):
        if not self.linked:
            return False
        message = bytes(message)
        if len(message) > self.cap:
            raise ValueError("message larger than link capacity")
        self.sent.append(message)
        if self.peer is not None:
            self.peer.queue.append(message)
        return True

    def receive(self):
        got = tuple(self.queue)
        self.queue = []
        return got

    def leave(self):
        self.left += 1
        for side in (self, self.peer):
            if side is not None:
                side.linked = False

    def close(self):
        self.closed = True


def link_module(link):
    def make(game):
        link.games.append(game)
        return link

    return types.SimpleNamespace(Link=make, Proximity=FakeProximity)


def pair(a, b, a_name="Ann", b_name="Bea"):
    a.peer = b
    b.peer = a
    a.linked = b.linked = True
    a.partner = FakePartner("id-b", b_name)
    b.partner = FakePartner("id-a", a_name)


def circle_raw(width=48, height=54, rgb=(110, 84, 240)):
    """Premultiplied RGBA: an opaque disc on a transparent background."""
    raw = bytearray(width * height * 4)
    cx = width // 2
    cy = height // 2
    r2 = (min(width, height) * 2 // 5) ** 2
    for y in range(height):
        for x in range(width):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                j = (y * width + x) * 4
                raw[j:j + 4] = bytes((rgb[0], rgb[1], rgb[2], 255))
    return raw


def png_size(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])


def app_sources():
    return sorted(APP_DIR.glob("*.py"))


def parse_app(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


# Loading ---------------------------------------------------------------------


class TestLoading(unittest.TestCase):
    def test_every_app_module_loaded_from_the_app_folder(self):
        for name in MODULE_ORDER:
            module = M[name]
            self.assertEqual(Path(module.__file__).resolve(), (APP_DIR / (name + ".py")).resolve())

    def test_app_modules_do_not_leak_into_sys_modules(self):
        for name in MODULE_ORDER:
            self.assertIsNot(sys.modules.get(name), M[name], name)
            self.assertIsNot(sys.modules.get(PREFIX + name), M[name], PREFIX + name)

    def test_every_source_file_parses(self):
        files = app_sources()
        self.assertIn(APP_DIR / "__init__.py", files)
        for path in files:
            parse_app(path)

    def test_app_entry_point_uses_the_runtime_contract(self):
        tree = parse_app(APP_DIR / "__init__.py")
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("badge", imported, "the launcher provides badge as a global")
        top = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertIn("update", top)
        self.assertIn("on_exit", top)
        last = tree.body[-1]
        self.assertIsInstance(last, ast.Expr)
        self.assertEqual(ast.dump(last.value), ast.dump(ast.parse("run(update)").body[0].value))
        source = (APP_DIR / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("screen.fill_rule = image.EVEN_ODD", source)
        self.assertIn("badge.caselights(0)", source)


# MicroPython compatibility ---------------------------------------------------

MISSING_METHODS = frozenset((
    "isalnum", "ljust", "rjust", "title", "zfill", "capitalize", "removeprefix",
    "removesuffix", "casefold", "swapcase", "isnumeric", "isprintable", "format_map",
    "isidentifier", "isdecimal", "bit_length", "hexdigest", "_replace", "_asdict",
    "expandtabs", "maketrans",
))
MISSING_ATTRS = {
    "random": ("shuffle", "sample", "choices", "Random"),
    "math": ("hypot", "dist", "prod", "gcd", "lcm", "isqrt", "comb", "perm"),
    "time": ("monotonic", "perf_counter", "process_time", "strftime"),
    "hashlib": ("md5", "sha1"),
    "collections": ("Counter", "defaultdict", "ChainMap"),
    "os": ("makedirs", "urandom", "environ", "walk", "replace", "getenv"),
    "json": ("JSONDecodeError",),
    "operator": ("itemgetter", "attrgetter"),
    "itertools": ("product", "permutations", "combinations", "groupby", "zip_longest",
                  "takewhile", "dropwhile", "pairwise"),
    "functools": ("lru_cache", "cache", "cmp_to_key"),
}
MISSING_PATH_ATTRS = ("splitext", "getsize")
BANNED_MODULES = frozenset((
    "textwrap", "dataclasses", "typing", "enum", "bisect", "__future__", "abc",
    "pathlib", "datetime", "operator", "functools", "re", "ure",
))
MISSING_NAMES = frozenset((
    "FileNotFoundError", "FileExistsError", "PermissionError", "IsADirectoryError",
    "NotADirectoryError", "TimeoutError", "ConnectionError", "ConnectionResetError",
    "ConnectionRefusedError", "ConnectionAbortedError", "BrokenPipeError",
    "InterruptedError", "BlockingIOError", "UnicodeDecodeError", "UnicodeEncodeError",
    "ModuleNotFoundError", "RecursionError", "UnboundLocalError", "IOError",
    "EnvironmentError", "Warning", "UserWarning", "DeprecationWarning",
    "RuntimeWarning", "ResourceWarning", "vars", "__builtins__", "hash",
    "__init_subclass__", "__doc__", "__qualname__",
))
ANY_KEYWORD = None
BANNED_KEYWORDS = {
    "dumps": ANY_KEYWORD,
    "loads": ANY_KEYWORD,
    "split": ANY_KEYWORD,
    "rsplit": ANY_KEYWORD,
    "deque": ANY_KEYWORD,
    "open": ("newline",),
    "from_bytes": ("signed",),
    "round": ("ndigits",),
    "sum": ("start",),
}


def _call_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def micropython_problems(path):
    """Constructs that crash or silently differ on the badge's MicroPython 1.29."""
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    problems = []

    def flag(node, what):
        problems.append("%s:%s %s" % (Path(path).name, getattr(node, "lineno", "?"), what))

    for number, line in enumerate(source.splitlines(), 1):
        if re.match(r"\s*(async\s+)?with\s*\(", line):
            problems.append("%s:%d parenthesised with" % (Path(path).name, number))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED_MODULES:
                    flag(node, "import " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in BANNED_MODULES:
                flag(node, "from %s import" % node.module)
            for alias in node.names:
                if alias.name in MISSING_ATTRS.get(module, ()):
                    flag(node, "from %s import %s" % (module, alias.name))
        elif isinstance(node, ast.Name) and node.id in MISSING_NAMES:
            flag(node, "name " + node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr in ("__doc__", "__qualname__", "__init_subclass__") or node.attr.startswith("tm_"):
                flag(node, "attribute " + node.attr)
            base = node.value
            if isinstance(base, ast.Name) and node.attr in MISSING_ATTRS.get(base.id, ()):
                flag(node, "%s.%s" % (base.id, node.attr))
            if (isinstance(base, ast.Attribute) and base.attr == "path"
                    and node.attr in MISSING_PATH_ATTRS):
                flag(node, "os.path." + node.attr)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.Lambda):
            if getattr(node.args, "posonlyargs", None):
                flag(node, "positional-only parameters")
            if isinstance(node, ast.FunctionDef) and node.name == "__init_subclass__":
                flag(node, "__init_subclass__ is never called")
        elif isinstance(node, ast.ClassDef) and node.keywords:
            flag(node, "class keywords (metaclass=)")
        elif isinstance(node, ast.Subscript):
            index = node.slice
            parts = index.elts if isinstance(index, ast.Tuple) else (index,)
            if any(isinstance(part, ast.Slice) and part.step is not None for part in parts):
                flag(node, "step slice")
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            if isinstance(getattr(node, "ctx", ast.Load()), ast.Load):
                if any(isinstance(elt, ast.Starred) for elt in node.elts):
                    flag(node, "starred display")
        elif isinstance(node, ast.Dict) and any(key is None for key in node.keys):
            flag(node, "dict ** display")
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if isinstance(node.func, ast.Attribute) and name in MISSING_METHODS:
                flag(node, "missing method ." + name + "()")
            if name in BANNED_KEYWORDS:
                banned = BANNED_KEYWORDS[name]
                for keyword in node.keywords:
                    if keyword.arg and (banned is ANY_KEYWORD or keyword.arg in banned):
                        flag(node, "%s(%s=)" % (name, keyword.arg))
            if name == "rsplit" and node.args and isinstance(node.args[0], ast.Constant) \
                    and node.args[0].value is None:
                flag(node, "rsplit(None, n)")
            if name == "center" and len(node.args) > 1:
                flag(node, "center() fill character")
            if name == "union" and len(node.args) > 1:
                flag(node, "set.union with several arguments")
            if name == "iter" and len(node.args) > 1:
                flag(node, "iter(callable, sentinel)")
            if name == "deque" and (len(node.args) != 2 or node.keywords):
                flag(node, "deque() needs (iterable, maxlen) positionally")
            if name in ("sort", "sorted"):
                flag(node, "sorted() is not stable on the badge")
            if name == "isinstance" and len(node.args) == 2 and isinstance(node.args[1], ast.BinOp):
                flag(node, "isinstance with X | Y")
            if (name in ("startswith", "endswith") and node.args
                    and isinstance(node.args[0], ast.Tuple)):
                flag(node, name + "() with a tuple")
            if (name == "format" and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and re.search(r"\{\w*[.\[]", node.func.value.value)):
                flag(node, "format field attribute or index")
    return problems


class TestMicroPythonSafety(unittest.TestCase):
    def test_app_avoids_constructs_the_badge_runtime_lacks(self):
        problems = []
        for path in app_sources():
            problems.extend(micropython_problems(path))
        self.assertEqual(problems, [])

    def test_scanner_catches_known_badge_gaps(self):
        bad = (
            "from __future__ import annotations\n"
            "import textwrap\n"
            "import random\n"
            "x = 'ab'[::-1]\n"
            "y = [*a, *b]\n"
            "z = {**d, 'k': 1}\n"
            "t = (*a, 1)\n"
            "random.shuffle(y)\n"
            "s = 'a'.ljust(4)\n"
            "try:\n    pass\nexcept FileNotFoundError:\n    pass\n"
            "def f(a, /, b):\n    pass\n"
            "json.dumps(x, indent=2)\n"
            "'a b'.split(maxsplit=1)\n"
            "'a b'.rsplit(None, 1)\n"
            "deque(maxlen=4)\n"
            "h = hash('octocat')\n"
            "v = vars(x)\n"
            "'{0.x}'.format(o)\n"
            "os.path.splitext(p)\n"
            "isinstance(x, int | float)\n"
            "class C(metaclass=Meta):\n    pass\n"
            "time.localtime().tm_year\n"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.py"
            path.write_text(bad, encoding="utf-8")
            found = "\n".join(micropython_problems(path))
        for expected in (
            "import textwrap", "from __future__ import", "step slice", "starred display",
            "dict ** display", "random.shuffle", ".ljust()", "name FileNotFoundError",
            "positional-only", "dumps(indent=)", "split(maxsplit=)", "rsplit(None, n)",
            "deque()", "name hash", "name vars", "format field", "os.path.splitext",
            "isinstance with X | Y", "class keywords", "attribute tm_year",
        ):
            self.assertIn(expected, found)

    def test_app_has_no_regex_handle_checks_or_float_derived_dna(self):
        dna_source = (APP_DIR / "mona_dna.py").read_text(encoding="utf-8")
        self.assertNotIn("import re", dna_source)
        tree = parse_app(APP_DIR / "mona_dna.py")
        floats = [node.lineno for node in ast.walk(tree)
                  if isinstance(node, ast.Constant) and isinstance(node.value, float)]
        self.assertEqual(floats, [], "DNA must be integer-only to match on every badge")

    def test_optional_hardware_modules_are_imported_lazily(self):
        lazy = ("aye_arr", "badgeware", "network", "socket", "urequests", "requests",
                "powman", "wifi", "secrets", "machine")
        for path in app_sources():
            if path.name == "__init__.py":
                continue
            tree = parse_app(path)
            for node in tree.body:
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    self.assertNotIn(name.split(".")[0], lazy,
                                     "%s imports %s at module level" % (path.name, name))


# Handles ---------------------------------------------------------------------


class TestHandles(unittest.TestCase):
    def setUp(self):
        self.D = M["mona_dna"]

    def test_valid_handles(self):
        for handle in ("a", "octocat", "Octo-Cat-9", "mona", "a" * 39, "0", "x-y-z", "WMarkus"):
            self.assertEqual(self.D.handle_problem(handle), "", handle)
            self.assertTrue(self.D.valid_handle(handle), handle)

    def test_invalid_handles_explain_the_problem(self):
        cases = (
            ("", "type a handle"),
            (None, "type a handle"),
            (42, "type a handle"),
            ("a" * 40, "39 characters max"),
            ("abc_def", "letters, digits and - only"),
            ("abc def", "letters, digits and - only"),
            ("octo.cat", "letters, digits and - only"),
            ("\u00e9t\u00e9", "letters, digits and - only"),
            ("-abc", "no - at either end"),
            ("abc-", "no - at either end"),
            ("ab--cd", "no double hyphens"),
        )
        for handle, problem in cases:
            self.assertEqual(self.D.handle_problem(handle), problem, repr(handle))
            self.assertFalse(self.D.valid_handle(handle), repr(handle))

    def test_non_ascii_letters_are_rejected_like_on_the_badge(self):
        # CPython's isalpha() accepts these, the badge's does not; the app must
        # use its explicit ASCII set so both agree.
        for handle in ("\u00e9", "caf\u00e9", "\u0434\u0430", "\uff41bc"):
            self.assertFalse(self.D.valid_handle(handle), repr(handle))
            self.assertEqual(self.D.clean_handle(handle), "")

    def test_clean_handle_accepts_urls_mentions_and_bytes(self):
        cases = (
            ("https://github.com/Octocat", "octocat"),
            ("HTTPS://GitHub.com/Octocat", "octocat"),
            ("@MonaLisa", "monalisa"),
            ("github.com/octocat/hello-world?tab=repos", "octocat"),
            ("www.github.com/ada#x", "ada"),
            ("  octocat  ", "octocat"),
            (b"octocat", "octocat"),
        )
        for raw, handle in cases:
            self.assertEqual(self.D.clean_handle(raw), handle, repr(raw))

    def test_clean_handle_rejects_junk(self):
        for raw in (b"\xff", 42, None, "", "not valid!", "a--b", "-ab", "x" * 40):
            self.assertEqual(self.D.clean_handle(raw), "", repr(raw))

    def test_clean_text_keeps_printable_ascii(self):
        self.assertEqual(self.D.clean_text("[x]\n\ty \u00e9\x00z ", 99), "(x)  y z")
        self.assertEqual(self.D.clean_text("abcdef", 3), "abc")
        self.assertEqual(self.D.clean_text(None, 5), "")
        self.assertEqual(self.D.clean_text(12, 5), "")


# DNA -------------------------------------------------------------------------

GOLDEN = (
    ("octocat", "11160b0808090d000c11000c00000600040603", "c4f5", 0xC9965038),
    ("mona", "111112030a11071c10120b001100090c000303", "f777", 0x9DA4DD9D),
    ("ada", "01040e0c0c0b0a1c002a121c000c0000000100", "2406", 0x7633BE0E),
    ("wmarkus", "0d120d1a1a0807030011000f240003000a0403", "405b", 0x460CF448),
)


class TestDna(unittest.TestCase):
    def setUp(self):
        self.D = M["mona_dna"]
        self.O = M["mona_octo"]

    def test_hash_and_prng_vectors_match_the_badge(self):
        D = self.D
        self.assertEqual(D.fnv1a(b""), 0x811C9DC5)
        self.assertEqual(D.fnv1a(b"a"), 0xE40C292C)
        self.assertEqual(D.fnv1a(b"foobar"), 0xBF9CF968)
        self.assertEqual(D.fmix32(0), 0)
        self.assertEqual(D.fmix32(1), 0x514E28B7)
        rng = D.Rng(0)
        self.assertEqual([rng.next() for _ in range(3)], [1359758873, 3761132862, 2075758394])
        rng = D.Rng(1)
        self.assertEqual([rng.next() for _ in range(3)], [270369, 67634689, 2647435461])
        rng = D.Rng(D.seed_of("octocat"))
        for limit in (1, 2, 7, 19, 255, 1000):
            for _ in range(50):
                value = rng.below(limit)
                self.assertTrue(0 <= value < limit)
                self.assertIsInstance(value, int)

    def test_golden_dna_is_stable(self):
        D = self.D
        for handle, hex_dna, short, seed in GOLDEN:
            dna = D.dna_for(handle)
            self.assertIsInstance(dna, tuple)
            self.assertEqual(len(dna), D.SIZE)
            self.assertEqual(D.dna_hex(dna), hex_dna, handle)
            self.assertEqual(D.short_id(dna), short, handle)
            self.assertEqual(D.seed_of(handle), seed, handle)
        self.assertEqual(D.dna_hex(D.dna_for_uid("bad9e0051e000001")),
                         "0d1500191910031c1c1815100f0000090a0000")
        self.assertEqual(D.dna_for_uid("BAD9E0051E000001"), D.dna_for_uid("bad9e0051e000001"))

    def test_dna_ignores_handle_case_and_is_deterministic(self):
        D = self.D
        self.assertEqual(D.dna_for("OctoCat"), D.dna_for("octocat"))
        self.assertEqual(D.dna_for("mona"), D.dna_for("mona"))
        self.assertNotEqual(D.dna_for("mona"), D.dna_for("monb"))

    def test_limits_fit_in_seven_bit_ir_bytes(self):
        D = self.D
        self.assertEqual(D.SIZE, 19)
        self.assertEqual(D.LIMITS, (18, 24, 24, 31, 31, 20, 19, 32, 37, 50, 33, 31, 38, 16,
                                    10, 19, 19, 8, 4))
        self.assertTrue(all(0 < limit <= 0x80 for limit in D.LIMITS))
        self.assertEqual(D.LIMITS[D.TITLE], len(D.TITLES))
        self.assertEqual(D.LIMITS[D.BACKDROP], len(D.BACKDROPS))
        self.assertEqual(D.LIMITS[D.BODY], len(D.BODY_NAMES))
        for cat in range(self.O.PICKS):
            self.assertEqual(D.LIMITS[D.PART0 + cat], self.O.count(cat) + 1, cat)
        self.assertEqual(D.LIMITS[D.MISC_A], self.O.count(self.O.MISC) + 1)

    def test_random_dna_follows_the_generator_rules(self):
        D = self.D
        O = self.O
        not_random = dict((cat, set(names)) for cat, names in D.NOT_RANDOM)
        theme_only = dict((cat, set(names)) for cat, names in D.THEME_ONLY)
        themes = D.themes()
        seen_themes = 0
        for number in range(300):
            handle = "user%d" % number
            dna = D.dna_for(handle)
            self.assertTrue(D.valid_dna(dna), handle)
            self.assertTrue(dna[D.PART0] >= 1 and dna[D.PART0 + 1] >= 1, "%s needs eyes and a mouth" % handle)
            picks, misc = D.picks_of(dna)
            present = set((cat, index) for cat, index in enumerate(picks) if index >= 0)
            present.update((O.MISC, index) for index in misc)
            for cat, index in present:
                name = O.part_name(cat, index)
                self.assertNotIn(name, not_random.get(cat, ()), "%s got %s" % (handle, name))
                if name in theme_only.get(cat, ()):
                    whole = [theme for theme in themes
                             if (cat, index) in theme and all(pair in present for pair in theme)]
                    self.assertTrue(whole, "%s has %s without its theme" % (handle, name))
                    seen_themes += 1
            if dna[D.MISC_A] and dna[D.MISC_B]:
                self.assertNotEqual(dna[D.MISC_A], dna[D.MISC_B])
                names = (O.part_name(O.MISC, dna[D.MISC_A] - 1), O.part_name(O.MISC, dna[D.MISC_B] - 1))
                for group in D.MISC_GROUPS:
                    self.assertFalse(names[0] in group and names[1] in group,
                                     "%s has two extras from one group" % handle)
        self.assertGreater(seen_themes, 0, "themes never came up in 300 handles")

    def test_valid_dna_rejects_malformed_values(self):
        D = self.D
        dna = D.dna_for("octocat")
        self.assertTrue(D.valid_dna(dna))
        self.assertTrue(D.valid_dna(list(dna)))
        for bad in (
            dna[:-1],
            dna + (0,),
            (True,) + dna[1:],
            (D.LIMITS[0],) + dna[1:],
            (-1,) + dna[1:],
            None,
            "x" * D.SIZE,
            bytes(dna),
        ):
            self.assertFalse(D.valid_dna(bad), repr(bad))

    def test_hex_round_trip_and_rejections(self):
        D = self.D
        dna = D.dna_for("octocat")
        hex_dna = D.dna_hex(dna)
        self.assertEqual(D.parse_hex(hex_dna), dna)
        self.assertEqual(D.parse_hex(hex_dna.upper()), dna)
        for bad in (hex_dna[:-2], "zz" + hex_dna[2:], "ff" + hex_dna[2:], None, b"ab", ""):
            self.assertIsNone(D.parse_hex(bad), repr(bad))

    def test_describe_and_highlights(self):
        D = self.D
        dna = D.dna_for("octocat")
        self.assertEqual(list(D.describe(dna)), [
            ("Title", "Mentor"), ("Body", "Periwinkle"), ("Eyes", "Sad"), ("Mouth", "Chillin"),
            ("Hair", "None"), ("Hat", "Chullo"), ("Top", "Dress"), ("Bottoms", "None"),
            ("Shoes", "Platforms"), ("Prop", "None"), ("Eyewear", "None"),
            ("Face hair", "Full Beard"), ("Extras", "Dress Buckle Belt"), ("Backdrop", "Rings"),
        ])
        self.assertEqual(D.highlights(dna), ["Chullo", "Dress", "Full Beard", "Platforms"])
        self.assertEqual(D.title_of(dna), "Mentor")
        self.assertEqual(D.backdrop_of(dna), 3)
        self.assertEqual(D.extras(dna), "Dress Buckle Belt")
        self.assertEqual([D.value_name(dna, field) for field in range(D.SIZE)], [
            "Periwinkle", "Swatch 23 of 24", "Swatch 12 of 24", "Swatch 9 of 31",
            "Swatch 9 of 31", "Sad", "Chillin", "None", "Chullo", "Dress", "None",
            "Platforms", "None", "None", "Full Beard", "None", "Dress Buckle Belt",
            "Mentor", "Rings",
        ])
        self.assertEqual(D.colours_of(dna), (6250902, 13015112, 14798789, 12160445,
                                             6901345, 8557442, 13214823, 13214823))
        self.assertEqual(D.picks_of(dna), ([8, 12, -1, 11, 16, -1, 11, -1, -1, 5], (3,)))
        self.assertEqual(D.body_rgb(dna), (6250902, 13015112, 14798789))
        self.assertEqual(D.item_name(self.O.PROPS, -1), "None")
        self.assertEqual(D.item_name(self.O.MISC, 3), "Dress Buckle Belt")

    def test_nudge_wraps_inside_each_field(self):
        D = self.D
        dna = D.dna_for("octocat")
        self.assertEqual(D.lowest(D.PART0), 1)
        self.assertEqual(D.lowest(D.PART0 + 1), 1)
        self.assertEqual(D.lowest(D.PART0 + 2), 0)
        self.assertEqual(D.lowest(D.BODY), 0)
        self.assertEqual(D.nudge(dna, D.PART0, -1)[D.PART0], 8)
        self.assertEqual(D.nudge(dna, D.PART0, 100)[D.PART0], 14)
        self.assertEqual(D.nudge(dna, D.BODY, -18)[D.BODY], 17)
        self.assertEqual(D.nudge(dna, D.TITLE, 1)[D.TITLE], 7)
        self.assertEqual(D.nudge(dna, D.BACKDROP, -4)[D.BACKDROP], 3)
        value = dna[D.PART0]
        span = D.LIMITS[D.PART0] - D.lowest(D.PART0)
        for _ in range(span * 2):
            dna = D.nudge(dna, D.PART0, 1)
            self.assertTrue(1 <= dna[D.PART0] < D.LIMITS[D.PART0])
            self.assertTrue(D.valid_dna(dna))
        self.assertEqual(dna[D.PART0], value)

    def test_compact_counts(self):
        D = self.D
        self.assertEqual([D.compact(n) for n in (0, 7, 999, 1000, 1500, 12345, 999999, 1000000, 1234567, -5)],
                         ["0", "7", "999", "1k", "1.5k", "12k", "999k", "1M", "1.2M", "-5"])
        self.assertEqual(D.counted(1, "repo"), "1 repo")
        self.assertEqual(D.counted(2, "repo"), "2 repos")
        self.assertEqual(D.counted(15300, "follower"), "15k followers")

    def test_profile_tunes_the_mona(self):
        D = self.D
        base = D.dna_for("octocat")
        profile = {
            "login": "octocat", "bio": "I maintain open source and play guitar",
            "company": "@github", "followers": 15300, "public_repos": 8, "public_gists": 8,
            "created_at": "2011-01-25T18:44:36Z", "site_admin": False,
        }
        dna, notes = D.apply_profile(base, profile)
        self.assertEqual(notes, ["Maintainer: from bio", "Ship It Squirrel: works at GitHub",
                                 "Crown: 15k followers"])
        self.assertEqual([(i, base[i], dna[i]) for i in range(D.SIZE) if base[i] != dna[i]],
                         [(8, 12, 17), (12, 0, 35), (17, 6, 0)])
        self.assertTrue(D.valid_dna(dna))
        self.assertEqual(D.apply_profile(base, profile), (dna, notes))

    def test_profile_rules(self):
        D = self.D
        base = D.dna_for("octocat")
        dna, notes = D.apply_profile(base, {"login": "old", "created_at": "2008-01-01T00:00:00Z",
                                            "public_repos": 150, "site_admin": True})
        self.assertEqual(notes, ["Maintainer: 150 repos", "Ship It Squirrel: GitHub staff",
                                 "Classic colours: joined 2008"])
        self.assertEqual(dna[D.BODY], 0)
        dna, notes = D.apply_profile(base, {"bio": "I make music"})
        self.assertEqual(notes, ["Guitar: from bio"])
        self.assertEqual(dna[D.PART0 + self.O.PROPS], self.O.find_part(self.O.PROPS, "Guitar") + 1)
        dna, notes = D.apply_profile(base, {"bio": "Docs and design"})
        self.assertEqual(notes, ["Designer: from bio", "Paintbrush: from bio"])
        self.assertEqual(dna[D.TITLE], D.TITLES.index("Designer"))
        dna, notes = D.apply_profile(base, {"public_gists": 25, "followers": 999,
                                            "created_at": "2010-12-31T00:00:00Z"})
        self.assertEqual(notes, ["Hacker: 25 gists", "Classic colours: joined 2010"])
        dna, notes = D.apply_profile(base, {
            "bio": "maintain music design docs security", "site_admin": True,
            "followers": 5000, "created_at": "2008-01-01", "public_repos": 500})
        self.assertEqual(len(notes), D.MAX_NOTES)
        self.assertTrue(D.valid_dna(dna))
        for empty in ({}, None, "nonsense", {"bio": None, "followers": "lots", "created_at": 7}):
            self.assertEqual(D.apply_profile(base, empty), (base, []), repr(empty))


def art_blocks(parts):
    """Every (offset, length) block the art index points at."""
    blocks = [(base[2], base[3]) for base in parts.BASE]
    for category in parts.PARTS:
        for part in category:
            for _holder, _cls, offset, length in part[2]:
                blocks.append((offset, length))
    return blocks


class TestOcto(unittest.TestCase):
    """The baked MyOctocat art library and its frame-sliced painter."""

    @classmethod
    def setUpClass(cls):
        load_app_modules()
        cls.data = (APP_DIR / M["mona_parts"].BIN).read_bytes()

    def setUp(self):
        self.O = M["mona_octo"]
        self.P = M["mona_parts"]
        self.D = M["mona_dna"]
        self.path = str(APP_DIR / self.P.BIN)

    def paint_kit(self):
        inject(self, self.O, mat3=FakeMat3, image=FakeImage, shape=FakeShapes, color=FakeColor)

    def outfit(self, handle="octocat"):
        dna = self.D.dna_for(handle)
        picks, misc = self.D.picks_of(dna)
        blocks, flags = self.O.compose(picks, misc)
        return blocks, flags, self.D.colours_of(dna)

    def test_art_file_matches_its_index(self):
        O, P = self.O, self.P
        self.assertEqual(len(self.data), P.BIN_SIZE)
        self.assertEqual(binascii.crc32(self.data) & 0xFFFFFFFF, P.BIN_CRC)
        self.assertEqual(self.data[:6], b"OCTO" + bytes((P.VERSION, P.Q)))
        self.assertTrue(O.check_header(self.data[:6]))
        for bad in (b"OCTO\x02", b"OCTX\x02\x04", b"OCTO\x03\x04", b"OCTO\x02\x08", b""):
            self.assertFalse(O.check_header(bad), bad)

    def test_every_art_block_parses_exactly(self):
        O, P = self.O, self.P
        blocks = art_blocks(P)
        self.assertEqual(len(blocks), 343)
        layer_count = 0
        for offset, length in blocks:
            self.assertGreaterEqual(offset, 6)
            self.assertLessEqual(offset + length, len(self.data))
            data = self.data[offset:offset + length]
            used = 2
            for role, rgb, alpha, variant, contours in O.layers(data):
                layer_count += 1
                self.assertTrue(role < len(P.ROLES) or role == O.CUSTOM, role)
                self.assertTrue(0 <= rgb <= 0xFFFFFF)
                self.assertTrue(0 <= alpha <= 255)
                self.assertIn(variant, (0, O.ORIGINAL, O.MASKED))
                used += 8 if role == O.CUSTOM else 5
                for contour in contours:
                    self.assertEqual(len(contour) % 4, 0)
                    self.assertGreaterEqual(len(contour), 12)
                    used += 2 + len(contour)
            self.assertEqual(used, length, "block at %d" % offset)
        self.assertEqual(layer_count, 4497)

    def test_part_names_and_lookup(self):
        O, P = self.O, self.P
        self.assertEqual(O.PICKS, 10)
        self.assertEqual([O.count(c) for c in range(O.MISC + 1)],
                         [19, 18, 31, 36, 49, 32, 30, 37, 15, 9, 18])
        self.assertEqual(len(P.PARTS), O.MISC + 1)
        self.assertEqual(O.part_name(O.PROPS, 0), "Baguette")
        self.assertEqual(O.part_name(O.PROPS, -1), "None")
        self.assertEqual(O.part_name(O.PROPS, 999), "None")
        self.assertEqual(O.part_name(O.PROPS, None), "None")
        self.assertEqual(O.find_part(O.PROPS, "Baguette"), 0)
        self.assertEqual(O.find_part(O.TOPS, "Dress"), 16)
        self.assertEqual(O.find_part(O.PROPS, "Nope"), -1)
        for cat in range(O.MISC + 1):
            for index in range(O.count(cat)):
                name = O.part_name(cat, index)
                self.assertTrue(name and isinstance(name, str))
                self.assertLessEqual(O.find_part(cat, name), index)

    def test_colours_index_the_myoctocat_swatches(self):
        O, P = self.O, self.P
        base = O.colours(0, 0, 0, 0, 0)
        self.assertEqual(base, (2631720, 4802889, 10078153, 16762287, 10702654, 5258039, 0, 0))
        self.assertEqual(len(base), len(P.ROLES))
        self.assertEqual(O.colours(len(P.BODY), len(P.FACE), len(P.EYE), len(P.HAIR), len(P.FACEHAIR)), base)

    def test_compose_follows_myoctocat_hiding_rules(self):
        O, P = self.O, self.P
        none = [-1] * O.PICKS
        blocks, flags = O.compose(none)
        self.assertEqual((len(blocks), flags), (4, 0))
        self.assertEqual(blocks[0], (P.BASE[0][2], P.BASE[0][3]))
        dress = list(none)
        dress[O.TOPS] = O.find_part(O.TOPS, "Dress")
        dress_blocks, dress_flags = O.compose(dress)
        self.assertTrue(dress_flags & P.F_NO_PANTS)
        trousers = list(dress)
        trousers[O.BOTTOMS] = 0
        self.assertEqual(O.compose(trousers)[0], dress_blocks)
        prop = list(none)
        prop[O.PROPS] = O.find_part(O.PROPS, "Baguette")
        prop_blocks, prop_flags = O.compose(prop)
        self.assertTrue(prop_flags & P.F_HAND)
        self.assertEqual(len(prop_blocks), 4)
        self.assertNotIn((P.BASE[3][2], P.BASE[3][3]), prop_blocks)
        self.assertEqual(O.compose(none, (0, 0, 999)), O.compose(none, (0,)))
        self.assertEqual(len(O.compose(none, (0,))[0]), 5)
        self.assertEqual(O.compose([3]), O.compose([3] + [-1] * (O.PICKS - 1)))
        self.assertEqual(O.skip_variant(0), O.MASKED)
        self.assertEqual(O.skip_variant(P.F_NO_BIG_HAIR), O.ORIGINAL)

    def test_composed_outfits_stay_inside_the_art_file(self):
        D, O = self.D, self.O
        known = set(art_blocks(self.P))
        for number in range(60):
            dna = D.dna_for("mona-%d" % number)
            picks, misc = D.picks_of(dna)
            blocks, _flags = O.compose(picks, misc)
            self.assertGreaterEqual(len(blocks), 3)
            self.assertEqual(len(set(blocks)), len(blocks))
            for block in blocks:
                self.assertIn(block, known)

    def test_fit_keeps_the_art_box_inside_the_target(self):
        O, P = self.O, self.P
        s, x, y = O.fit(240, 240)
        self.assertAlmostEqual(s, 0.12454592631, places=9)
        self.assertAlmostEqual(x, -16.440062273, places=6)
        self.assertAlmostEqual(y, -0.12454592631, places=9)
        for width, height, margin in ((240, 240, 0), (240, 240, 10), (192, 216, 0), (320, 100, 4)):
            s, x, y = O.fit(width, height, margin)
            left, right = x + P.BOX[0] * s, x + P.BOX[2] * s
            top, bottom = y + P.BOX[1] * s, y + P.BOX[3] * s
            self.assertGreaterEqual(left, margin - 1e-6)
            self.assertLessEqual(right, width - margin + 1e-6)
            self.assertGreaterEqual(top, margin - 1e-6)
            self.assertLessEqual(bottom, height - margin + 1e-6)
            self.assertAlmostEqual(left - margin, width - margin - right, places=6)

    def expected_layers(self, blocks, flags):
        skip = self.O.skip_variant(flags)
        total = 0
        for offset, length in blocks:
            for _role, _rgb, _alpha, variant, contours in self.O.layers(self.data[offset:offset + length]):
                if variant != skip and contours:
                    total += 1
        return total

    def test_painter_draws_the_whole_outfit(self):
        O, P = self.O, self.P
        self.paint_kit()
        blocks, flags, palette = self.outfit()
        painter = O.Painter(self.path)
        target = FakeImage(192, 216)
        painter.start(target, blocks, flags, palette, 0.1, 5, 7)
        self.addCleanup(painter.close)
        self.assertFalse(painter.done)
        self.assertEqual(painter.failed, "")
        self.assertEqual(painter.progress(), 0)
        self.assertEqual(target.antialias, "X4")
        self.assertEqual(target.fill_rule, "NON_ZERO")
        self.assertEqual(painter.transform.ops, [("translate", 5, 7), ("scale", 0.1 / P.Q, None)])
        for _ in range(1000):
            if painter.step(budget_ms=10 ** 9):
                break
        self.assertTrue(painter.done)
        self.assertEqual(painter.errors, 0)
        self.assertEqual(painter.drawn, self.expected_layers(blocks, flags))
        self.assertEqual(painter.drawn, 127)
        self.assertEqual(target.count("shape"), painter.drawn)
        self.assertEqual(painter.progress(), 100)
        for call in target.calls:
            made, pen = call[1], call[2]
            self.assertEqual(made.kind, "custom")
            self.assertIs(made.transform, painter.transform)
            self.assertTrue(all(contour.typecode == "f" for contour in made.args))
            self.assertEqual(len(pen), 4)
        self.assertTrue(painter.step())

    def test_painter_respects_its_frame_budget(self):
        O = self.O
        self.paint_kit()
        blocks, flags, palette = self.outfit("ada")
        painter = O.Painter(self.path)
        painter.start(FakeImage(), blocks, flags, palette, 0.1, 0, 0)
        self.assertFalse(painter.step(budget_ms=-1))
        self.assertEqual(painter.drawn, 1)
        self.assertLess(painter.progress(), 100)
        painter.close()
        self.assertIsNone(painter.file)
        painter.close()

    def test_painter_paces_the_paint_in_by_badge_time(self):
        O = self.O
        self.paint_kit()
        blocks, flags, palette = self.outfit()
        total = self.expected_layers(blocks, flags)
        end = (total * O.LAYER_MS // 80 + 1) * 80

        def reveal(frame_ms):
            painter = O.Painter(self.path)
            self.addCleanup(painter.close)
            painter.start(FakeImage(192, 216), blocks, flags, palette, 0.1, 5, 7)
            seen = []
            for elapsed in range(0, end + 1, frame_ms):
                done = painter.step(10 ** 9, 7000 + elapsed)
                if elapsed % 80 == 0:
                    seen.append((elapsed, painter.laid, done))
            return seen

        fast, slow = reveal(16), reveal(40)
        self.assertEqual(fast, slow)
        self.assertEqual(len(fast), end // 80 + 1)
        for elapsed, laid, done in fast:
            self.assertEqual(laid, min(total, elapsed // O.LAYER_MS + 1))
            self.assertEqual(done, elapsed >= total * O.LAYER_MS)
        self.assertTrue(fast[-1][2])

    def test_painter_budget_still_caps_a_late_frame(self):
        O = self.O
        self.paint_kit()
        blocks, flags, palette = self.outfit("ada")
        painter = O.Painter(self.path)
        self.addCleanup(painter.close)
        painter.start(FakeImage(), blocks, flags, palette, 0.1, 0, 0)
        self.assertFalse(painter.step(-1, 0))
        self.assertEqual(painter.laid, 1)
        self.assertFalse(painter.step(10 ** 9, 0))
        self.assertEqual(painter.laid, 1)
        for second in range(1, 4):
            laid = painter.laid
            self.assertFalse(painter.step(-1, second * 1000))
            self.assertLessEqual(painter.laid, laid + 1)
        self.assertTrue(painter.step(10 ** 9, 60000))
        self.assertEqual(painter.laid, painter.drawn)
        self.assertEqual(painter.drawn, self.expected_layers(blocks, flags))

    def test_painter_survives_missing_bad_and_short_art(self):
        O = self.O
        self.paint_kit()
        blocks, flags, palette = self.outfit()
        missing = O.Painter(str(APP_DIR / "no-such-art.bin"))
        missing.start(FakeImage(), blocks, flags, palette, 1, 0, 0)
        self.assertTrue(missing.done)
        self.assertEqual(missing.failed, "art file missing")
        self.assertTrue(missing.step())
        self.assertEqual((missing.progress(), missing.drawn), (100, 0))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        bad = os.path.join(folder.name, "bad.bin")
        with open(bad, "wb") as handle:
            handle.write(b"OCTO\x01\x04" + bytes(32))
        wrong = O.Painter(bad)
        wrong.start(FakeImage(), blocks, flags, palette, 1, 0, 0)
        self.assertTrue(wrong.done)
        self.assertEqual(wrong.failed, "art file is the wrong version")
        self.assertIsNone(wrong.file)
        short = os.path.join(folder.name, "short.bin")
        with open(short, "wb") as handle:
            handle.write(self.data[:6] + bytes(10))
        cut = O.Painter(short)
        target = FakeImage()
        cut.start(target, blocks, flags, palette, 1, 0, 0)
        self.addCleanup(cut.close)
        self.assertTrue(cut.step(budget_ms=10 ** 9))
        self.assertEqual((cut.errors, cut.drawn, target.count("shape")), (len(blocks), 0, 0))


class TestAscii(unittest.TestCase):
    """The independent MicroPython take on Ascii-Motion's conversion techniques."""

    def setUp(self):
        self.A = M["mona_ascii"]
        inject(self, self.A, image=FakeImage, font=FAKE_FONT, color=FakeColor,
               vec2=fake_vec2, rect=fake_rect, shape=FakeShapes)

    def test_tables(self):
        A = self.A
        self.assertEqual((A.COLS, A.ROWS, A.CELL_W, A.CELL_H), (24, 18, 8, 12))
        self.assertEqual((A.WIDTH, A.HEIGHT), (A.COLS * A.CELL_W, A.ROWS * A.CELL_H))
        self.assertEqual(A.PALETTE_NAMES, ("Primer", "ANSI", "Phosphor", "Amber"))
        self.assertEqual(A.PRIMER, 0)
        for table in (A.RAMPS, A.BACKS, A.TINTS, A.BG_PERCENT):
            self.assertEqual(len(table), len(A.PALETTE_NAMES))
        for ramp in A.RAMPS:
            self.assertEqual(len(ramp), 10)
            self.assertEqual(ramp[0], " ")
        self.assertEqual(A.GLYPH_COUNT, len(A.CHARS))
        self.assertEqual(len(A.CHARS), 89)
        self.assertEqual(len(set(A.CHARS)), len(A.CHARS))
        self.assertTrue(all(32 <= ord(ch) < 127 for ch in A.CHARS))
        self.assertEqual(A.CHARS[0], " ")
        self.assertEqual(len(A.GLYPHS), 6 * A.GLYPH_COUNT)
        self.assertTrue(all(0 <= value <= 255 for value in A.GLYPHS))
        self.assertEqual(sorted(A.BAYER), list(range(16)))
        self.assertEqual(len(A.GAMMA), 256)
        self.assertEqual((A.GAMMA[0], A.GAMMA[255]), (0, 255))
        self.assertTrue(all(A.GAMMA[i] <= A.GAMMA[i + 1] for i in range(255)))

    def test_shape_vector_matching(self):
        A = self.A
        self.assertEqual(A.match_shape((0,) * 6), 0)
        self.assertEqual(A.CHARS[A.match_shape((255,) * 6)], "$")
        self.assertEqual(A.CHARS[A.match_shape((255, 255, 255, 0, 0, 0))], "F")
        self.assertEqual(A.CHARS[A.match_shape((0, 0, 0, 255, 255, 255))], "y")
        for vector in ((10, 200, 30, 90, 255, 0), (128,) * 6, (0, 255) * 3):
            self.assertIn(A.match_shape(vector), range(A.GLYPH_COUNT))

    def test_bayer_dither(self):
        A = self.A
        self.assertEqual([A.dither_index(level, 0, 0, 10) for level in (0, 64, 128, 200, 255)],
                         [0, 3, 5, 7, 9])
        for x in range(4):
            for y in range(4):
                self.assertEqual(A.dither_index(0, x, y, 10), 0)
                self.assertEqual(A.dither_index(255, x, y, 10), 9)
                steps = [A.dither_index(level, x, y, 10) for level in range(256)]
                self.assertEqual(steps, sorted(steps))

    def test_palette_colours(self):
        A = self.A
        self.assertEqual([A.colour_for(p, (110, 84, 240), 200) for p in range(4)],
                         [(163, 113, 247), (85, 85, 255), (38, 191, 76), (191, 132, 0)])
        self.assertEqual([A.cursor_colour(p) for p in range(4)],
                         [(230, 237, 243), (255, 255, 255), (51, 255, 102), (255, 176, 0)])
        self.assertEqual(A.blend((0, 0, 0), (200, 100, 50), 50), (100, 50, 25))
        self.assertEqual(A.blend((10, 20, 30), (200, 100, 50), 0), (10, 20, 30))
        self.assertEqual(A.blend((10, 20, 30), (200, 100, 50), 100), (200, 100, 50))
        self.assertEqual(A.hue(255, 0, 0, 255, 0), 0)
        self.assertEqual(A.pen_for((1, 2, 3)), (1, 2, 3, 255))
        for p in range(4):
            for rgb in ((0, 0, 0), (255, 255, 255), (110, 84, 240), (255, 0, 0)):
                for level in (0, 1, 128, 255):
                    out = A.colour_for(p, rgb, level)
                    self.assertEqual(len(out), 3)
                    self.assertTrue(all(isinstance(c, int) and 0 <= c <= 255 for c in out))

    def test_levels_and_cell_sampling(self):
        A = self.A
        raw = circle_raw()
        count = A.SAMPLE_W * A.SAMPLE_H
        levels = A.levels_from_raw(raw, count)
        self.assertEqual(len(levels), count)
        opaque = sum(1 for i in range(count) if raw[i * 4 + 3])
        self.assertEqual(sum(1 for value in levels if value), opaque)
        self.assertEqual(levels[0], 0)
        self.assertGreaterEqual(min(value for value in levels if value), A.FLOOR)
        self.assertEqual(max(levels), 255)
        self.assertEqual(A.cell_samples(levels, 12, 9), (255,) * 6)
        self.assertEqual(A.cell_samples(levels, 0, 0), (0,) * 6)
        self.assertEqual(A.cell_rgba(raw, 12, 9), (110, 84, 240, 255))
        self.assertEqual(A.cell_rgba(raw, 0, 0), (0, 0, 0, 0))
        means = A.cell_means(levels)
        self.assertEqual(len(means), A.COLS * A.ROWS)
        self.assertEqual((means[0], max(means)), (0, 255))
        self.assertEqual(A.edge_char(bytearray(A.COLS * A.ROWS), 5, 5, A.RAMPS[0]), " ")
        self.assertEqual(max(A.levels_from_raw(bytearray(count * 4), count)), 0)

    def test_every_style_and_palette_converts(self):
        A = self.A
        raw = circle_raw()
        levels = A.levels_from_raw(raw, A.SAMPLE_W * A.SAMPLE_H)
        means = A.cell_means(levels)
        centre = {
            A.SHAPES: '  "$$$$$$$$$$$$$$$$$$(  ',
            A.DITHER: "  .@@@@@@@@@@@@@@@@@@%  ",
            A.EDGES: "  ||::::::::::::::::||| ",
        }
        for style in (A.SHAPES, A.DITHER, A.EDGES):
            for palette in range(len(A.PALETTE_NAMES)):
                rows = [A.convert_row(style, palette, raw, levels, means if style == A.EDGES else None, y)
                        for y in range(A.ROWS)]
                self.assertEqual([len(row) for row in rows], [A.COLS] * A.ROWS)
                text = A.grid_text(rows)
                self.assertEqual(text[0], " " * A.COLS)
                self.assertEqual(text[-1], " " * A.COLS)
                self.assertGreaterEqual(len(text[9].strip()), 18)
                if palette == A.PRIMER:
                    self.assertEqual(text[9], centre[style])
                for row in rows:
                    for ch, fg, bg in row:
                        self.assertEqual(len(ch), 1)
                        for rgb in (fg, bg):
                            if rgb is not None:
                                self.assertTrue(all(0 <= c <= 255 for c in rgb), rgb)
                        if style == A.EDGES:
                            self.assertIsNone(bg)

    def test_view_types_itself_in_and_redraws(self):
        A = self.A
        view = A.AsciiView()
        target = FakeImage()
        self.assertFalse(view.draw(target, 0, 0, 0))
        self.assertFalse(view.step())
        self.assertFalse(view.typing)
        view.set_source(FakeImage(A.WIDTH, A.HEIGHT))
        self.assertTrue(view.typing)
        self.assertTrue(view._images())
        self.assertEqual((view.cache.width, view.cache.height, view.cache.font), (A.WIDTH, A.HEIGHT, "teatime"))
        self.assertEqual((view.sample.width, view.sample.height), (A.SAMPLE_W, A.SAMPLE_H))
        view.sample.raw = circle_raw()
        results = []
        for _ in range(20):
            results.append(view.step())
            if results[-1]:
                break
        self.assertEqual(results, [False] * 8 + [True])
        self.assertTrue(view.ready)
        self.assertFalse(view.typing)
        self.assertIsNone(view.raw)
        self.assertGreater(view.cache.count("text"), 100)
        self.assertGreaterEqual(view.cache.count("shape"), A.ROWS)
        self.assertTrue(view.draw(target, 3, 4, 0))
        self.assertEqual(target.calls[-1], ("blit", view.cache, ("vec2", 3, 4)))
        self.assertEqual(target.count("shape"), 0)
        view.set_mode(A.SHAPES, A.PRIMER)
        self.assertTrue(view.ready)
        view.set_mode(A.EDGES, 2)
        self.assertEqual((view.ready, view.typing, view.row, view.style, view.palette), (False, True, 0, A.EDGES, 2))
        view.step()
        cursor = FakeImage()
        self.assertTrue(view.draw(cursor, 3, 4, 0))
        self.assertEqual(cursor.calls[-1][1].args, (4, 4 + 2 * A.CELL_H + 1, A.CELL_W - 2, A.CELL_H - 2))
        self.assertTrue(view.draw(cursor, 3, 4, A.BLINK_MS))
        self.assertEqual(cursor.count("shape"), 1)
        view.clear()
        self.assertFalse(view.typing)
        self.assertFalse(view.step())

    def test_view_paces_the_type_in_by_badge_time(self):
        A = self.A
        end = ((A.ROWS - 1) * A.ROW_MS // 80 + 1) * 80

        def reveal(frame_ms):
            view = A.AsciiView()
            view.set_source(FakeImage(A.WIDTH, A.HEIGHT))
            self.assertTrue(view._images())
            view.sample.raw = circle_raw()
            seen = []
            for elapsed in range(0, end + 1, frame_ms):
                view.step(2, 9000 + elapsed)
                if elapsed % 80 == 0:
                    seen.append((elapsed, A.ROWS if view.ready else view.row, view.ready))
            return seen

        fast, slow = reveal(16), reveal(40)
        self.assertEqual(fast, slow)
        for elapsed, typed, ready in fast:
            due = elapsed // A.ROW_MS + 1
            self.assertEqual(typed, min(A.ROWS, due))
            self.assertEqual(ready, due >= A.ROWS)
        self.assertTrue(fast[-1][2])

    def test_view_row_cap_still_bounds_a_late_frame(self):
        A = self.A
        view = A.AsciiView()
        view.set_source(FakeImage(A.WIDTH, A.HEIGHT))
        self.assertTrue(view._images())
        view.sample.raw = circle_raw()
        self.assertFalse(view.step(2, 0))
        self.assertEqual(view.row, 1)
        self.assertFalse(view.step(2, 0))
        self.assertEqual(view.row, 1)
        self.assertFalse(view.step(2, 60000))
        self.assertEqual(view.row, 3)
        self.assertFalse(view.step(1, 120000))
        self.assertEqual(view.row, 4)
        view.set_mode(A.EDGES, 2)
        self.assertFalse(view.step(2, 180000))
        self.assertEqual(view.row, 1)
        self.assertFalse(view.step(2, 180000 + A.ROW_MS))
        self.assertEqual(view.row, 2)

    def test_view_without_memory_degrades(self):
        A = self.A
        inject(self, A, image=BrokenImage)
        view = A.AsciiView()
        view.set_source(FakeImage(A.WIDTH, A.HEIGHT))
        self.assertFalse(view.step())
        self.assertTrue(view.failed)
        self.assertFalse(view.typing)
        self.assertFalse(view.draw(FakeImage(), 0, 0, 0))


class Recorder:
    def __init__(self, fail_at=None):
        self.sent = []
        self.fail_at = fail_at

    def __call__(self, address, command):
        if self.fail_at is not None and len(self.sent) == self.fail_at:
            raise OSError("pio stalled")
        self.sent.append((address, command))


class BrokenStateApi:
    def __init__(self, stored=None):
        self.stored = stored

    def load(self, key, target):
        raise OSError(2, "no state")

    def save(self, key, value):
        self.stored = value


class TestIr(unittest.TestCase):
    """NEC framing on 0x4C, the 0x45/0x88 quest beam and the IrPort lifecycle."""

    def setUp(self):
        self.I = M["mona_ir"]
        self.D = M["mona_dna"]

    def feed(self, decoder, data, now=0, spacing=80):
        found = []
        for byte in data:
            hit = decoder.push(byte, now)
            if hit is not None:
                found.append((now, hit))
            now += spacing
        return found, now

    def test_addresses_and_remotes(self):
        I = self.I
        self.assertEqual((I.DNA_ADDRESS, I.QUEST_ADDRESS, I.QUEST_CODE, I.QUEST_NUMBER), (0x4C, 0x45, 0x88, 8))
        self.assertEqual((I.TX_PIN, I.RX_PIN), (16, 17))
        self.assertNotIn((0, 0), I.TX_SLOTS)
        for remote, address in ((I.DnaRemote(), 0x4C), (I.QuestRemote(), 0x45)):
            self.assertEqual(remote.ADDRESS, address)
            self.assertEqual(remote.BUTTON_CODES, {})
            self.assertTrue(remote.NAME.startswith("AsciiMona"))
            self.assertIsNone(remote.on_any)
            self.assertIsNone(remote.on_known)

    def test_crc8_and_packet_layout(self):
        I, D = self.I, self.D
        self.assertEqual(I.crc8(b"123456789"), 0xF4)
        self.assertEqual(I.crc8(b""), 0)
        for handle, size in (("octocat", 31), ("mona", 28), ("ada", 27), ("wmarkus", 31), ("", 24)):
            dna = D.dna_for(handle or "mystery")
            packet = I.encode_packet(handle, dna)
            self.assertEqual(len(packet), size)
            self.assertEqual(packet[:2], [0xA5, 0x5A])
            self.assertEqual(packet[2], len(packet) - 4)
            self.assertEqual(packet[3], I.VERSION)
            self.assertEqual(tuple(packet[4:4 + D.SIZE]), dna)
            self.assertEqual(bytes(packet[4 + D.SIZE:-1]), handle.encode())
            self.assertEqual(packet[-1], I.crc8(packet[2:-1]))
            self.assertTrue(all(0 <= byte <= 255 for byte in packet))
            self.assertTrue(all(byte < 0x80 for byte in dna))
        self.assertEqual(I.encode_packet(None, D.dna_for("x")), I.encode_packet("", D.dna_for("x")))
        for handle, dna in (("bad handle", D.dna_for("x")), ("x" * 40, D.dna_for("x")),
                            ("ok", (0,) * 5), ("ok", None)):
            with self.assertRaises(ValueError):
                I.encode_packet(handle, dna)

    def test_payload_round_trip_and_rejections(self):
        I, D = self.I, self.D
        for handle in ("octocat", "MonaLisa", "a", "x" * 39, "hub-ot", ""):
            dna = D.dna_for(handle or "y")
            payload = I.encode_packet(handle, dna)[3:-1]
            self.assertEqual(I.parse_payload(payload), (handle, dna))
            self.assertEqual(I.parse_payload(bytes(payload)), (handle, dna))
        good = I.encode_packet("octocat", D.dna_for("octocat"))[3:-1]
        broken = []
        broken.append(good[:I.MIN_LEN - 1])
        broken.append([3] + good[1:])
        too_big = list(good)
        too_big[1] = D.LIMITS[0]
        broken.append(too_big)
        high = list(good)
        high[2] = 200
        broken.append(high)
        for bad_char in (32, 127, 10):
            odd = list(good)
            odd[-1] = bad_char
            broken.append(odd)
        broken.append(list(good[:I.MIN_LEN]) + [ord("-")] + list(b"ab"))
        broken.append(list(good[:I.MIN_LEN]) + [ord("a")] * 40)
        for payload in broken:
            self.assertIsNone(I.parse_payload(payload), payload)

    def test_beam_frames_carry_two_copies_then_the_quest_code(self):
        I, D = self.I, self.D
        for handle, total in (("octocat", 65), ("ada", 57)):
            dna = D.dna_for(handle)
            packet = I.encode_packet(handle, dna)
            frames = I.beam_frames(handle, dna)
            self.assertEqual(len(frames), total)
            self.assertEqual(len(frames), 2 * len(packet) + I.QUEST_REPEATS)
            self.assertEqual([f[1] for f in frames[:len(packet)]], packet)
            self.assertEqual([f[1] for f in frames[len(packet):2 * len(packet)]], packet)
            self.assertEqual(frames[0][2], 0)
            self.assertEqual(frames[len(packet)][2], I.COPY_GAP_MS)
            self.assertEqual(frames[-3:], [(0x45, 0x88, I.QUEST_GAP_MS), (0x45, 0x88, 0), (0x45, 0x88, 0)])
            for address, command, wait in frames:
                self.assertIn(address, (0x4C, 0x45))
                self.assertTrue(0 <= command <= 255)
                self.assertGreaterEqual(wait, 0)
                if address == 0x45:
                    self.assertEqual(command, 0x88)

    def test_decoder_accepts_once_then_dedupes(self):
        I, D = self.I, self.D
        dna = D.dna_for("octocat")
        packet = I.encode_packet("octocat", dna)
        decoder = I.Decoder()
        found, now = self.feed(decoder, packet)
        self.assertEqual(found, [((len(packet) - 1) * 80, ("octocat", dna))])
        again, now = self.feed(decoder, packet, now + I.COPY_GAP_MS)
        self.assertEqual(again, [])
        later, _ = self.feed(decoder, packet, now + I.DEDUPE_MS)
        self.assertEqual([hit for _at, hit in later], [("octocat", dna)])
        other = I.encode_packet("ada", D.dna_for("ada"))
        fresh = I.Decoder()
        self.feed(fresh, packet)
        hits, _ = self.feed(fresh, other, 3000)
        self.assertEqual([hit[0] for _at, hit in hits], ["ada"])

    def test_decoder_survives_noise_drops_and_gaps(self):
        I, D = self.I, self.D
        dna = D.dna_for("mona")
        packet = I.encode_packet("mona", dna)
        decoder = I.Decoder()
        noise = [0xA5, 0x5A, 0x40, 0xA5, 7, 0x5A, 0xFF, 0x00]
        found, _ = self.feed(decoder, noise + packet)
        self.assertEqual([hit for _at, hit in found], [("mona", dna)])
        decoder = I.Decoder()
        corrupt = list(packet)
        corrupt[10] ^= 0x01
        found, now = self.feed(decoder, corrupt)
        self.assertEqual(found, [])
        found, _ = self.feed(decoder, packet, now + I.COPY_GAP_MS)
        self.assertEqual([hit for _at, hit in found], [("mona", dna)])
        decoder = I.Decoder()
        dropped = packet[:12] + packet[13:]
        found, now = self.feed(decoder, dropped)
        self.assertEqual(found, [])
        found, _ = self.feed(decoder, packet, now + I.COPY_GAP_MS)
        self.assertEqual([hit for _at, hit in found], [("mona", dna)])
        decoder = I.Decoder()
        _, now = self.feed(decoder, packet[:15])
        found, _ = self.feed(decoder, packet[15:], now + I.GAP_MS + 100)
        self.assertEqual(found, [])
        long_handle = "a" * 39
        long_dna = D.dna_for(long_handle)
        decoder = I.Decoder()
        found, _ = self.feed(decoder, noise + I.encode_packet(long_handle, long_dna))
        self.assertEqual([hit for _at, hit in found], [(long_handle, long_dna)])

    def test_beam_paces_one_frame_per_update(self):
        I, D = self.I, self.D
        dna = D.dna_for("octocat")
        beam = I.Beam("octocat", dna, True)
        send = Recorder()
        self.assertEqual(beam.progress(), 0)
        self.assertTrue(beam.step(0, send))
        self.assertFalse(beam.step(I.FRAME_MS - 1, send))
        self.assertTrue(beam.step(I.FRAME_MS, send))
        now = I.FRAME_MS
        quest_seen = False
        for _ in range(2000):
            if beam.done:
                break
            now += 16
            quest_seen = quest_seen or beam.in_quest()
            beam.step(now, send)
        self.assertTrue(beam.done)
        self.assertTrue(quest_seen)
        self.assertFalse(beam.in_quest())
        self.assertEqual(beam.progress(), 100)
        self.assertEqual(send.sent, [(a, c) for a, c, _w in beam.frames])
        self.assertGreaterEqual(now, (len(beam.frames) - 1) * I.FRAME_MS + I.COPY_GAP_MS + I.QUEST_GAP_MS)
        self.assertFalse(beam.step(now + 10000, send))
        self.assertEqual(beam.error, "")
        quiet = I.Beam("", dna, False)
        for step in range(5000):
            if quiet.done:
                break
            quiet.step(step * 100, None)
        self.assertTrue(quiet.done)
        failing = I.Beam("ada", D.dna_for("ada"), True)
        bad = Recorder(fail_at=3)
        for step in range(10):
            failing.step(step * 1000, bad)
        self.assertTrue(failing.done)
        self.assertEqual(failing.error, "IR send failed: pio stalled")
        self.assertEqual(len(bad.sent), 3)

    def test_mark_quest_matches_the_quest_app(self):
        I = self.I
        state = FakeState()
        self.assertTrue(I.mark_quest(state))
        self.assertEqual(state.stored["quest"], {"completed": [8]})
        self.assertFalse(I.mark_quest(state))
        kept = FakeState({"quest": {"completed": [1, 3], "other": "x"}})
        self.assertTrue(I.mark_quest(kept))
        self.assertEqual(kept.stored["quest"], {"completed": [1, 3, 8], "other": "x"})
        odd = FakeState({"quest": {"completed": "nope"}})
        self.assertTrue(I.mark_quest(odd))
        self.assertEqual(odd.stored["quest"]["completed"], [8])
        unreadable = BrokenStateApi()
        self.assertTrue(I.mark_quest(unreadable))
        self.assertEqual(unreadable.stored, {"completed": [8]})
        self.assertFalse(I.mark_quest(FakeState(fail_save=True)))

    def test_port_listens_on_both_addresses(self):
        I, D = self.I, self.D
        ir = install_ir(self)
        port = I.IrPort()
        self.assertTrue(port.listen())
        self.assertEqual(sorted(ir.bound), [0x45, 0x4C])
        dna = D.dna_for("ada")
        for byte in I.encode_packet("ada", dna):
            ir.deliver(0x4C, byte)
        self.assertEqual(port.update(1000), [("mona", "ada", dna)])
        ir.deliver(0x45, 0x10)
        self.assertEqual(port.update(2000), [])
        ir.deliver(0x45, 0x88)
        ir.deliver(0x45, 0x88)
        self.assertEqual(port.update(3000), [("quest",)])
        self.assertEqual(port.update(4000), [])
        for _ in range(I.INBOX_MAX + 50):
            ir.deliver(0x4C, 0)
        self.assertEqual(len(port.inbox), I.INBOX_MAX)
        port.close()
        self.assertTrue(ir.closed)
        self.assertFalse(port.listening)
        port.close()

    def test_port_listen_degrades(self):
        I = self.I
        install_ir(self, busy=(0x4C, 0x45))
        port = I.IrPort()
        self.assertFalse(port.listen())
        self.assertEqual(port.note, "IR receive busy")
        install_ir(self, busy=(0x45,))
        self.assertTrue(I.IrPort().listen())
        install_modules(self, {"badgeware": None, "badgeware.ir": None})
        port = I.IrPort()
        self.assertFalse(port.listen())
        self.assertEqual(port.note, "IR receive unavailable")
        self.assertEqual(port.update(0), [])
        port.close()

    def test_sender_slots_skip_busy_state_machines(self):
        I = self.I
        sender = sender_class()
        install_sender(self, sender)
        port = I.IrPort()
        self.assertTrue(port.open_sender())
        self.assertTrue(port.open_sender())
        self.assertEqual(len(sender.made), 1)
        tx = sender.made[0]
        self.assertEqual((tx.pin, tx.pio, tx.sm, tx.started), (16, 0, 1, True))
        port.close()
        self.assertTrue(tx.stopped)
        sender = sender_class(fail_construct=((0, 1),), fail_start=((0, 2),))
        install_sender(self, sender)
        port = I.IrPort()
        self.assertTrue(port.open_sender())
        self.assertEqual([(t.pio, t.sm) for t in sender.made], [(0, 2), (0, 3)])
        self.assertTrue(sender.made[0].stopped)
        self.assertIs(port.tx, sender.made[1])
        sender = sender_class(fail_construct=I.TX_SLOTS)
        install_sender(self, sender)
        port = I.IrPort()
        self.assertFalse(port.open_sender())
        self.assertEqual(port.note, "IR send busy: simulated beam")
        install_modules(self, {"aye_arr": None, "aye_arr.nec": None})
        port = I.IrPort()
        self.assertFalse(port.open_sender())
        self.assertEqual(port.note, "IR send unavailable: simulated beam")

    def run_beam(self, port, now=0, limit=3000):
        events = []
        for _ in range(limit):
            now += 20
            got = port.update(now)
            events.extend(got)
            if any(event[0] == "sent" for event in got):
                return events, now
        self.fail("beam never finished")

    def test_live_beam_ignores_its_own_echo(self):
        I, D = self.I, self.D
        ir = install_ir(self)
        sender = sender_class()
        install_sender(self, sender)
        port = I.IrPort()
        port.listen()
        dna = D.dna_for("octocat")
        self.assertTrue(port.start_beam("octocat", dna))
        self.assertTrue(port.beaming)
        self.assertFalse(port.start_beam("octocat", dna))
        self.assertTrue(port.beam.live)
        packet = I.encode_packet("octocat", dna)
        port.update(0)
        for byte in packet:
            ir.deliver(0x4C, byte)
        ir.deliver(0x45, 0x88)
        events, now = self.run_beam(port)
        self.assertEqual(events, [("sent", True, "")])
        self.assertEqual(sender.made[0].sent, [(a, c) for a, c, _w in I.beam_frames("octocat", dna)])
        self.assertEqual(sender.made[0].sent.count((0x45, 0x88)), I.QUEST_REPEATS)
        self.assertNotIn((0x45, 0xF0), sender.made[0].sent)
        self.assertFalse(port.beaming)
        for byte in packet:
            ir.deliver(0x4C, byte)
        self.assertEqual(port.update(now + I.ECHO_MS - 1), [])
        other = D.dna_for("ada")
        for byte in I.encode_packet("ada", other):
            ir.deliver(0x4C, byte)
        self.assertEqual(port.update(now + I.ECHO_MS + 1), [("mona", "ada", other)])
        port.close()
        self.assertTrue(sender.made[0].stopped)
        self.assertIsNone(port.beam)

    def test_beam_failures_and_simulated_beams(self):
        I, D = self.I, self.D
        install_sender(self, sender_class(fail_send=True))
        port = I.IrPort()
        port.start_beam("ada", D.dna_for("ada"))
        events, _ = self.run_beam(port)
        self.assertEqual(events, [("sent", False, "IR send failed: pio stalled")])
        install_modules(self, {"aye_arr": None, "aye_arr.nec": None})
        port = I.IrPort()
        self.assertTrue(port.start_beam("", D.dna_for("mystery")))
        self.assertFalse(port.beam.live)
        events, _ = self.run_beam(port)
        self.assertEqual(events, [("sent", True, "")])
        self.assertEqual(port.note, "IR send unavailable: simulated beam")


class TestLink(unittest.TestCase):
    """The Contacts-style Bluetooth proximity swap (badgeware.link)."""

    def setUp(self):
        self.L = M["mona_link"]
        self.D = M["mona_dna"]

    def badge(self, handle, name, capacity=48):
        L, D = self.L, self.D
        link = FakeLink(capacity)
        mona = L.MonaLink(L.make_card(handle, D.dna_for(handle), name))
        self.assertTrue(mona.open(link_module(link)))
        self.assertEqual(link.games, [L.GAME])
        return mona, link

    def frames(self, badges, start, count, step=50, idle=True):
        got = [[] for _ in badges]
        now = start
        for _ in range(count):
            for index, mona in enumerate(badges):
                found = mona.update(now, idle)
                if found is not None:
                    got[index].append(found)
            now += step
        return got, now

    def test_cards_round_trip_and_accept_contacts_cards(self):
        L, D = self.L, self.D
        dna = D.dna_for("octocat")
        card = L.make_card("octocat", dna, "The Octocat")
        self.assertEqual(card, {"v": 2, "github": "octocat", "dna": D.dna_hex(dna), "name": "The Octocat"})
        self.assertNotIn("name", L.make_card("", dna, "  "))
        self.assertEqual(L.read_card(card), ("octocat", dna, "The Octocat"))
        self.assertEqual(L.decode_card(json.dumps(card).encode()), ("octocat", dna, "The Octocat"))
        contact = {"name": "Ann", "github": "Octocat", "linkedin": "ann"}
        self.assertEqual(L.read_card(contact), ("Octocat", dna, "Ann"))
        self.assertEqual(L.read_card({"github": "@Octocat"})[0], "octocat")
        self.assertEqual(L.read_card({"github": "https://github.com/Hubot"})[:2], ("hubot", D.dna_for("hubot")))
        self.assertEqual(L.read_card({"github": "", "dna": D.dna_hex(dna)}), ("", dna, ""))
        self.assertEqual(L.read_card({"github": "ada", "dna": "zz"}), ("ada", D.dna_for("ada"), ""))
        name = L.read_card({"github": "ada", "name": "[A]\nB" + "x" * 60})[2]
        self.assertEqual(len(name), L.MAX_NAME)
        self.assertTrue(name.startswith("(A) B"))
        for bad in ({"github": "bad handle!"}, {"github": 5}, {"github": "  "}, {}, "x", None, [1]):
            self.assertIsNone(L.read_card(bad), bad)
        for bad in (b"not json", b"[1,2]", b"\xff", b""):
            self.assertIsNone(L.decode_card(bad), bad)

    def test_chunking_survives_small_links_and_any_order(self):
        L = self.L
        payload = bytes(range(50))
        link = FakeLink(capacity=10)
        outbox = L.Outbox(b"C", payload)
        self.assertFalse(outbox.done)
        self.assertFalse(outbox.pump(link))
        self.assertEqual(link.sent, [])
        link.linked = True
        self.assertTrue(outbox.pump(link))
        self.assertTrue(outbox.done)
        self.assertEqual(len(link.sent), 8)
        self.assertTrue(all(len(message) <= 10 and message[:1] == b"C" for message in link.sent))
        inbox = L.Inbox()
        results = [inbox.add(message) for message in reversed(link.sent)]
        self.assertEqual(results[:-1], [None] * 7)
        self.assertEqual(results[-1], payload)
        self.assertIsNone(inbox.add(b"C"))
        self.assertIsNone(inbox.add(b"C\x00\x00"))
        self.assertIsNone(inbox.add(b"C\x02\x02x"))
        inbox.add(b"C\x00\x03a")
        self.assertIsNone(inbox.add(b"C\x00\x02b"))
        self.assertEqual(inbox.add(b"C\x01\x02c"), b"bc")

    def test_two_badges_swap_cards_then_share(self):
        L, D = self.L, self.D
        ann, ann_link = self.badge("octocat", "Ann")
        bea, bea_link = self.badge("ada", "Bea", capacity=20)
        self.assertIsNone(ann.hint(0))
        self.assertEqual(ann.lights(0, True), (0.25,))
        self.assertIsNone(ann.update(0, True))
        pair(ann_link, bea_link)
        got, now = self.frames((ann, bea), 100, 3)
        self.assertEqual(got[0], [("card", "ada", D.dna_for("ada"), "Bea")])
        self.assertEqual(got[1], [("card", "octocat", D.dna_for("octocat"), "Ann")])
        for mona in (ann, bea):
            self.assertTrue(mona.lingering)
            self.assertEqual(mona.status, "swapped")
            self.assertEqual(mona.hint(now), ("linked: SELECT shares by link too", None))
        self.assertGreater(len(bea_link.sent), 2)
        shared = D.dna_for("mona")
        self.assertTrue(ann.share_mona("mona", shared, "Mona", now))
        got, now = self.frames((ann, bea), now, 2)
        self.assertEqual(got, [[], [("share", "mona", shared, "Mona")]])
        got, now = self.frames((ann, bea), now + L.LINGER_MS, 2)
        self.assertEqual(got, [[], []])
        self.assertEqual((ann.state, bea.state), (L.IDLE, L.IDLE))
        self.assertFalse(ann_link.linked)
        self.assertEqual(ann.prox.rested[-1], "id-b")
        self.assertFalse(ann.share_mona("mona", shared, "", now))

    def test_swap_progress_hints_and_lights(self):
        L = self.L
        ann, ann_link = self.badge("octocat", "Ann")
        bea, bea_link = self.badge("ada", "Bea")
        pair(ann_link, bea_link)
        ann.update(0, True)
        self.assertTrue(ann.swapping)
        self.assertEqual(ann.partner_name, "Bea")
        self.assertEqual(ann.hint(0), ("swapping with Bea", None))
        self.assertEqual(ann.lights(0, True), (0.5,))
        self.assertIsNone(bea.lights(0, False))

    def test_busy_badges_refuse_a_link(self):
        L = self.L
        ann, ann_link = self.badge("octocat", "Ann")
        bea, bea_link = self.badge("ada", "Bea")
        pair(ann_link, bea_link)
        self.assertIsNone(ann.update(0, False))
        self.assertEqual(ann.state, L.IDLE)
        self.assertEqual(ann_link.left, 1)
        self.assertFalse(bea_link.linked)

    def test_walking_away_mid_swap(self):
        L, D = self.L, self.D
        ann, ann_link = self.badge("octocat", "Ann")
        bea, bea_link = self.badge("ada", "Bea")
        pair(ann_link, bea_link)
        ann.update(0, True)
        ann_link.linked = False
        self.assertIsNone(ann.update(50, True))
        self.assertEqual(ann.status, "they walked away")
        self.assertEqual(ann.prox.cleared, 1)
        self.assertEqual(ann.state, L.IDLE)
        carol, carol_link = self.badge("octocat", "Carol")
        dan, dan_link = self.badge("hubot", "Dan")
        pair(carol_link, dan_link)
        dan.update(0, True)
        carol.update(0, True)
        self.assertIsNotNone(carol.got)
        self.assertFalse(carol.acked)
        carol_link.linked = False
        self.assertEqual(carol.update(50, True), ("card", "hubot", D.dna_for("hubot"), "Dan"))
        self.assertEqual(carol.prox.rested, ["id-b"])

    def test_silent_partner_times_out(self):
        L = self.L
        ann, ann_link = self.badge("octocat", "Ann")
        _bea, bea_link = self.badge("ada", "Bea")
        pair(ann_link, bea_link)
        ann.update(0, True)
        self.assertIsNone(ann.update(L.SWAP_MS - 1, True))
        self.assertTrue(ann.swapping)
        self.assertIsNone(ann.update(L.SWAP_MS + 1, True))
        self.assertEqual(ann.status, "swap failed, try again")
        self.assertEqual(ann_link.left, 1)
        self.assertEqual(ann.state, L.IDLE)

    def test_missing_or_broken_link_never_crashes(self):
        L, D = self.L, self.D
        install_modules(self, {"badgeware": None, "badgeware.link": None})
        mona = L.MonaLink(L.make_card("octocat", D.dna_for("octocat")))
        self.assertFalse(mona.open())
        self.assertEqual(mona.error, "badge link unavailable")
        self.assertFalse(mona.available)
        self.assertIsNone(mona.update(0, True))
        self.assertIsNone(mona.lights(0, True))
        self.assertIsNone(mona.hint(0))
        self.assertFalse(mona.share_mona("ada", D.dna_for("ada"), "", 0))
        mona.close()

        def refuse(game):
            raise OSError("radio off")

        self.assertFalse(L.MonaLink({}).open(types.SimpleNamespace(Link=refuse, Proximity=FakeProximity)))
        ann, ann_link = self.badge("octocat", "Ann")
        bea, bea_link = self.badge("ada", "Bea")
        pair(ann_link, bea_link)
        ann.update(0, True)

        def explode():
            raise OSError("radio glitch")

        ann_link.receive = explode
        self.assertIsNone(ann.update(10, True))
        self.assertEqual(ann.error, "link error: radio glitch")
        self.assertEqual(ann.state, L.IDLE)
        ann.set_card(L.make_card("mona", D.dna_for("mona")))
        self.assertEqual(ann.card["github"], "mona")
        ann.close()
        self.assertTrue(ann_link.closed)
        self.assertFalse(ann.available)
        ann.close()


class TestWheel(unittest.TestCase):
    """The arcade letter wheel for typing a handle with the badge buttons."""

    def setUp(self):
        self.W = M["mona_wheel"]
        self.D = M["mona_dna"]

    def tap(self, wheel, now, name):
        result = wheel.update(now, (name,), (name,))
        wheel.update(now + 20, (), ())
        return result

    def test_alphabet_covers_every_handle_character(self):
        W, D = self.W, self.D
        self.assertEqual(W.CHARS[W.BLANK], " ")
        self.assertEqual(W.CHARS[1:], "abcdefghijklmnopqrstuvwxyz0123456789-")
        self.assertEqual(D.MAX_HANDLE, 39)

    def test_load_cleans_text_into_slots(self):
        W, D = self.W, self.D
        empty = W.Wheel()
        self.assertEqual((empty.slots, empty.cursor, empty.text), ([W.BLANK], 0, ""))
        self.assertTrue(empty.problem)
        wheel = W.Wheel("Octo-Cat!")
        self.assertEqual((wheel.text, wheel.cursor, wheel.problem), ("octo-cat", 7, ""))
        self.assertEqual(W.Wheel(" a b ").text, "ab")
        self.assertEqual(W.Wheel("a" * 50).text, "a" * D.MAX_HANDLE)
        for junk in (None, 5, "!!!"):
            self.assertEqual(W.Wheel(junk).slots, [W.BLANK])
        for text in ("-a", "a-", "a--b"):
            self.assertEqual(W.Wheel(text).problem, D.handle_problem(text))
            self.assertTrue(W.Wheel(text).problem)

    def test_spinning_wraps_around_the_wheel(self):
        W = self.W
        wheel = W.Wheel()
        self.assertEqual((wheel.letter(), wheel.letter(1), wheel.letter(-1)), (" ", "a", "-"))
        seen = []
        for _ in range(len(W.CHARS)):
            wheel.spin(1)
            seen.append(wheel.letter())
        self.assertEqual("".join(seen), W.CHARS[1:] + " ")
        wheel.spin(-1)
        self.assertEqual(wheel.text, "-")

    def test_cursor_moves_add_and_drop_slots(self):
        W, D = self.W, self.D
        wheel = W.Wheel()
        wheel.right()
        self.assertEqual((wheel.slots, wheel.cursor), ([W.BLANK], 0))
        wheel.spin(1)
        wheel.right()
        self.assertEqual((wheel.slots, wheel.cursor), ([1, W.BLANK], 1))
        wheel.right()
        self.assertEqual(len(wheel.slots), 2)
        wheel.left()
        self.assertEqual((wheel.slots, wheel.cursor), ([1], 0))
        wheel.left()
        self.assertEqual(wheel.cursor, 0)
        middle = W.Wheel("abc")
        middle.left()
        self.assertEqual((middle.text, middle.cursor), ("abc", 1))
        middle.spin(-2)
        self.assertEqual(middle.text, "ac")
        full = W.Wheel("a" * D.MAX_HANDLE)
        full.right()
        self.assertEqual((len(full.slots), full.cursor), (D.MAX_HANDLE, D.MAX_HANDLE - 1))

    def test_delete_and_window(self):
        W = self.W
        wheel = W.Wheel("abc")
        wheel.cursor = 1
        wheel.nudge = "nope"
        wheel.delete()
        self.assertEqual((wheel.text, wheel.cursor, wheel.nudge), ("ac", 1, ""))
        wheel.delete()
        self.assertEqual((wheel.text, wheel.cursor), ("a", 0))
        wheel.delete()
        wheel.delete()
        self.assertEqual(wheel.slots, [W.BLANK])
        long = W.Wheel("abcdefghij")
        for cursor, first in ((0, 0), (3, 1), (9, 5)):
            long.cursor = cursor
            start, slots = long.window(5)
            self.assertEqual(start, first)
            self.assertEqual(slots, long.slots[first:first + 5])
            self.assertTrue(start <= cursor < start + len(slots))
        self.assertEqual(W.Wheel("ab").window(5), (0, [1, 2]))

    def test_buttons_type_a_handle_and_accept_it(self):
        W = self.W
        wheel = W.Wheel()
        now = 0
        for index, ch in enumerate("mona"):
            if index:
                self.assertIsNone(self.tap(wheel, now, "right"))
                now += 100
            for _ in range(W.CHARS.find(ch)):
                self.assertIsNone(self.tap(wheel, now, "up"))
                now += 100
        self.assertEqual(wheel.text, "mona")
        self.assertEqual(wheel.update(now, ("select",), ("select",)), "done")
        self.assertEqual(wheel.update(now, ("back",), ("back",)), "cancel")
        self.assertEqual(wheel.update(now, ("back", "select"), ("back", "select")), "cancel")

    def test_holding_a_direction_repeats(self):
        W = self.W
        wheel = W.Wheel()
        wheel.update(0, ("up",), ("up",))
        self.assertEqual(wheel.text, "a")
        wheel.update(W.REPEAT_DELAY_MS - 1, (), ("up",))
        self.assertEqual(wheel.text, "a")
        now = W.REPEAT_DELAY_MS
        for expected in "bcd":
            wheel.update(now, (), ("up",))
            self.assertEqual(wheel.text, expected)
            wheel.update(now + W.REPEAT_MS - 1, (), ("up",))
            self.assertEqual(wheel.text, expected)
            now += W.REPEAT_MS
        wheel.update(now, (), ())
        self.assertIsNone(wheel.repeat)
        wheel.update(now + 1000, (), ("up",))
        self.assertEqual(wheel.text, "d")
        wheel.update(now + 2000, ("down",), ("down",))
        wheel.update(now + 2000 + W.REPEAT_DELAY_MS, (), ("down",))
        self.assertEqual(wheel.text, "b")

    def test_select_refuses_invalid_handles(self):
        W, D = self.W, self.D
        for text in ("", "a-", "a--b"):
            wheel = W.Wheel(text)
            self.assertIsNone(wheel.update(0, ("select",), ("select",)))
            self.assertEqual(wheel.nudge, D.handle_problem(text))
        wheel = W.Wheel("a-")
        wheel.update(0, ("select",), ("select",))
        self.assertTrue(wheel.nudge)
        self.assertIsNone(wheel.update(10, ("menu",), ("menu",)))
        self.assertEqual((wheel.text, wheel.nudge), ("a", ""))
        self.assertEqual(wheel.update(20, ("select",), ("select",)), "done")


# Network fakes ---------------------------------------------------------------


class FakeResponse:
    def __init__(self, code, data=None, broken_json=False):
        self.status_code = code
        self.data = data
        self.broken_json = broken_json
        self.closed = False

    def json(self):
        if self.broken_json:
            raise ValueError("syntax error in JSON")
        return self.data

    def close(self):
        self.closed = True


class FakeRequests:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class FakeWifi:
    def __init__(self, connected=False, status=(1, "joining"), fail_connect=False):
        self.connected = connected
        self.code = status
        self.fail_connect = fail_connect
        self.calls = []

    def is_connected(self):
        return self.connected

    def connect(self, timeout=None, retries=None):
        self.calls.append((timeout, retries))
        if self.fail_connect:
            raise OSError("radio off")
        return self.connected

    def status(self):
        return self.code


class FakeDownload:
    """The firmware's async fetch request: truthy once the file is written."""

    def __init__(self):
        self.done = False
        self.error = None
        self.state = "Idle"
        self.path = None

    def __bool__(self):
        return self.done

    def to(self, path):
        self.path = path
        return self


class FakeFetch:
    def __init__(self, fail=None):
        self.AsyncFetch = type("AsyncFetch", (), {"MAX_HEADER_BYTES": 1024})
        self.fail = fail
        self.calls = []
        self.download = FakeDownload()

    def url(self, url, headers=None):
        self.calls.append((url, headers))
        if self.fail is not None:
            raise self.fail
        return self.download


def loader(**modules):
    return modules.get


class TestNet(unittest.TestCase):
    """The optional api.github.com profile lookup."""

    def setUp(self):
        self.N = M["mona_net"]

    def run_lookup(self, lookup, start=0, frames=6):
        for step in range(frames):
            result = lookup.update(start + step * 10)
            if result is not None:
                return result
        return None

    def temp_state(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        state = os.path.join(folder.name, "state")
        temp = os.path.join(state, "profile.tmp")
        inject(self, self.N, STATE_DIR=state, TEMP=temp)
        return state, temp

    def test_firmware_modules_load_lazily(self):
        N = self.N
        wifi = FakeWifi()
        install_modules(self, {"wifi": wifi, "fetch": None, "missing_details": None})
        self.assertIs(N.load_module("wifi"), wifi)
        self.assertIsNone(N.load_module("fetch"))
        self.assertIsNone(N.load_module("missing_details"))
        self.assertIsNone(N.load_module("os"))

    def test_token_only_goes_to_the_github_api(self):
        N = self.N
        self.assertEqual(N.token(loader(secrets=types.SimpleNamespace(GITHUB_TOKEN="  tok-123  "))), "tok-123")
        for secrets in (None, types.SimpleNamespace(), types.SimpleNamespace(GITHUB_TOKEN=None)):
            self.assertEqual(N.token(loader(secrets=secrets)), "")
        api = N.API + "octocat"
        self.assertEqual(N.headers_for(api, "tok"), {"User-Agent": N.USER_AGENT, "Authorization": "Bearer tok"})
        self.assertEqual(N.headers_for(api), {"User-Agent": N.USER_AGENT})
        for url in ("https://example.com/users/octocat", "http://api.github.com/users/octocat",
                    "https://api.github.com.example.net/users/octocat"):
            self.assertNotIn("Authorization", N.headers_for(url, "tok"), url)

    def test_slim_keeps_only_public_scalar_fields(self):
        N = self.N
        profile = {
            "login": "octocat", "name": "The\nOctocat", "bio": "x" * 500, "followers": 10,
            "site_admin": False, "public_repos": 8, "email": "octo@example.com",
            "plan": {"name": "pro"}, "blog": "https://github.blog", "hireable": None,
            "id": 583231, "score": 1.5, "created_at": "2011-01-25T18:44:36Z", "type": "User",
            "company": "@github", "location": "San Francisco",
        }
        slim = N.slim(profile)
        self.assertEqual(set(slim), set(("login", "name", "bio", "followers", "site_admin", "public_repos",
                                         "created_at", "type", "company", "location")))
        self.assertTrue(set(slim) <= set(N.KEEP))
        self.assertEqual(slim["name"], "The Octocat")
        self.assertEqual(len(slim["bio"]), N.TEXT_LIMIT)
        self.assertIs(slim["site_admin"], False)
        for bad in (None, [], "octocat", {}, {"login": 5}, {"login": "bad handle!"}, {"login": ""}):
            self.assertIsNone(N.slim(bad), bad)

    def test_failure_reasons_are_short_and_drawable(self):
        N = self.N
        cases = (
            (None, 404, "no such GitHub user"),
            ({"message": "Not Found"}, 0, "no such GitHub user"),
            ({"message": "API rate limit exceeded for 10.0.0.1."}, 403, "GitHub rate limit, try later"),
            ({}, 403, "GitHub rate limit, try later"),
            (None, 429, "GitHub rate limit, try later"),
            (None, 500, "GitHub said 500"),
            ({"message": "Bad credentials"}, 401, "Bad credentials"),
            ({}, 200, "no such GitHub user"),
            (None, 0, "bad reply from GitHub"),
            ("<html>", 200, "bad reply from GitHub"),
        )
        for data, code, expected in cases:
            self.assertEqual(N.reason(data, code), expected, (data, code))
        self.assertEqual(len(N.reason({"message": "x" * 100}, 422)), 40)

    def test_lookup_needs_a_handle_and_a_network(self):
        N = self.N
        lookup = N.Lookup(loader())
        for handle in ("  ", "bad handle!", None):
            self.assertEqual(lookup.start(handle, 0), ("failed", "no handle to look up"))
        self.assertEqual(lookup.start("octocat", 0), ("failed", "no network on this badge"))
        self.assertEqual(lookup.status, "no network on this badge")
        self.assertFalse(lookup.busy)
        self.assertIsNone(lookup.update(10))
        requests = FakeRequests(FakeResponse(200, {"login": "mona"}))
        lookup = N.Lookup(loader(requests=requests))
        self.assertIsNone(lookup.start("mona", 0))
        self.assertTrue(lookup.busy)
        lookup.cancel()
        self.assertFalse(lookup.busy)
        self.assertIsNone(lookup.update(10))
        self.assertEqual(requests.calls, [])

    def test_blocking_request_paints_a_frame_first(self):
        N = self.N
        response = FakeResponse(200, {"login": "octocat", "public_repos": 8, "email": "x"})
        requests = FakeRequests(response)
        secrets = types.SimpleNamespace(GITHUB_TOKEN="tok")
        lookup = N.Lookup(loader(requests=requests, wifi=FakeWifi(connected=True), secrets=secrets))
        self.assertIsNone(lookup.start("@Octocat", 0))
        self.assertEqual((lookup.state, lookup.status), (N.FETCHING, "asking GitHub..."))
        self.assertIsNone(lookup.update(10))
        self.assertEqual(requests.calls, [])
        self.assertEqual(lookup.update(20), ("profile", {"login": "octocat", "public_repos": 8}))
        url = N.API + "octocat"
        self.assertEqual(requests.calls, [(url, N.headers_for(url, "tok"), N.REQUEST_TIMEOUT)])
        self.assertTrue(response.closed)
        self.assertEqual((lookup.busy, lookup.status), (False, ""))

    def test_blocking_request_failures(self):
        N = self.N
        cases = (
            (FakeRequests(FakeResponse(404, {"message": "Not Found"})), "no such GitHub user"),
            (FakeRequests(FakeResponse(403, {"message": "API rate limit exceeded"})), "GitHub rate limit, try later"),
            (FakeRequests(FakeResponse(500, broken_json=True)), "GitHub said 500"),
            (FakeRequests(FakeResponse(200, broken_json=True)), "bad reply from GitHub"),
            (FakeRequests(FakeResponse(200, {"message": "hi"})), "hi"),
            (FakeRequests(error=OSError("ETIMEDOUT")), "lookup failed: ETIMEDOUT"),
        )
        for requests, expected in cases:
            lookup = N.Lookup(loader(requests=requests))
            self.assertIsNone(lookup.start("mona", 0))
            self.assertEqual(self.run_lookup(lookup), ("failed", expected))
            self.assertEqual(lookup.status, expected)
            self.assertFalse(lookup.busy)
            if requests.response is not None:
                self.assertTrue(requests.response.closed)

    def test_waits_for_wifi_and_gives_up(self):
        N = self.N
        wifi = FakeWifi(status=(-3, "wrong password"))
        requests = FakeRequests(FakeResponse(200, {"login": "mona"}))
        lookup = N.Lookup(loader(requests=requests, wifi=wifi))
        self.assertIsNone(lookup.start("mona", 0))
        self.assertEqual(wifi.calls, [(N.WIFI_TIMEOUT, N.WIFI_RETRIES)])
        self.assertEqual((lookup.state, lookup.status), (N.CONNECTING, "connecting to Wi-Fi..."))
        self.assertIsNone(lookup.update(100))
        self.assertEqual(lookup.status, "Wi-Fi: wrong password")
        wifi.code = (1, "joining")
        wifi.connected = True
        self.assertIsNone(lookup.update(200))
        self.assertEqual((lookup.state, lookup.status), (N.FETCHING, "asking GitHub..."))
        self.assertEqual(self.run_lookup(lookup, 300), ("profile", {"login": "mona"}))
        stuck = N.Lookup(loader(requests=requests, wifi=FakeWifi()))
        stuck.start("mona", 1000)
        self.assertIsNone(stuck.update(1000 + N.GIVE_UP_MS))
        self.assertEqual(stuck.update(1001 + N.GIVE_UP_MS), ("failed", "GitHub timed out"))
        self.assertIsNone(stuck.update(2000 + N.GIVE_UP_MS))
        broken = N.Lookup(loader(requests=requests, wifi=FakeWifi(fail_connect=True)))
        self.assertEqual(broken.start("mona", 0), ("failed", "Wi-Fi: radio off"))
        details = types.SimpleNamespace(missing=lambda key: [key])
        unset = N.Lookup(loader(requests=requests, wifi=FakeWifi(), missing_details=details))
        self.assertEqual(unset.start("mona", 0), ("failed", "add Wi-Fi in Settings"))

    def test_async_fetch_downloads_to_a_temp_file(self):
        N = self.N
        state, temp = self.temp_state()
        fetch = FakeFetch()
        secrets = types.SimpleNamespace(GITHUB_TOKEN="tok")
        lookup = N.Lookup(loader(fetch=fetch, secrets=secrets, requests=FakeRequests()))
        self.assertIsNone(lookup.start("Octocat", 1000))
        self.assertTrue(os.path.isdir(state))
        self.assertEqual(fetch.AsyncFetch.MAX_HEADER_BYTES, 8192)
        url = N.API + "octocat"
        self.assertEqual(fetch.calls, [(url, N.headers_for(url, "tok"))])
        self.assertEqual(fetch.download.path, temp)
        self.assertEqual(lookup.state, N.FETCHING)
        self.assertIsNone(lookup.update(1100))
        fetch.download.state = "Connecting"
        self.assertIsNone(lookup.update(1200))
        self.assertEqual(lookup.status, "Connecting")
        with open(temp, "w") as file:
            json.dump({"login": "octocat", "name": "The Octocat", "followers": 9, "plan": {"name": "pro"}}, file)
        fetch.download.done = True
        self.assertEqual(lookup.update(1300), ("profile", {"login": "octocat", "name": "The Octocat", "followers": 9}))
        self.assertFalse(os.path.exists(temp))
        self.assertFalse(lookup.busy)

    def test_async_fetch_failures(self):
        N = self.N
        _state, temp = self.temp_state()
        bodies = (
            ('{"message": "Not Found"}', "no such GitHub user"),
            ('{"message": "API rate limit exceeded for 10.0.0.1."}', "GitHub rate limit, try later"),
            ("<html>captive portal</html>", "bad reply from GitHub"),
            (None, "bad reply from GitHub"),
        )
        for body, expected in bodies:
            fetch = FakeFetch()
            lookup = N.Lookup(loader(fetch=fetch))
            self.assertIsNone(lookup.start("mona", 0))
            if body is not None:
                with open(temp, "w") as file:
                    file.write(body)
            fetch.download.done = True
            self.assertEqual(lookup.update(10), ("failed", expected), body)
            self.assertFalse(os.path.exists(temp))
        fetch = FakeFetch()
        lookup = N.Lookup(loader(fetch=fetch))
        lookup.start("mona", 0)
        fetch.download.error = "Connection failed"
        self.assertEqual(lookup.update(10), ("failed", "Connection failed"))
        refused = N.Lookup(loader(fetch=FakeFetch(fail=OSError("no sockets"))))
        self.assertEqual(refused.start("mona", 0), ("failed", "fetch failed: no sockets"))
        details = types.SimpleNamespace(missing=lambda key: [key])
        unset = N.Lookup(loader(fetch=FakeFetch(), missing_details=details))
        self.assertEqual(unset.start("mona", 0), ("failed", "add Wi-Fi in Settings"))


# Your Mona -------------------------------------------------------------------


class FakeBadge:
    """The runtime's badge object, as far as the app needs it to start and take presses."""

    def __init__(self):
        self.ticks = 0
        self.uid = "bad9e0051e000001"
        self.modes = []
        self.down = ()

    def mode(self, value):
        self.modes.append(value)

    def pressed(self, button):
        return button in self.down

    def held(self, button):
        return button in self.down


class LandingLookup:
    """mona_net.Lookup, except the profile lands only once the test sets landing."""

    def __init__(self, profile):
        self.profile = profile
        self.started = []
        self.busy = False
        self.landing = False
        self.status = "fetching"

    def start(self, handle, now):
        self.started.append(handle)
        self.busy = True

    def cancel(self):
        self.busy = False

    def update(self, now):
        if not (self.busy and self.landing):
            return None
        self.busy = self.landing = False
        return ("profile", self.profile)


MAIN = {}


def load_app_main():
    """Load the app's __init__.py once, with fake runtime globals in its namespace.

    The plain mona_* names, and stubs that make badgeware and missing_details
    imports fail, sit in sys.modules only while it loads.
    """
    if MAIN:
        return MAIN["module"]
    load_app_modules()
    stubs = {"badgeware": None, "missing_details": None, "secrets": types.SimpleNamespace()}
    names = list(MODULE_ORDER) + list(stubs)
    saved_modules = dict((name, sys.modules.get(name, _MISSING)) for name in names)
    saved_path = list(sys.path)
    saved_cwd = os.getcwd()
    saved_flag = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for name in MODULE_ORDER:
            sys.modules[name] = M[name]
        sys.modules.update(stubs)
        spec = importlib.util.spec_from_file_location(PREFIX + "main", str(APP_DIR / "__init__.py"))
        module = importlib.util.module_from_spec(spec)
        module.__dict__.update({
            "is_dir": lambda path: False,
            "run": lambda update: None,
            "badge": FakeBadge(),
            "screen": FakeImage(),
            "image": FakeImage,
            "font": FAKE_FONT,
            "color": FakeColor,
            "shape": FakeShapes,
            "mat3": FakeMat3,
            "vec2": fake_vec2,
            "rect": fake_rect,
            "HIRES": 1,
            "VSYNC": 2,
            "BUTTON_UP": "up",
            "BUTTON_DOWN": "down",
            "BUTTON_LEFT": "left",
            "BUTTON_RIGHT": "right",
            "BUTTON_SELECT": "select",
            "BUTTON_BACK": "back",
        })
        spec.loader.exec_module(module)
    finally:
        for name, old in saved_modules.items():
            _restore_module(name, old)
        sys.path[:] = saved_path
        os.chdir(saved_cwd)
        sys.dont_write_bytecode = saved_flag
    MAIN["module"] = module
    return module


class TestOwner(unittest.TestCase):
    """Your own Mona, as the app rebuilds it when it opens or a lookup lands."""

    PROFILE = {
        "login": "octocat", "name": "The Octocat", "bio": "I maintain open source and play guitar",
        "company": "@github", "followers": 15300, "public_repos": 8, "public_gists": 8,
        "created_at": "2011-01-25T18:44:36Z", "site_admin": False,
    }

    def setUp(self):
        self.A = load_app_main()
        self.D = M["mona_dna"]
        self.L = M["mona_link"]
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.user_file = os.path.join(folder.name, "badge_user.json")
        self.store = FakeState()
        inject(self, self.A, BADGE_USER_FILE=self.user_file, STORE=self.store, badge=FakeBadge())
        install_modules(self, {"badgeware": None, "missing_details": None})
        self.settings("octocat")

    def settings(self, handle):
        install_modules(self, {"secrets": types.SimpleNamespace(GITHUB_USERNAME=handle)})

    def badge_user(self, profile):
        with open(self.user_file, "w") as file:
            json.dump(profile, file)

    def tuned(self, profile):
        return self.D.apply_profile(self.D.dna_for("octocat"), profile)[0]

    def look_up_own_profile(self):
        """A first visit where you look up your own handle; the app saves."""
        app = self.A.MonaApp()
        found = M["mona_net"].slim(self.PROFILE)
        app.lookup = types.SimpleNamespace(update=lambda now: ("profile", found))
        app.lookup_events(0)
        return app

    def assert_owner(self, app, dna, name):
        self.assertEqual(app.owner[:3], ("octocat", dna, name))
        self.assertEqual(app.current, ("octocat", dna, name, "you"))
        self.assertEqual(app.link.card, self.L.make_card("octocat", dna, name))

    def run_app(self):
        """The app as run() drives it, minus drawing, with a lookup the test lands."""
        app = self.A.MonaApp()
        app.paint = app.draw = lambda now: None
        app.lights = lambda now, idle: None
        app.lookup = LandingLookup(M["mona_net"].slim(self.PROFILE))
        return app

    def frame(self, app, *buttons):
        self.A.badge.down = buttons
        self.A.badge.ticks += 40
        app.update()
        self.A.badge.down = ()

    def test_reopen_keeps_your_looked_up_profile_without_badge_user(self):
        first = self.look_up_own_profile()
        dna = self.tuned(self.PROFILE)
        self.assertNotEqual(dna, self.D.dna_for("octocat"))
        self.assert_owner(first, dna, "The Octocat")
        self.assertFalse(os.path.exists(self.user_file))
        again = self.A.MonaApp()
        self.assert_owner(again, dna, "The Octocat")
        self.assertEqual(again.owner[3], first.owner[3])
        self.assertTrue(again.notes)
        self.assertEqual(again.notes, first.notes)

    def test_reopen_keeps_your_saved_tweak_over_the_cached_profile(self):
        first = self.look_up_own_profile()
        first.tweak = self.D.nudge(first.current[1], self.D.EDIT[0][1], 1)
        first.save_tweak()
        mine = first.owner[1]
        self.assertNotEqual(mine, self.tuned(self.PROFILE))
        self.assert_owner(first, mine, "The Octocat")
        again = self.A.MonaApp()
        self.assert_owner(again, mine, "The Octocat")
        self.assertEqual(again.mine, ("octocat", mine))

    def test_badge_user_profile_still_comes_first_when_it_is_yours(self):
        self.look_up_own_profile()
        newer = dict(self.PROFILE, name="Mona Lisa Octocat", bio="", company="", followers=12)
        self.assertNotEqual(self.tuned(newer), self.tuned(self.PROFILE))
        self.badge_user(newer)
        self.assert_owner(self.A.MonaApp(), self.tuned(newer), "Mona Lisa Octocat")
        self.settings("")
        self.assert_owner(self.A.MonaApp(), self.tuned(newer), "Mona Lisa Octocat")

    def test_badge_user_for_someone_else_falls_back_to_your_cached_profile(self):
        self.look_up_own_profile()
        self.badge_user(dict(self.PROFILE, login="hubot", name="Hubot"))
        self.assert_owner(self.A.MonaApp(), self.tuned(self.PROFILE), "The Octocat")

    def test_no_handle_keeps_the_mystery_mona_whatever_is_cached(self):
        self.look_up_own_profile()
        self.settings("")
        app = self.A.MonaApp()
        self.assertEqual(app.owner, ("", self.D.dna_for_uid(self.A.badge.uid), "", None))

    def test_a_lookup_landing_in_tweak_closes_it_so_select_saves_nothing(self):
        app = self.run_app()
        self.frame(app, "up")
        self.frame(app, "select")
        self.frame(app, "down")
        self.assertEqual((app.view, app.lookup.started), (self.A.TWEAK, ["octocat"]))
        app.lookup.landing = True
        self.frame(app)
        dna, notes = self.D.apply_profile(self.D.dna_for("octocat"), self.PROFILE)
        self.assertEqual((app.view, app.toast), (self.A.MAIN, notes[0]))
        self.frame(app, "select")
        self.assertIsNone(app.mine)
        self.assert_owner(app, dna, "The Octocat")
        self.assertIsNone(self.store.stored[self.A.STATE_KEY]["mine"])
        again = self.A.MonaApp()
        self.assertFalse(again.has_mine())
        self.assert_owner(again, dna, "The Octocat")

    def test_a_lookup_landing_in_who_closes_it_so_you_stay_tuned(self):
        inject(self, self.A, MENU_BUTTON="menu")
        app = self.run_app()
        self.frame(app, "menu")
        self.frame(app, "down")
        self.assertEqual((app.view, app.rows[app.row][2]), (self.A.WHO, "you"))
        app.lookup.landing = True
        self.frame(app)
        self.assertEqual(app.view, self.A.MAIN)
        self.frame(app, "select")
        self.assert_owner(app, self.tuned(self.PROFILE), "The Octocat")

    def test_your_lookup_landing_leaves_a_tweak_of_another_mona_open(self):
        inject(self, self.A, MENU_BUTTON="menu")
        app = self.run_app()
        self.frame(app, "menu")
        app.adopt("hubot", self.D.dna_for("hubot"), "Hubot", "typed")
        self.frame(app, "up")
        self.frame(app, "down")
        self.frame(app, "right")
        tweak = app.tweak
        self.assertNotEqual(tweak, self.D.dna_for("hubot"))
        app.lookup.landing = True
        self.frame(app)
        self.assertEqual((app.view, app.tweak), (self.A.TWEAK, tweak))
        self.assertEqual(app.toast, "Profile saved for @octocat")
        self.frame(app, "select")
        self.assertEqual(app.current, ("hubot", tweak, "Hubot", "tweaked"))
        dna = self.tuned(self.PROFILE)
        self.assertEqual(app.owner[:3], ("octocat", dna, "The Octocat"))
        self.assertEqual(app.link.card, self.L.make_card("octocat", dna, "The Octocat"))


# App files -------------------------------------------------------------------


class TestAppFiles(unittest.TestCase):
    """The files the menu, the README check and deployment rely on."""

    def test_icon_is_a_square_png_of_at_least_24_pixels(self):
        width, height = png_size(APP_DIR / "icon.png")
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 24)

    def test_app_paces_both_reveals_with_the_frame_time(self):
        source = (APP_DIR / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("now = badge.ticks", source)
        self.assertIn("self.painter.step(budget, now)", source)
        self.assertIn("view.step(1 if self.ir.beaming else 2, now)", source)

    def test_readme_passes_the_repository_check(self):
        path = ROOT / ".github" / "scripts" / "validate_app_readmes.py"
        if not path.exists():
            self.skipTest("README validator not in this checkout")
        saved_flag = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec = importlib.util.spec_from_file_location(PREFIX + "validate_app_readmes", str(path))
            validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validator)
        finally:
            sys.dont_write_bytecode = saved_flag
        self.assertIsNone(validator.check_app(APP_DIR))

    def test_readme_documents_the_beams_and_credits(self):
        readme = (APP_DIR / "README.md").read_text(encoding="utf-8")
        for needed in ("0x4C", "0x45", "0x88", "Octocat Generator", "Level Up Lounge",
                       "Ascii-Motion", "myoctocat.com", "GITHUB_TOKEN", "badgeware.link"):
            self.assertIn(needed, readme)
        self.assertNotIn("0XF0", readme.upper())

    def test_app_folder_ships_only_app_files(self):
        for folder, allowed in (("", (".py", ".png", ".md")), ("assets", (".bin", ".png"))):
            for path in (APP_DIR / folder).iterdir():
                if path.name == "__pycache__" or path.name.startswith("."):
                    continue
                if not folder and path.name == "assets":
                    continue
                self.assertTrue(path.is_file(), path.name)
                self.assertIn(path.suffix, allowed, path.name)
        self.assertFalse((APP_DIR / "secrets.py").exists())
        token = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")
        for path in sorted(APP_DIR.glob("*.py")) + [APP_DIR / "README.md"]:
            self.assertIsNone(token.search(path.read_text(encoding="utf-8")), path.name)
