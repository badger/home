#!/usr/bin/env python3
"""Run static checks on badge app structure, assets, and target-specific risks."""

from __future__ import annotations

import argparse
import ast
import re
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

from skill_paths import project_root

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_SCANLINE_BYTES = 32 * 1024 * 1024
APP_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
RESERVED_APPS = {"menu", "startup"}

BADGEWARE_NAMES = {
    "State",
    "link",
    "get_backlight",
    "set_backlight",
}

LEGACY_BADGEWARE_NAMES = {
    "Image",
    "Matrix",
    "PixelFont",
    "SpriteSheet",
    "brushes",
    "clamp",
    "display",
    "file_exists",
    "get_battery_level",
    "io",
    "is_charging",
    "is_dir",
    "run",
    "screen",
    "shapes",
}

HARDWARE_ONLY_MODULES = {
    "aioble",
    "bluetooth",
    "board",
    "machine",
    "micropython",
    "ntptime",
    "pimoroni",
    "pimoroni_i2c",
    "powman",
    "rp2",
    "st7789",
}

DESKTOP_ONLY_MODULES = {
    "cv2",
    "numpy",
    "pandas",
    "pathlib",
    "PIL",
    "pygame",
    "requests_html",
    "scipy",
    "subprocess",
    "tkinter",
}

SIMULATOR_MOCKS = {"badgeware", "network", "urequest", "urllib", "urandom", "aye_arr"}
LOAD_CALLS = {
    ("image", "load"),
}
LIFECYCLE_NAMES = ("update", "init", "on_exit")


@dataclass(order=True)
class Issue:
    severity: str
    message: str
    path: Path | None = None
    line: int | None = None

    def render(self, base: Path) -> str:
        location = ""
        if self.path is not None:
            try:
                display_path = self.path.relative_to(base)
            except ValueError:
                display_path = self.path
            location = str(display_path)
            if self.line is not None:
                location += f":{self.line}"
            location += ": "
        return f"{self.severity}: {location}{self.message}"


def png_info(path: Path) -> tuple[int, int, int, int]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")

    offset = len(PNG_SIGNATURE)
    info = None
    interlace = None
    idat_data = bytearray()
    saw_idat = False
    saw_iend = False
    palette_entries = None
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise ValueError("truncated PNG chunk data")
        chunk_data = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValueError(f"invalid {chunk_type.decode(errors='replace')} CRC")

        if info is None:
            if chunk_type != b"IHDR" or length != 13:
                raise ValueError("PNG must begin with a 13-byte IHDR")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
            if width < 1 or height < 1:
                raise ValueError("PNG width and height must be positive")
            if compression != 0 or filter_method != 0 or interlace not in {0, 1}:
                raise ValueError("unsupported PNG compression, filter, or interlace method")
            info = (width, height, bit_depth, color_type)
        elif chunk_type == b"IHDR":
            raise ValueError("duplicate PNG IHDR")

        if chunk_type == b"PLTE":
            if palette_entries is not None:
                raise ValueError("duplicate PNG PLTE")
            if saw_idat:
                raise ValueError("PNG PLTE must appear before IDAT")
            if length < 3 or length > 768 or length % 3 != 0:
                raise ValueError("invalid PNG PLTE length")
            palette_entries = length // 3
        if chunk_type == b"IDAT":
            if info[3] == 3:
                if palette_entries is None:
                    raise ValueError("indexed PNG requires PLTE before IDAT")
                if palette_entries > 2 ** info[2]:
                    raise ValueError("PNG palette has too many entries for bit depth")
            saw_idat = True
            idat_data.extend(chunk_data)
        if chunk_type == b"IEND":
            if length != 0:
                raise ValueError("invalid PNG IEND")
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end

    if info is None or not saw_idat or not saw_iend:
        raise ValueError("PNG requires IHDR, IDAT, and IEND chunks")
    if offset != len(data):
        raise ValueError("unexpected data after PNG IEND")
    scanline_layout = png_scanline_layout(*info, interlace or 0)
    expected_size = sum(
        row_count * (row_bytes + 1) for row_count, row_bytes in scanline_layout
    )
    if expected_size > MAX_PNG_SCANLINE_BYTES:
        raise ValueError(
            f"PNG decompressed image data exceeds the "
            f"{MAX_PNG_SCANLINE_BYTES // (1024 * 1024)} MiB limit"
        )
    try:
        decompressor = zlib.decompressobj()
        scanlines = decompressor.decompress(bytes(idat_data), expected_size + 1)
    except zlib.error as error:
        raise ValueError(f"invalid PNG image data: {error}") from error
    if len(scanlines) > expected_size:
        raise ValueError("PNG decompressed scanline data exceeds expected dimensions")
    if not decompressor.eof:
        raise ValueError("incomplete or oversized PNG image data")
    validate_scanlines(scanlines, *info, interlace or 0)
    return info


