from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scaffold_app = load_script("scaffold_app")
validate_app = load_script("validate_app")
deploy_app = load_script("deploy_app")
inventory_badge_apps = load_script("inventory_badge_apps")


class SkillScriptTests(unittest.TestCase):
    def test_validator_defaults_to_hardware_target(self):
        args = validate_app.parse_args(["badge/apps/demo"])
        self.assertEqual(args.target, "hardware")

    def test_inventory_lists_readable_files_and_excludes_secrets_and_compiled_files(self):
        with tempfile.TemporaryDirectory() as temp:
            mount = Path(temp)
            apps = mount / "apps" / "demo"
            apps.mkdir(parents=True)
            (apps / "__init__.py").write_text("value = 1\n", encoding="utf-8")
            (apps / "icon.png").write_bytes(b"png")
            (apps / "secrets.py").write_text("TOKEN = 'secret'\n", encoding="utf-8")
            (apps / "private.mpy").write_bytes(b"compiled")
            (apps / ".metadata").write_text("hidden", encoding="utf-8")

            inventory = inventory_badge_apps.render_inventory(mount / "apps")

            self.assertIn("`demo`", inventory)
            self.assertIn("`__init__.py`", inventory)
            self.assertIn("`icon.png`", inventory)
            self.assertNotIn("secrets.py", inventory)
            self.assertNotIn("private.mpy", inventory)
            self.assertNotIn(".metadata", inventory)

    def test_inventory_supports_system_apps_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            mount = Path(temp)
            (mount / "system" / "apps" / "demo").mkdir(parents=True)
            self.assertEqual(
                inventory_badge_apps.find_apps_dir(mount),
                mount / "system" / "apps",
            )

    def test_scaffold_creates_valid_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apps = root / "badge" / "apps"
            app_dir = scaffold_app.scaffold("demo-app", "Demo App", apps)

            self.assertTrue((app_dir / "__init__.py").is_file())
            self.assertTrue((app_dir / "assets").is_dir())
            self.assertEqual(validate_app.png_info(app_dir / "icon.png")[:2], (24, 24))
            issues = validate_app.validate_app(app_dir, root)
            self.assertFalse([issue for issue in issues if issue.severity == "ERROR"])
            source = (app_dir / "__init__.py").read_text(encoding="utf-8")
            self.assertIn('APP_DIR = "/system/apps/demo-app"', source)
            self.assertIn("badge.pressed(BUTTON_SELECT)", source)
            self.assertIn("run(update)", source)
            self.assertNotIn("PixelFont", source)
            self.assertNotIn("from badgeware import", source)
            self.assertNotIn('if __name__ == "__main__"', source)
            self.assertFalse([issue for issue in issues if "README" in issue.message])

    def test_scaffold_readme_passes_repository_readme_check(self):
        checker = SCRIPT_DIR.parents[3] / ".github" / "scripts" / "validate_app_readmes.py"
        if not checker.is_file():
            self.skipTest("Repository README checker is not available")
        spec = importlib.util.spec_from_file_location("validate_app_readmes", checker)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp)
            default = scaffold_app.scaffold("demo", "Demo", apps)
            custom = scaffold_app.scaffold(
                "other", "Other", apps, "Other counts how often you wave the badge."
            )
            self.assertIsNone(module.check_app(default))
            self.assertIsNone(module.check_app(custom))
            self.assertIn("wave the badge", (custom / "README.md").read_text())

    def test_validator_warns_when_readme_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
            (app_dir / "README.md").unlink()
            issues = validate_app.validate_app(app_dir, root)
            self.assertTrue(
                any(i.severity == "WARNING" and "README.md" in i.message for i in issues)
            )

    def test_validator_accepts_larger_square_icons(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
            issues = validate_app.validate_app(app_dir, root)
            self.assertFalse([i for i in issues if "icon.png" in i.message])

    def test_scaffold_rejects_digit_leading_names(self):
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp)
            with self.assertRaises(ValueError):
                scaffold_app.scaffold(
                    "30_minutes_to_alpha_centauri", "Alpha Centauri", apps
                )
            self.assertFalse(any(apps.iterdir()))

    def test_deploy_accepts_existing_digit_leading_app_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "30_minutes_to_alpha_centauri"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "def update():\n    pass\n\nrun(update)\n", encoding="utf-8"
            )
            issues = validate_app.validate_app(app_dir, root)
            self.assertFalse([issue for issue in issues if issue.severity == "ERROR"])
            mount = root / "BADGER"
            destination = mount / "apps" / app_dir.name
            destination.mkdir(parents=True)
            (destination / "old.txt").write_text("old", encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                deployed = deploy_app.deploy(app_dir, mount, True, True, root)

            self.assertEqual(deployed, destination)
            self.assertEqual(
                (destination / "__init__.py").read_bytes(),
                (app_dir / "__init__.py").read_bytes(),
            )
            self.assertFalse((destination / "old.txt").exists())
            self.assertEqual(
                len(list((mount / ".badge-app-backups").glob(f"{app_dir.name}-*"))),
                1,
            )

    def test_scaffold_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp)
            scaffold_app.scaffold("demo", "Demo", apps)
            with self.assertRaises(FileExistsError):
                scaffold_app.scaffold("demo", "Demo", apps)

    def test_scaffold_escapes_title(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold(
                "quoted", 'Mona\'s "Badge"', root / "badge" / "apps"
            )
            issues = validate_app.validate_app(app_dir, root)
            self.assertFalse([issue for issue in issues if issue.severity == "ERROR"])

    def test_validator_requires_update(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "broken"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text("value = 1\n", encoding="utf-8")
            issues = validate_app.validate_app(app_dir, root)
            self.assertTrue(
                any(
                    issue.severity == "ERROR" and "update()" in issue.message
                    for issue in issues
                )
            )

    def test_validator_requires_module_level_run_for_u26_apps(self):
        samples = {
            "missing-run": "def update():\n    pass\n",
            "guarded-run": (
                "def update():\n"
                "    pass\n"
                "if __name__ == \"__main__\":\n"
                "    run(update)\n"
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in samples.items():
                with self.subTest(app=name):
                    app_dir = root / "badge" / "apps" / name
                    app_dir.mkdir(parents=True)
                    (app_dir / "__init__.py").write_text(source, encoding="utf-8")
                    issues = validate_app.validate_app(app_dir, root)
                    self.assertTrue(
                        any(
                            issue.severity == "ERROR"
                            and "must call run(update) at module level" in issue.message
                            for issue in issues
                        )
                    )

    def test_validator_ignores_class_methods_as_module_callbacks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "class-callback"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "class App:\n"
                "    @staticmethod\n"
                "    def update():\n"
                "        pass\n",
                encoding="utf-8",
            )
            issues = validate_app.validate_app(app_dir, root)
            self.assertTrue(
                any(
                    issue.severity == "ERROR"
                    and "Required update binding is missing" in issue.message
                    for issue in issues
                )
            )

    def test_validator_rejects_relative_asset_outside_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "outside-asset"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                'picture = image.load("../shared.png")\n'
                "def update():\n"
                "    pass\n",
                encoding="utf-8",
            )
            (app_dir.parent / "shared.png").write_bytes(b"host file")
            issues = validate_app.validate_app(app_dir, root)
            self.assertTrue(
                any(
                    issue.severity == "ERROR"
                    and "resolves outside the app directory" in issue.message
                    for issue in issues
                )
            )

    def test_validator_accepts_legacy_imported_update(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "modular"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "from badgeware import io, run\n"
                "from game import update\n"
                "if __name__ == \"__main__\":\n"
                "    run(update)\n",
                encoding="utf-8",
            )
            (app_dir / "game.py").write_text(
                "def update():\n    pass\n", encoding="utf-8"
            )
            issues = validate_app.validate_app(app_dir, root)
            self.assertFalse(
                any(
                    issue.severity == "ERROR"
                    and (
                        "update binding" in issue.message
                        or "must call run(update)" in issue.message
                    )
                    for issue in issues
                )
            )

    def test_validator_rejects_required_lifecycle_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "arguments"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "def init(required):\n"
                "    pass\n"
                "def update(required, optional=1):\n"
                "    pass\n",
                encoding="utf-8",
            )
            issues = validate_app.validate_app(app_dir, root)
            lifecycle_errors = [
                issue
                for issue in issues
                if issue.severity == "ERROR" and "callable with no arguments" in issue.message
            ]
            self.assertEqual(len(lifecycle_errors), 2)

    def test_png_validation_rejects_header_only_file(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "broken.png"
            png.write_bytes(
                validate_app.PNG_SIGNATURE
                + b"\x00\x00\x00\rIHDR"
                + b"\x00\x00\x00\x18\x00\x00\x00\x18\x08\x02\x00\x00\x00"
            )
            with self.assertRaises(ValueError):
                validate_app.png_info(png)

    def test_png_validation_rejects_invalid_compressed_data(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "broken.png"
            ihdr = b"\x00\x00\x00\x18\x00\x00\x00\x18\x08\x02\x00\x00\x00"
            png.write_bytes(
                validate_app.PNG_SIGNATURE
                + scaffold_app.png_chunk(b"IHDR", ihdr)
                + scaffold_app.png_chunk(b"IDAT", b"not-zlib-data")
                + scaffold_app.png_chunk(b"IEND", b"")
            )
            with self.assertRaises(ValueError):
                validate_app.png_info(png)

    def test_png_validation_limits_decompressed_scanline_data(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "oversized.png"
            ihdr = b"\x00\x00\x00\x08\x00\x00\x00\x08\x08\x06\x00\x00\x01"
            compressed = zlib.compress(b"\x00" + bytes(1024 * 1024))
            png.write_bytes(
                validate_app.PNG_SIGNATURE
                + scaffold_app.png_chunk(b"IHDR", ihdr)
                + scaffold_app.png_chunk(b"IDAT", compressed)
                + scaffold_app.png_chunk(b"IEND", b"")
            )
            with self.assertRaisesRegex(ValueError, "exceeds expected dimensions"):
                validate_app.png_info(png)

    def test_png_validation_requires_palette_for_indexed_images(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "indexed.png"
            ihdr = b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x03\x00\x00\x00"
            png.write_bytes(
                validate_app.PNG_SIGNATURE
                + scaffold_app.png_chunk(b"IHDR", ihdr)
                + scaffold_app.png_chunk(b"IDAT", b"x\x9cc`\x00\x00\x00\x02\x00\x01")
                + scaffold_app.png_chunk(b"IEND", b"")
            )
            with self.assertRaisesRegex(ValueError, "requires PLTE"):
                validate_app.png_info(png)

    def test_validator_rejects_async_and_non_callable_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "invalid-callbacks"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "async def update():\n"
                "    pass\n"
                "init = 1\n",
                encoding="utf-8",
            )
            issues = validate_app.validate_app(app_dir, root)
            messages = [issue.message for issue in issues if issue.severity == "ERROR"]
            self.assertTrue(any("synchronous" in message for message in messages))
            self.assertTrue(any("non-callable" in message for message in messages))

    def test_validator_warns_on_physical_display_coordinates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "oversized"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "from badgeware import shapes\n"
                "SCREEN_WIDTH = 320\n"
                "def update():\n"
                "    return shapes.rectangle(0, 0, 320, 240)\n",
                encoding="utf-8",
            )
            issues = validate_app.validate_app(app_dir, root)
            self.assertTrue(
                any("logical" in issue.message for issue in issues)
            )

    def test_validator_emits_one_bluetooth_warning_for_emulator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "bluetooth-app"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "import bluetooth\n"
                "def update():\n"
                "    pass\n",
                encoding="utf-8",
            )
            issues = validate_app.validate_app(app_dir, root, "emulator")
            bluetooth_warnings = [
                issue.message
                for issue in issues
                if issue.severity == "WARNING"
                and ("bluetooth" in issue.message or "BLE behavior" in issue.message)
            ]
            self.assertEqual(
                bluetooth_warnings,
                [
                    "BLE behavior requires real peers; verify the chosen "
                    "emulator's bluetooth support and test on physical badges."
                ],
            )

    def test_deploy_is_dry_run_by_default_and_icon_is_optional(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold(
                "demo", "Demo", root / "badge" / "apps"
            )
            (app_dir / "icon.png").unlink()
            mount = root / "BADGER"
            (mount / "system" / "apps").mkdir(parents=True)

            output = io.StringIO()
            with redirect_stdout(output):
                destination = deploy_app.deploy(app_dir, mount, False, False, root)

            self.assertFalse(destination.exists())
            self.assertIn("No icon.png", output.getvalue())
            self.assertNotIn("ERROR", output.getvalue())

    def test_deploy_ignores_hidden_and_cached_python_and_png_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold(
                "demo", "Demo", root / "badge" / "apps"
            )
            excluded = [
                "._helper.py",
                "._picture.png",
                "assets/._helper.py",
                "assets/._picture.png",
                ".hidden/helper.py",
                ".hidden/picture.png",
                "assets/.hidden/helper.py",
                "assets/.hidden/picture.png",
                "__pycache__/helper.py",
                "__pycache__/picture.png",
                "assets/__pycache__/helper.py",
                "assets/__pycache__/picture.png",
            ]
            for relative in excluded:
                path = app_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\x00not valid Python or PNG")

            issues = validate_app.validate_app(app_dir, root)
            self.assertFalse([issue for issue in issues if issue.severity == "ERROR"])
            mount = root / "BADGER"
            (mount / "apps").mkdir(parents=True)
            with redirect_stdout(io.StringIO()):
                destination = deploy_app.deploy(app_dir, mount, True, False, root)

            self.assertEqual(
                sorted(
                    path.relative_to(destination).as_posix()
                    for path in destination.rglob("*")
                    if path.is_file()
                ),
                ["README.md", "__init__.py", "icon.png"],
            )

    def test_validator_still_checks_visible_python_and_png_files(self):
        for relative in ("assets/helper.py", "assets/picture.png"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                app_dir = scaffold_app.scaffold(
                    "demo", "Demo", root / "badge" / "apps"
                )
                path = app_dir / relative
                path.write_bytes(b"\x00not valid Python or PNG")

                issues = validate_app.validate_app(app_dir, root)

                self.assertTrue(
                    any(
                        issue.severity == "ERROR" and issue.path == path
                        for issue in issues
                    )
                )

    def test_deploy_rejects_secrets_hidden_files_and_bytecode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold(
                "demo", "Demo", root / "badge" / "apps"
            )
            (app_dir / "secrets.py").write_text("TOKEN = 'nope'\n", encoding="utf-8")
            (app_dir / ".hidden").write_text("hidden", encoding="utf-8")
            (app_dir / "cache.pyc").write_bytes(b"bytecode")
            mount = root / "BADGER"
            (mount / "system" / "apps").mkdir(parents=True)

            with self.assertRaises(RuntimeError):
                deploy_app.deploy(app_dir, mount, True, False, root)

    def test_validator_rejects_non_png_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "linked"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "def update():\n    pass\n", encoding="utf-8"
            )
            outside = root / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            try:
                (app_dir / "data.json").symlink_to(outside)
            except OSError as error:
                if sys.platform == "win32" and getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows needs Developer Mode or symlink permission")
                raise
            issues = validate_app.validate_app(app_dir, root)
            self.assertTrue(
                any(issue.severity == "ERROR" and "Symlinks" in issue.message for issue in issues)
            )

    def test_deploy_writes_and_backs_up_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold(
                "demo", "Demo", root / "badge" / "apps"
            )
            mount = root / "BADGER"
            apps_dir = mount / "system" / "apps"
            existing = apps_dir / "demo"
            existing.mkdir(parents=True)
            (existing / "old.txt").write_text("old", encoding="utf-8")

            destination = deploy_app.deploy(app_dir, mount, True, True, root)

            self.assertTrue((destination / "__init__.py").is_file())
            backups = list((mount / ".badge-app-backups").glob("demo-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "old.txt").read_text(encoding="utf-8"), "old")

    def test_deploy_supports_current_badger_apps_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = scaffold_app.scaffold(
                "demo", "Demo", root / "badge" / "apps"
            )
            mount = root / "BADGER"
            (mount / "apps").mkdir(parents=True)

            destination = deploy_app.deploy(app_dir, mount, True, False, root)

            self.assertTrue((destination / "__init__.py").is_file())

    def test_deploy_refuses_reserved_system_apps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "badge" / "apps" / "menu"
            app_dir.mkdir(parents=True)
            (app_dir / "__init__.py").write_text(
                "def update():\n    pass\n", encoding="utf-8"
            )
            mount = root / "BADGER"
            (mount / "system" / "apps").mkdir(parents=True)
            with self.assertRaises(RuntimeError):
                deploy_app.deploy(app_dir, mount, True, True, root)


if __name__ == "__main__":
    unittest.main()
