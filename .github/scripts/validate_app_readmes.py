#!/usr/bin/env python3
"""Validate that every app in badge/apps has a README with a valid description.

The first paragraph after the title must be a plain-text description of the app
(one to two short sentences). It is consumed by badger/badgerfactory to build
app-descriptions.json.
"""
import re
import sys
from pathlib import Path

MIN_LENGTH = 10
MAX_LENGTH = 200
SKIP_PREFIXES = ("#", ">", "|", "-", "*", "!", "[!", "```", "<")


def first_paragraph(readme):
    paragraph = []
    for line in readme.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            if paragraph:
                break
            continue
        if s.startswith(SKIP_PREFIXES):
            if paragraph:
                break
            continue
        paragraph.append(s)
    return " ".join(paragraph)


def first_sentence(text):
    match = re.match(r"(.+?[.!?])(?=\s|$)", text)
    return (match.group(1) if match else text).strip()


def check_app(app):
    readme = next((app / n for n in ("README.md", "readme.md") if (app / n).exists()), None)
    if readme is None:
        return "missing README.md"
    paragraph = first_paragraph(readme)
    if not paragraph:
        return "README.md has no description paragraph after the title"
    sentence = first_sentence(paragraph)
    if len(sentence) < MIN_LENGTH:
        return f"description is too short (minimum {MIN_LENGTH} characters)"
    if len(sentence) > MAX_LENGTH:
        return f"first sentence is too long ({len(sentence)} > {MAX_LENGTH} characters)"
    if sentence[-1] not in ".!?":
        return "first sentence must end with punctuation"
    return None


def main():
    apps_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "badge/apps")
    failures = 0
    for app in sorted(p for p in apps_dir.iterdir() if p.is_dir()):
        if not ((app / "__init__.py").exists() or (app / "__init__.mpy").exists()):
            continue
        error = check_app(app)
        if error:
            failures += 1
            print(f"::error file={app.as_posix()}/README.md::{app.name}: {error}")
    if failures:
        print(f"{failures} app(s) have an invalid README description.")
        return 1
    print("All app READMEs have a valid description.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