def png_scanline_layout(
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> list[tuple[int, int]]:
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    valid_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if channels is None or bit_depth not in valid_depths[color_type]:
        raise ValueError("invalid PNG color type or bit depth")

    passes = [(0, 0, 1, 1)]
    if interlace == 1:
        passes = [
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        ]

    layout = []
    for x_start, y_start, x_step, y_step in passes:
        pass_width = (
            0 if width <= x_start else (width - x_start + x_step - 1) // x_step
        )
        pass_height = (
            0 if height <= y_start else (height - y_start + y_step - 1) // y_step
        )
        if pass_width == 0 or pass_height == 0:
            continue
        row_bytes = (pass_width * channels * bit_depth + 7) // 8
        layout.append((pass_height, row_bytes))
    return layout


def validate_scanlines(
    data: bytes,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> None:
    offset = 0
    for pass_height, row_bytes in png_scanline_layout(
        width, height, bit_depth, color_type, interlace
    ):
        for _ in range(pass_height):
            if offset >= len(data):
                raise ValueError("truncated PNG scanlines")
            if data[offset] > 4:
                raise ValueError("invalid PNG scanline filter")
            offset += 1 + row_bytes
            if offset > len(data):
                raise ValueError("truncated PNG scanline")
    if offset != len(data):
        raise ValueError("unexpected PNG scanline data")


def resolve_app(value: str, repo_root: Path) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()
    project_relative = repo_root / candidate
    if project_relative.exists():
        return project_relative.resolve()
    named = repo_root / "badge" / "apps" / value
    return named.resolve()


def module_root(name: str) -> str:
    return name.split(".", 1)[0]


def local_modules(app_dir: Path) -> set[str]:
    modules = {path.stem for path in app_dir.glob("*.py")}
    modules.update(path.name for path in app_dir.iterdir() if path.is_dir())
    return modules


class AppVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: set[str] = set()
        self.function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.bindings: set[str] = set()
        self.binding_kinds: dict[str, str] = {}
        self.imports: list[tuple[str, int]] = []
        self.badgeware_names: list[tuple[str, int]] = []
        self.uses_legacy_badgeware_api = False
        self.asset_paths: list[tuple[str, int]] = []
        self.resolution_warnings: list[tuple[str, int]] = []
        self.module_run_update_lines: list[int] = []
        self._depth = 0

    def visit_Module(self, node: ast.Module) -> None:
        for statement in node.body:
            if isinstance(statement, (ast.Expr, ast.Assign, ast.AnnAssign)):
                value = statement.value
                while isinstance(value, ast.Attribute):
                    value = value.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "run"
                    and value.args
                    and isinstance(value.args[0], ast.Name)
                    and value.args[0].id == "update"
                ):
                    self.module_run_update_lines.append(value.lineno)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._depth == 0:
            self.functions.add(node.name)
            self.function_nodes[node.name] = node
            self.bindings.add(node.name)
            self.binding_kinds[node.name] = "function"
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._depth == 0 and isinstance(node.target, ast.Name):
            self.bindings.add(node.target.id)
            if isinstance(node.value, ast.Lambda):
                kind = "function"
            elif isinstance(node.value, (ast.Name, ast.Attribute)):
                kind = "alias"
            elif isinstance(
                node.value,
                (
                    ast.Constant,
                    ast.Dict,
                    ast.List,
                    ast.Set,
                    ast.Tuple,
                ),
            ):
                kind = "non-callable"
            else:
                kind = "unknown"
            self.binding_kinds[node.target.id] = kind
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self._depth == 0:
            self.functions.add(node.name)
            self.function_nodes[node.name] = node
            self.bindings.add(node.name)
            self.binding_kinds[node.name] = "async-function"
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
            if self._depth == 0:
                binding = alias.asname or module_root(alias.name)
                self.bindings.add(binding)
                self.binding_kinds[binding] = "module"

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        self.imports.append((module, node.lineno))
        if self._depth == 0:
            for alias in node.names:
                binding = alias.asname or alias.name
                self.bindings.add(binding)
                self.binding_kinds[binding] = "imported"
        if module == "badgeware":
            self.badgeware_names.extend((alias.name, node.lineno) for alias in node.names)
            if any(
                alias.name == "*"
                or alias.name in LEGACY_BADGEWARE_NAMES
                for alias in node.names
            ):
                self.uses_legacy_badgeware_api = True

    def visit_Call(self, node: ast.Call) -> None:
        owner = None
        method = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            owner = node.func.value.id
            method = node.func.attr
        elif isinstance(node.func, ast.Name):
            owner = node.func.id

        if (owner, method) in LOAD_CALLS and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                self.asset_paths.append((argument.value, node.lineno))

        if (
            owner == "shapes"
            and method == "rectangle"
            and len(node.args) >= 4
            and all(
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, (int, float))
                for argument in node.args[:4]
            )
        ):
            x, y, width, height = [argument.value for argument in node.args[:4]]
            if x == 0 and y == 0 and (width > 160 or height > 120):
                self.resolution_warnings.append(
                    (
                        f"Full-screen rectangle is {width}x{height}; badge drawing "
                        "coordinates use the 160x120 logical framebuffer.",
                        node.lineno,
                    )
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._depth == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.bindings.add(target.id)
                    if isinstance(node.value, ast.Lambda):
                        kind = "function"
                    elif isinstance(node.value, (ast.Name, ast.Attribute)):
                        kind = "alias"
                    elif isinstance(
                        node.value,
                        (ast.Constant, ast.Dict, ast.List, ast.Set, ast.Tuple),
                    ):
                        kind = "non-callable"
                    else:
                        kind = "unknown"
                    self.binding_kinds[target.id] = kind
        if isinstance(node.value, ast.Constant) and isinstance(
            node.value.value, (int, float)
        ):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id in {"SCREEN_WIDTH", "DISPLAY_WIDTH"} and node.value.value > 160:
                    self.resolution_warnings.append(
                        (
                            f"{target.id} is {node.value.value}; app coordinates should "
                            "normally use logical width 160.",
                            node.lineno,
                        )
                    )
                if target.id in {"SCREEN_HEIGHT", "DISPLAY_HEIGHT"} and node.value.value > 120:
                    self.resolution_warnings.append(
                        (
                            f"{target.id} is {node.value.value}; app coordinates should "
                            "normally use logical height 120.",
                            node.lineno,
                        )
                    )
        self.generic_visit(node)


def parse_python(path: Path, issues: list[Issue]) -> tuple[ast.AST | None, AppVisitor | None]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as error:
        line = getattr(error, "lineno", None)
        issues.append(Issue("ERROR", f"Python syntax/read failure: {error}", path, line))
        return None, None

    visitor = AppVisitor()
    visitor.visit(tree)
    return tree, visitor


def required_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    positional = [*node.args.posonlyargs, *node.args.args]
    required_count = len(positional) - len(node.args.defaults)
    required = [argument.arg for argument in positional[:required_count]]
    required.extend(
        argument.arg
        for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
        if default is None
    )
    return required


def resolve_asset(asset: str, app_dir: Path, repo_root: Path) -> Path | None:
    if asset.startswith("/system/"):
        return repo_root / "badge" / asset.removeprefix("/system/")
    if asset.startswith("/"):
        return None
    return app_dir / asset


def excluded_from_scan(relative: Path) -> bool:
    return any(
        part.startswith(".") or part == "__pycache__" for part in relative.parts
    )


def validate_app(app_dir: Path, repo_root: Path, target: str = "hardware") -> list[Issue]:
    issues: list[Issue] = []
    if not app_dir.is_dir():
        return [Issue("ERROR", f"App directory does not exist: {app_dir}")]
    app_root = app_dir.resolve()

    if not APP_NAME_RE.fullmatch(app_dir.name):
        issues.append(
            Issue(
                "WARNING",
                "For new apps, start the directory name with a lowercase letter "
                "and use only lowercase letters, numbers, hyphens, or underscores. "
                "Existing app names do not need to change.",
                app_dir,
            )
        )

    for path in sorted(app_dir.rglob("*")):
        if path.is_symlink():
            issues.append(
                Issue(
                    "ERROR",
                    "Symlinks are not safe to deploy; copy the file or directory "
                    "into the app.",
                    path,
                )
            )

    entrypoint = app_dir / "__init__.py"
    if not entrypoint.is_file():
        issues.append(Issue("ERROR", "Missing required __init__.py", entrypoint))
        return issues

    icon = app_dir / "icon.png"
    if icon.is_file():
        try:
            width, height, _, _ = png_info(icon)
            if width != height or width < 24:
                issues.append(
                    Issue(
                        "WARNING",
                        f"icon.png is {width}x{height}; use a square PNG of at "
                        "least 24x24 (48x48 looks sharpest in the menu).",
                        icon,
                    )
                )
        except (OSError, ValueError, struct.error) as error:
            issues.append(Issue("ERROR", f"Invalid icon.png: {error}", icon))
    else:
        issues.append(
            Issue(
                "WARNING",
                "No icon.png; the menu will show its default icon.",
                icon,
            )
        )

    readme = app_dir / "README.md"
    if not readme.is_file():
        issues.append(
            Issue(
                "WARNING",
                "Missing README.md. badger/home requires one whose first "
                "paragraph is a one-sentence description of the app.",
                readme,
            )
        )

    parsed: dict[Path, AppVisitor] = {}
    for python_file in sorted(app_dir.rglob("*.py")):
        if python_file.is_symlink() or excluded_from_scan(
            python_file.relative_to(app_dir)
        ):
            continue
        _, visitor = parse_python(python_file, issues)
        if visitor is not None:
            parsed[python_file] = visitor

    entry_visitor = parsed.get(entrypoint)
    if entry_visitor is not None:
        if "update" not in entry_visitor.bindings:
            issues.append(
                Issue(
                    "ERROR",
                    "Required update binding is missing. Define update() or import it "
                    "into __init__.py.",
                    entrypoint,
                )
            )
        elif (
            not entry_visitor.uses_legacy_badgeware_api
            and not entry_visitor.module_run_update_lines
        ):
            issues.append(
                Issue(
                    "ERROR",
                    "U26 apps must call run(update) at module level, outside a "
                    "__main__ guard, so the launcher starts the frame loop.",
                    entrypoint,
                )
            )
        for lifecycle_name in LIFECYCLE_NAMES:
            node = entry_visitor.function_nodes.get(lifecycle_name)
            kind = entry_visitor.binding_kinds.get(lifecycle_name)
            if kind == "async-function":
                issues.append(
                    Issue(
                        "ERROR",
                        f"{lifecycle_name}() must be synchronous; the launcher does "
                        "not await coroutine functions.",
                        entrypoint,
                        node.lineno if node is not None else None,
                    )
                )
            elif lifecycle_name != "on_exit" and kind in {"module", "non-callable"}:
                issues.append(
                    Issue(
                        "ERROR",
                        f"{lifecycle_name} is bound as {kind} and cannot be used as "
                        "a launcher callback.",
                        entrypoint,
                    )
                )
            elif kind == "unknown":
                issues.append(
                    Issue(
                        "WARNING",
                        f"Could not prove that {lifecycle_name} is callable; verify "
                        "the assigned value accepts no arguments.",
                        entrypoint,
                    )
                )
            if node is None:
                continue
            required = required_parameters(node)
            if required:
                issues.append(
                    Issue(
                        "ERROR",
                        f"{lifecycle_name}() must be callable with no arguments; "
                        f"required parameter(s): {', '.join(required)}.",
                        entrypoint,
                        node.lineno,
                    )
                )

    locals_ = local_modules(app_dir)
    loaded_pngs: set[Path] = set()
    for python_file, visitor in parsed.items():
        for name, line in visitor.badgeware_names:
            if name == "*":
                issues.append(
                    Issue(
                        "WARNING",
                        "Wildcard badgeware import hides which hardware APIs the app uses.",
                        python_file,
                        line,
                    )
                )
            elif name not in BADGEWARE_NAMES:
                issues.append(
                    Issue(
                        "WARNING",
                        f"'{name}' is not part of the U26 badgeware import API; use the "
                        "documented runtime globals or verify it against current firmware.",
                        python_file,
                        line,
                    )
                )

        for imported, line in visitor.imports:
            root = module_root(imported)
            if root in locals_ or root in {"", "__future__"}:
                continue
            if target in {"both", "hardware"} and root in DESKTOP_ONLY_MODULES:
                issues.append(
                    Issue(
                        "ERROR",
                        f"Desktop-only module '{root}' is not available in badge MicroPython.",
                        python_file,
                        line,
                    )
                )
            if target in {"both", "emulator"} and (
                root in HARDWARE_ONLY_MODULES or root.startswith("breakout_")
            ):
                if root == "bluetooth" and target == "emulator":
                    message = (
                        "BLE behavior requires real peers; verify the chosen "
                        "emulator's bluetooth support and test on physical badges."
                    )
                else:
                    message = (
                        f"'{root}' uses hardware-specific APIs; check support in "
                        "the chosen emulator and test physical behavior on the badge."
                    )
                issues.append(
                    Issue(
                        "WARNING",
                        message,
                        python_file,
                        line,
                    )
                )

        for asset, line in visitor.asset_paths:
            asset_path = resolve_asset(asset, app_dir, repo_root)
            if asset_path is None:
                continue
            asset_path = asset_path.resolve()
            if not asset.startswith("/") and not asset_path.is_relative_to(app_root):
                issues.append(
                    Issue(
                        "ERROR",
                        f"Referenced relative asset resolves outside the app directory: "
                        f"{asset}. Use /system/... for shared system assets.",
                        python_file,
                        line,
                    )
                )
                continue
            if not asset_path.is_file():
                issues.append(
                    Issue("ERROR", f"Referenced asset does not exist: {asset}", python_file, line)
                )
            elif asset_path.suffix.lower() == ".png":
                loaded_pngs.add(asset_path)

        for message, line in visitor.resolution_warnings:
            issues.append(Issue("WARNING", message, python_file, line))

    estimated_bytes = 0
    image_count = 0
    for png in sorted(app_dir.rglob("*.png")):
        if png.is_symlink() or excluded_from_scan(png.relative_to(app_dir)):
            continue
        try:
            width, height, _, color_type = png_info(png)
        except (OSError, ValueError, struct.error) as error:
            issues.append(Issue("ERROR", f"Invalid PNG: {error}", png))
            continue
        if png.resolve() in loaded_pngs:
            image_count += 1
            bytes_per_pixel = 1 if color_type == 3 else 4
            estimated_bytes += width * height * bytes_per_pixel

    if estimated_bytes > 400 * 1024:
        issues.append(
            Issue(
                "WARNING",
                f"{image_count} statically referenced PNGs estimate to "
                f"{estimated_bytes / 1024:.1f} KiB of pixel storage, above this tool's "
                "400 KiB advisory threshold, not a firmware limit. Load assets on "
                "demand and measure memory on the target.",
                app_dir,
            )
        )
    elif estimated_bytes > 200 * 1024:
        issues.append(
            Issue(
                "WARNING",
                f"{image_count} statically referenced PNGs estimate to "
                f"{estimated_bytes / 1024:.1f} KiB of pixel storage. This advisory "
                "estimate excludes overhead and does not prove memory use. "
                "Profile assets on the target.",
                app_dir,
            )
        )

    if (app_dir / "secrets.py").exists():
        issues.append(
            Issue(
                "ERROR",
                "App-local secrets.py risks credential deployment or commits. Use the "
                "badge root secrets.py and never copy credentials implicitly.",
                app_dir / "secrets.py",
            )
        )

    return issues


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", help="App name or path")
    parser.add_argument(
        "--target",
        choices=("both", "emulator", "hardware"),
        default="hardware",
        help="Target-specific warnings to include (default: hardware)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Project root used to resolve /system paths (default: current project)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo_root = project_root(args.repo_root)
        app_dir = resolve_app(args.app, repo_root)
        issues = validate_app(app_dir, repo_root, args.target)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    errors = [issue for issue in issues if issue.severity == "ERROR"]
    warnings = [issue for issue in issues if issue.severity == "WARNING"]
    for issue in errors + warnings:
        print(issue.render(repo_root))

    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"OK: {app_dir} ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
