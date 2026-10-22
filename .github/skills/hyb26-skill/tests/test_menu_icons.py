from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import patch_menu_icons  # noqa: E402

REPOSITORY_MENU = SCRIPT_DIR.parents[3] / "badge" / "apps" / "menu" / "app.py"

UNPATCHED_MENU = '''ICON_SIZE = 48
ICON_SHIFT = 3
TILE_FILTER = image.BILINEAR


def load_animation(slug):
    return None


class App(Tile):
    def __init__(self, ordinal, name, slug, path, animated):
        self.icon_key = slug if slug in ICONS else "default"
        self.icon = build_icon(ICONS[self.icon_key])
        self.animation = None

    def draw(self, selected):
        if selected:
            pass

        icon = self.current_icon(selected)
        screen.shape(icon)
'''


def unpatch(text: str) -> str:
    text = text.replace('ICON_FILE = "icon.png"\n', "")
    text = text.replace(patch_menu_icons.LOAD_PICTURE, "")
    text = text.replace(
        "        self.picture = None if slug in ICONS else load_picture(path)\n", ""
    )
    block = "".join(
        f"        {row}\n" if row else "\n"
        for row in patch_menu_icons.BLIT_PICTURE.rstrip("\n").split("\n")
    ) + "\n"
    return text.replace(block, "")


class MenuIconPatchTests(unittest.TestCase):
    def test_patch_adds_icon_loading_and_is_idempotent(self):
        patched = patch_menu_icons.patch_text(UNPATCHED_MENU)
        self.assertTrue(patch_menu_icons.is_patched(patched))
        self.assertIn('ICON_FILE = "icon.png"\nTILE_FILTER', patched)
        self.assertIn(
            "        self.picture = None if slug in ICONS else load_picture(path)\n",
            patched,
        )
        self.assertIn("            return\n\n        icon = self.current_icon", patched)
        self.assertEqual(patch_menu_icons.patch_text(patched), patched)
        compile(patched, "app.py", "exec")

    def test_patch_preserves_crlf(self):
        patched = patch_menu_icons.patch_text(UNPATCHED_MENU.replace("\n", "\r\n"))
        self.assertNotIn("\n", patched.replace("\r\n", ""))

    def test_patch_matches_repository_menu(self):
        if not REPOSITORY_MENU.is_file():
            self.skipTest("badger/home menu source is not available")
        patched = REPOSITORY_MENU.read_text(encoding="utf-8")
        self.assertTrue(patch_menu_icons.is_patched(patched))
        original = unpatch(patched)
        self.assertFalse(patch_menu_icons.is_patched(original))
        self.assertEqual(patch_menu_icons.patch_text(original), patched)

    def test_patch_refuses_unknown_menu(self):
        for text in (
            "print('hello')\n",
            UNPATCHED_MENU.replace("ICON_SHIFT = 3\n", ""),
            UNPATCHED_MENU.replace(", path,", ","),
            UNPATCHED_MENU + 'ICON_FILE = "icon.png"\n',
        ):
            with self.subTest(text=text[:40]):
                with self.assertRaises(patch_menu_icons.PatchError):
                    patch_menu_icons.patch_text(text)

    def test_mount_dry_run_then_write_with_backup(self):
        for layout in (("apps",), ("system", "apps")):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as temp:
                mount = Path(temp) / "BADGER"
                menu = mount.joinpath(*layout, "menu", "app.py")
                menu.parent.mkdir(parents=True)
                menu.write_text(UNPATCHED_MENU, encoding="utf-8")

                with redirect_stdout(io.StringIO()):
                    self.assertEqual(patch_menu_icons.main(["--mount", str(mount)]), 0)
                self.assertEqual(menu.read_text(encoding="utf-8"), UNPATCHED_MENU)

                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        patch_menu_icons.main(["--mount", str(mount), "--write"]), 0
                    )
                self.assertTrue(patch_menu_icons.is_patched(menu.read_text(encoding="utf-8")))
                backups = list((mount / ".badge-app-backups").glob("menu-app.py-*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(encoding="utf-8"), UNPATCHED_MENU)
                self.assertEqual(sorted(p.name for p in menu.parent.iterdir()), ["app.py"])

    def test_missing_source_menu_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            mount = Path(temp)
            (mount / "apps" / "menu").mkdir(parents=True)
            (mount / "apps" / "menu" / "app.mpy").write_bytes(b"compiled")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(patch_menu_icons.main(["--mount", str(mount)]), 1)


if __name__ == "__main__":
    unittest.main()
