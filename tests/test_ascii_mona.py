"""Tests for the ASCII Mona badge app (badge/apps/ascii_mona).

The app's modules import each other by plain name (mona_dna, mona_octo, ...).
They are loaded here under unique ``ascii_mona_*`` names, and the plain names
only sit in sys.modules while loading, so other apps' tests in the same
process never see them. Badge runtime globals (image, shape, color, ...) are
injected into these private module objects rather than builtins, and fake
runtime modules (badgeware.ir, aye_arr.nec, ...) are removed after each test.
"""

import ast
import importlib.util
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "badge" / "apps" / "ascii_mona"
PREFIX = "ascii_mona_"
MODULE_ORDER = (
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
        allowed = (".py", ".png", ".md")
        for path in APP_DIR.iterdir():
            if path.name == "__pycache__" or path.name.startswith("."):
                continue
            self.assertTrue(path.is_file(), path.name)
            self.assertIn(path.suffix, allowed, path.name)
        self.assertFalse((APP_DIR / "secrets.py").exists())
        token = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")
        for path in sorted(APP_DIR.glob("*.py")) + [APP_DIR / "README.md"]:
            self.assertIsNone(token.search(path.read_text(encoding="utf-8")), path.name)
