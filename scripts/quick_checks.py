#!/usr/bin/env python3
"""Simple repository quick-checks for the Badger project.

Runs under CPython and performs non-runtime validations:
- presence of critical files (AGENTS.md, badge/main.py, copilot instructions)
- checks for apps in `badge/apps/` that each have `__init__.py` and `icon.png`
- warns if `badge/secrets.py` still contains default or empty credentials
- checks for bundled fonts in `assets/fonts/` (e.g. `nope.ppf`)

Exit codes:
 0 - all critical checks passed
 1 - one or more critical checks failed

Use: python scripts/quick_checks.py
"""
from pathlib import Path
import sys
import re
import struct

ROOT = Path(__file__).resolve().parents[1]

def exists(p):
    return (ROOT / p).exists()

def read(p):
    try:
        return (ROOT / p).read_text(encoding="utf-8")
    except Exception:
        return ""

critical_failures = []
warnings = []

print(f"Running quick checks in: {ROOT}\n")

# Critical files
for p in [".github/copilot-instructions.md", "badge/AGENTS.md", "badge/main.py", "README.md"]:
    if not exists(p):
        critical_failures.append(p)
        print(f"MISSING (critical): {p}")
    else:
        print(f"OK: {p}")

print("")

# Check apps
apps_dir = ROOT / "badge" / "apps"
if not apps_dir.exists() or not apps_dir.is_dir():
    critical_failures.append(str(apps_dir))
    print(f"MISSING (critical): {apps_dir} (expected directory with app subfolders)")
else:
    print("Inspecting apps in badge/apps/")
    for child in sorted(apps_dir.iterdir()):
        if not child.is_dir():
            continue
        init_py = child / "__init__.py"
        icon = child / "icon.png"
        if not init_py.exists():
            warnings.append(f"{child}/__init__.py")
            print(f"  WARNING: {child.name} missing __init__.py")
        else:
            print(f"  OK: {child.name}/__init__.py")
        if not icon.exists():
            warnings.append(f"{child}/icon.png")
            print(f"  WARNING: {child.name} missing icon.png (launcher expects 24x24 PNG)")
        else:
            # quick PNG dimension check (expect 24x24)
            try:
                def png_size(p):
                    with open(p, "rb") as f:
                        header = f.read(24)
                        if len(header) >= 24 and header.startswith(b"\x89PNG\r\n\x1a\n"):
                            width, height = struct.unpack('>II', header[16:24])
                            return width, height
                        return None

                size = png_size(icon)
                if size is None:
                    warnings.append(f"{child}/icon.png: not a valid PNG")
                    print(f"  WARNING: {child.name}/icon.png is not a valid PNG")
                else:
                    w, h = size
                    if (w, h) != (24, 24):
                        warnings.append(f"{child}/icon.png: {w}x{h}")
                        print(f"  WARNING: {child.name}/icon.png is {w}x{h} (expected 24x24)")
                    else:
                        print(f"  OK: {child.name}/icon.png (24x24)")
            except Exception:
                warnings.append(f"{child}/icon.png: error reading")
                print(f"  WARNING: {child.name}/icon.png could not be read")

        # check app assets folder (if present) has at least one usable file
        assets_dir = child / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            found = False
            for ext in (".png", ".ppf", ".json"):
                if any(assets_dir.rglob(f"*{ext}")):
                    found = True
                    break
            if not found:
                warnings.append(f"{child}/assets: empty or no recognized assets")
                print(f"  WARNING: {child.name}/assets/ appears to have no .png/.ppf/.json files")

print("")

# Fonts
fonts_dir = ROOT / "assets" / "fonts"
if not fonts_dir.exists():
    warnings.append(str(fonts_dir))
    print(f"WARNING: fonts directory not found at assets/fonts/")
else:
    sample = fonts_dir / "nope.ppf"
    if not sample.exists():
        warnings.append(str(sample))
        print(f"WARNING: sample font nope.ppf missing in assets/fonts/")
    else:
        print(f"OK: assets/fonts/nope.ppf")

# Sprite sheets directory
sprites_dir = ROOT / "assets" / "mona-sprites"
if not sprites_dir.exists() or not any(sprites_dir.glob("*.png")):
    warnings.append("assets/mona-sprites: no png sprite sheets found")
    print("WARNING: assets/mona-sprites/ contains no .png files")
else:
    print(f"OK: assets/mona-sprites/ contains sprite sheets")

print("")

# Secrets file quick-scan
secrets = ROOT / "badge" / "secrets.py"
if secrets.exists():
    content = secrets.read_text(encoding="utf-8")
    ssid_match = re.search(r"WIFI_SSID\s*=\s*\"(.*)\"", content)
    github_match = re.search(r"GITHUB_USERNAME\s*=\s*\"(.*)\"", content)
    if ssid_match:
        ssid = ssid_match.group(1)
        if ssid == "" or "u25-badger-party" in ssid:
            warnings.append("badge/secrets.py: WIFI_SSID default or empty")
            print("WARNING: badge/secrets.py contains default or empty WIFI_SSID")
        else:
            print("OK: badge/secrets.py WIFI_SSID set")
    if github_match:
        gh = github_match.group(1)
        if gh == "":
            warnings.append("badge/secrets.py: GITHUB_USERNAME empty")
            print("WARNING: badge/secrets.py GITHUB_USERNAME is empty")
        else:
            print("OK: badge/secrets.py GITHUB_USERNAME set")
else:
    warnings.append("badge/secrets.py missing")
    print("WARNING: badge/secrets.py not found")

print("\nSummary:")
print(f"  Critical failures: {len(critical_failures)}")
for f in critical_failures:
    print(f"    - {f}")
print(f"  Warnings: {len(warnings)}")
for w in warnings:
    print(f"    - {w}")

if critical_failures:
    print("\nOne or more critical checks failed. See above.")
    sys.exit(1)
else:
    print("\nAll critical checks passed.")
    if warnings:
        print("Address warnings as needed, but repository is structurally OK.")
    sys.exit(0)
