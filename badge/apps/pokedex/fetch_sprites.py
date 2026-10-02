#!/usr/bin/env python3
"""Download Gen 1 Pokemon sprites for the badge Pokedex app.

Fetches normal and shiny sprites (64x64 PNG) from PokeAPI via wsrv.nl proxy.
Sprites are Nintendo/Game Freak/The Pokemon Company's intellectual property
and are NOT included in this repository. This script fetches them for
personal use on your badge.

Usage:
    python3 fetch_sprites.py              # Download to ./sprites/ and ./shiny/
    python3 fetch_sprites.py /Volumes/BADGER  # Download directly to badge
"""

import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://wsrv.nl/?url=https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{path}{id}.png&w=80&h=80&output=png"
MAX_POKEMON = 151
WORKERS = 10


def fetch_sprite(pokemon_id, output_dir, shiny=False):
    path = "shiny/" if shiny else ""
    subdir = "shiny" if shiny else "sprites"
    out_dir = os.path.join(output_dir, subdir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{pokemon_id}.png")

    if os.path.exists(out_path):
        return pokemon_id, shiny, True

    url = BASE_URL.format(id=pokemon_id, path=path)
    try:
        result = subprocess.run(
            ["curl", "-sf", url, "-o", out_path],
            capture_output=True, timeout=30,
        )
        return pokemon_id, shiny, result.returncode == 0
    except Exception:
        return pokemon_id, shiny, False


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    tasks = []
    for pid in range(1, MAX_POKEMON + 1):
        tasks.append((pid, False))  # normal
        tasks.append((pid, True))   # shiny

    total = len(tasks)
    done = 0
    failed = []

    print(f"Fetching {total} sprites ({MAX_POKEMON} normal + {MAX_POKEMON} shiny)...")

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(fetch_sprite, pid, output_dir, is_shiny): (pid, is_shiny)
            for pid, is_shiny in tasks
        }
        for future in as_completed(futures):
            pid, is_shiny, ok = future.result()
            done += 1
            label = "shiny" if is_shiny else "normal"
            if not ok:
                failed.append((pid, label))
                print(f"  FAILED: {label} #{pid}")
            if done % 50 == 0:
                print(f"  {done}/{total} complete...")

    print(f"\nDone! {done - len(failed)}/{total} sprites downloaded.")
    if failed:
        print(f"{len(failed)} failed: {failed}")

    # Verify
    sprites_dir = os.path.join(output_dir, "sprites")
    shiny_dir = os.path.join(output_dir, "shiny")
    normal_count = len(os.listdir(sprites_dir)) if os.path.isdir(sprites_dir) else 0
    shiny_count = len(os.listdir(shiny_dir)) if os.path.isdir(shiny_dir) else 0
    print(f"Normal: {normal_count}, Shiny: {shiny_count}")


if __name__ == "__main__":
    main()
