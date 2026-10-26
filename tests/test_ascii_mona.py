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
