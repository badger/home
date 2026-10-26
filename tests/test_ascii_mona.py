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
import os
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "badge" / "apps" / "ascii_mona"
PREFIX = "ascii_mona_"
MODULE_ORDER = (
    "mona_parts",
    "mona_octo",
    "mona_dna",
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
        for path in files:
            parse_app(path)


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


# App files -------------------------------------------------------------------


class TestAppFiles(unittest.TestCase):
    """The files the menu, the README check and deployment rely on."""

    def test_icon_is_a_square_png_of_at_least_24_pixels(self):
        width, height = png_size(APP_DIR / "icon.png")
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 24)

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

    def test_app_folder_ships_only_app_files(self):
        allowed = (".py", ".png", ".md", ".bin")
        for path in APP_DIR.iterdir():
            if path.name == "__pycache__" or path.name.startswith("."):
                continue
            self.assertTrue(path.is_file(), path.name)
            self.assertIn(path.suffix, allowed, path.name)
        self.assertFalse((APP_DIR / "secrets.py").exists())
        token = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")
        for path in sorted(APP_DIR.glob("*.py")) + [APP_DIR / "README.md"]:
            self.assertIsNone(token.search(path.read_text(encoding="utf-8")), path.name)
