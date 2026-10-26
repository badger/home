from __future__ import annotations

import io
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import deploy_app
import install_skill
import inventory_badge_apps
import scaffold_app
import skill_paths
import validate_app


class WorkflowTests(unittest.TestCase):
    def run_tool(self, package, script, cwd, *arguments, success=True):
        result = subprocess.run(
            [sys.executable, str(package / "scripts" / script), *map(str, arguments)],
            cwd=cwd,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_personal_install_uses_plain_project_with_spaces(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "Badge Projects"
            project.mkdir()
            installed = install_skill.install(PACKAGE, root / "User Home")
            result = self.run_tool(
                installed, "scaffold_app.py", project, "demo", "--title", "My Counter"
            )
            app = project / "badge" / "apps" / "demo"
            self.assertTrue((app / "__init__.py").is_file())
            self.assertFalse((installed / "badge").exists())
            self.assertIn("menu-icons.md", result.stdout)
            command = next(
                line.removeprefix("Validate: ")
                for line in result.stdout.splitlines() if line.startswith("Validate: ")
            )
            if os.name != "nt":
                result = subprocess.run(
                    shlex.split(command), cwd=project, capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.run_tool(installed, "validate_app.py", project, "demo")

    def test_repository_install_preserves_project_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "Repository With Spaces"
            installed = project / ".github" / "skills" / "hyb26-skill"
            shutil.copytree(PACKAGE, installed, ignore=shutil.ignore_patterns("__pycache__"))
            elsewhere = root / "Other Folder"
            elsewhere.mkdir()
            self.run_tool(installed, "scaffold_app.py", elsewhere, "demo")
            self.run_tool(installed, "validate_app.py", elsewhere, "demo")
            self.assertTrue((project / "badge" / "apps" / "demo").is_dir())
            self.assertFalse((elsewhere / "badge").exists())

    def test_explicit_project_resolves_shared_system_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "Chosen Project"
            apps = project / "badge" / "apps"
            self.run_tool(PACKAGE, "scaffold_app.py", root, "demo", "--apps-dir", apps)
            assets = project / "badge" / "assets"
            assets.mkdir()
            scaffold_app.make_icon(assets / "shared.png")
            entry = apps / "demo" / "__init__.py"
            entry.write_text(
                'picture = image.load("/system/assets/shared.png")\n'
                + entry.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.run_tool(
                PACKAGE, "validate_app.py", root, "demo", "--repo-root", project
            )
            self.assertFalse((root / "badge").exists())

    def test_skill_and_home_folders_are_not_implicit_projects(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "User Home"
            installed = install_skill.install(PACKAGE, home)
            result = self.run_tool(
                installed, "scaffold_app.py", installed, "do-not-create", success=False
            )
            self.assertIn("Open your badge project folder", result.stderr)
            with (
                patch.object(skill_paths, "SCRIPT_DIR", installed / "scripts"),
                patch.object(skill_paths.Path, "cwd", return_value=home),
                patch.object(skill_paths.Path, "home", return_value=home),
            ):
                with self.assertRaisesRegex(ValueError, "home folder"):
                    skill_paths.project_root()

    def test_powershell_next_command_quotes_literal_paths(self):
        app = Path("Badge Projects") / "Mona's app"
        with patch.object(skill_paths, "os", SimpleNamespace(name="nt")):
            command = skill_paths.validation_command(app)
        self.assertTrue(command.startswith("& '"))
        self.assertIn("Mona''s app", command)
        self.assertIn("validate_app.py'", command)

    def test_install_update_keeps_local_files_and_excludes_generated_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Skill Source"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: hyb26-skill\n---\nFirst version\n", encoding="utf-8"
            )
            (source / ".DS_Store").write_bytes(b"metadata")
            cache = source / "__pycache__"
            cache.mkdir()
            (cache / "module.pyc").write_bytes(b"cache")
            (source / "._SKILL.md").write_bytes(b"metadata")
            destination = install_skill.install(source, root / "User Home")
            (destination / "local.txt").write_text("keep", encoding="utf-8")
            (source / "SKILL.md").write_text(
                "---\nname: hyb26-skill\n---\nUpdated version\n", encoding="utf-8"
            )
            install_skill.install(source, root / "User Home")
            self.assertIn("Updated version", (destination / "SKILL.md").read_text())
            self.assertEqual((destination / "local.txt").read_text(), "keep")
            self.assertFalse((destination / ".DS_Store").exists())
            self.assertFalse((destination / "._SKILL.md").exists())
            self.assertFalse((destination / "__pycache__").exists())
            self.assertEqual(install_skill.install(destination, root / "User Home"), destination)

    def test_installer_rejects_name_outside_frontmatter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# Example\nname: hyb26-skill\n")
            with self.assertRaisesRegex(ValueError, "No valid skill name"):
                install_skill.install(source, root / "home")
            self.assertFalse((root / "home").exists())

    def test_invalid_preview_still_fails_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
            (app / "icon.png").write_bytes(b"not a PNG")
            issues = validate_app.validate_app(app, root)
            self.assertTrue(any(
                issue.severity == "ERROR" and "Invalid icon.png" in issue.message
                for issue in issues
            ))

    def test_observed_event_helpers_do_not_get_legacy_warnings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
            entry = app / "__init__.py"
            entry.write_text(
                "from badgeware import link, get_backlight, set_backlight\n"
                + entry.read_text(encoding="utf-8"), encoding="utf-8"
            )
            self.assertEqual(validate_app.validate_app(app, root), [])

    def test_inventory_and_deployment_reject_ambiguous_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
            mount = root / "BADGER"
            (mount / "apps").mkdir(parents=True)
            (mount / "system" / "apps").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "Multiple badge app directories"):
                inventory_badge_apps.find_apps_dir(mount)
            with self.assertRaisesRegex(RuntimeError, "Multiple badge app directories"):
                deploy_app.deploy(app, mount, True, False, root)
            self.assertFalse((mount / "apps" / "demo").exists())
            self.assertFalse((mount / "system" / "apps" / "demo").exists())
            self.assertEqual(
                inventory_badge_apps.find_apps_dir(mount / "system"),
                mount / "system" / "apps",
            )

    def test_copy_preview_and_replacement_for_each_usb_layout(self):
        for layout in ("apps", "system/apps"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                app = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
                (app / ".metadata").write_text("do not copy")
                (app / "cache.pyc").write_bytes(b"do not copy")
                mount = root / "BADGER"
                apps = mount / layout
                apps.mkdir(parents=True)
                self.run_tool(
                    PACKAGE, "deploy_app.py", root, "demo", "--mount", mount,
                    "--repo-root", root
                )
                self.assertEqual(list(mount.iterdir()), [mount / layout.split("/")[0]])
                self.run_tool(
                    PACKAGE, "deploy_app.py", root, "demo", "--mount", mount,
                    "--repo-root", root, "--write"
                )
                self.assertEqual(
                    (apps / "demo" / "__init__.py").read_bytes(),
                    (app / "__init__.py").read_bytes(),
                )
                self.assertFalse((apps / "demo" / ".metadata").exists())
                self.assertFalse((apps / "demo" / "cache.pyc").exists())
                self.run_tool(
                    PACKAGE, "inventory_badge_apps.py", root, "--mount", mount
                )
                refusal = self.run_tool(
                    PACKAGE, "deploy_app.py", root, "demo", "--mount", mount,
                    "--repo-root", root, "--write", success=False
                )
                self.assertIn("--replace", refusal.stderr)
                self.run_tool(
                    PACKAGE, "deploy_app.py", root, "demo", "--mount", mount,
                    "--repo-root", root, "--write", "--replace"
                )
                backups = list((mount / ".badge-app-backups").glob("demo-*"))
                self.assertEqual(len(backups), 1)
                self.assertTrue((backups[0] / "__init__.py").is_file())

    def test_failed_staging_keeps_existing_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = scaffold_app.scaffold("demo", "Demo", root / "badge" / "apps")
            mount = root / "BADGER"
            old = mount / "apps" / "demo"
            old.mkdir(parents=True)
            (old / "original.txt").write_text("keep")
            with patch.object(deploy_app, "copy_app", side_effect=OSError("copy failed")):
                with redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(OSError, "copy failed"):
                        deploy_app.deploy(app, mount, True, True, root)
            self.assertEqual((old / "original.txt").read_text(), "keep")
            self.assertFalse((mount / ".badge-app-staging").exists())


if __name__ == "__main__":
    unittest.main()
