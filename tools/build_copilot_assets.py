#!/usr/bin/env python3
"""Build the badge's offline character pack from pinned Agent Buddy artwork."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
from pathlib import Path
from urllib.request import urlopen

from PIL import Image


REVISION = "c246248cc091b59fb199c54ad7f40fab0836e00a"
BASE_URL = "https://raw.githubusercontent.com/DanWahlin/agent-buddy/" + REVISION
OUTPUT = Path(__file__).resolve().parents[1] / "badge/apps/Copilot"
SIZE = (192, 180)
MAX_BUNDLE_BYTES = 3_000_000
TRACKS = {
    "left": "sprites",
    "right": "sprites",
    "up": "sprites",
    "down": "sprites",
    "surprise": "expressions",
    "working": "expressions",
    "attention": "expressions",
    "complete": "expressions",
}


def fetch(path):
    with urlopen(BASE_URL + "/" + path, timeout=60) as response:
        return response.read()


def resize(source, size):
    rgba = source.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def build(output):
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for directory in ("sprites", "expressions"):
        path = "characters/copilot/" + directory + "/animation.json"
        manifests[directory] = json.loads(fetch(path))

    jobs = [("neutral", "sprites/right-00.png")]
    jobs.extend(("blink-%d" % level, "sprites/right-00-blink-%d.png" % level)
                for level in range(1, 5))
    for track, directory in TRACKS.items():
        frames = manifests[directory]["directions"][track]["frames"]
        if len(frames) != 24:
            raise ValueError("Expected 24 source frames for " + track)
        # Sample the full movement, including its neutral and final poses.
        for index in range(12):
            source_index = (index * 23 + 5) // 11
            jobs.append(("%s-%02d" % (track, index),
                         directory + "/" + frames[source_index]["file"]))

    def convert(job):
        name, source_path = job
        source_path = "characters/copilot/" + source_path
        raw = fetch(source_path)
        with Image.open(BytesIO(raw)) as source:
            frame = resize(source, SIZE)
            frame.save(assets / (name + ".png"), optimize=True)
            if name == "neutral":
                icon = resize(source, (26, 24)).crop((1, 0, 25, 24))
                icon.save(output / "icon.png", optimize=True)
        return {"file": name + ".png", "source": source_path,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "sha256": hashlib.sha256((assets / (name + ".png")).read_bytes()).hexdigest()}

    with ThreadPoolExecutor(max_workers=6) as pool:
        files = list(pool.map(convert, jobs))
    (assets / "LICENSE.txt").write_bytes(fetch("LICENSE"))
    metadata = {
        "repository": "https://github.com/DanWahlin/agent-buddy",
        "revision": REVISION,
        "size": list(SIZE),
        "frames_per_track": 12,
        "conversion": "Composite on black, RGB, Lanczos resize; Pillow " + Image.__version__,
        "files": files,
    }
    (assets / "sources.json").write_text(json.dumps(metadata, indent=2) + "\n")
    size = sum(path.stat().st_size for path in assets.iterdir() if path.is_file())
    if size > MAX_BUNDLE_BYTES:
        raise ValueError("Character pack exceeds flash budget: %d bytes" % size)
    print("Built %d frames, %d bytes in %s" % (len(files), size, assets))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    build(parser.parse_args().output)
