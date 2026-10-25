#!/bin/sh
set -eu
skill_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$skill_root/scripts/install_skill.py"
