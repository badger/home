"""Synthetic camera only: exercise the badge without claiming real sensor tests."""

import argparse
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PIL import Image, ImageDraw


def picture(width, height, label, background):
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((width // 2, 0, width, height // 2), fill=(20, 220, 60))
    draw.rectangle((0, height // 2, width // 2, height), fill=(30, 70, 240))
    draw.rectangle((width // 2, height // 2, width, height), fill=(240, 210, 30))
    draw.text((12, 22), label, fill="white", stroke_width=1)
    return image


def encode(image):
    output = io.BytesIO()
    image.save(output, "JPEG", quality=75)
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    directory = None
    captures = 0
    previews = 0
    fail_capture = False
    delay_preview = 0
    live = encode(picture(320, 240, "SYNTHETIC LIVE", (220, 25, 30)))

    def reply(self, status, data, content_type="application/json"):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The badge can cancel a live frame to take a photo or exit.

    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == "/status":
            self.reply(200, {"protocol": 1, "camera": True, "sd": True})
        elif route.path == "/preview":
            import time
            time.sleep(type(self).delay_preview)
            type(self).previews += 1
            self.reply(200, self.live, "image/jpeg")
        elif route.path == "/thumbnail":
            photo_id = parse_qs(route.query).get("id", [""])[0]
            if not self.valid_id(photo_id):
                return self.reply(400, b"Bad id", "text/plain")
            path = self.directory / (photo_id + ".thumb.jpg")
            if not path.exists():
                return self.reply(404, b"No thumbnail", "text/plain")
            self.reply(200, path.read_bytes(), "image/jpeg")
        elif route.path == "/stats":
            self.reply(200, {"captures": self.captures, "previews": self.previews})
        else:
            self.reply(404, b"Not found", "text/plain")

    @staticmethod
    def valid_id(value):
        return len(value) == 16 and all(c in "0123456789abcdef" for c in value)

    def do_POST(self):
        route = urlsplit(self.path)
        if route.path == "/test/fail":
            type(self).fail_capture = parse_qs(route.query).get("enabled") == ["1"]
            return self.reply(200, {"ok": True})
        if route.path == "/test/slow":
            type(self).delay_preview = 15 if parse_qs(route.query).get("enabled") == ["1"] else 0
            return self.reply(200, {"ok": True})
        if route.path != "/capture":
            return self.reply(404, b"Not found", "text/plain")
        if self.fail_capture:
            return self.reply(507, b"SD card unavailable", "text/plain")
        photo_id = parse_qs(route.query).get("id", [""])[0]
        if not self.valid_id(photo_id):
            return self.reply(400, b"Bad id", "text/plain")
        path = self.directory / (photo_id + ".jpg")
        if not path.exists():
            full = picture(1600, 1200, "SYNTHETIC SAVED " + photo_id, (180, 25, 190))
            full.save(path, "JPEG", quality=95)
            # Thumbnail is deliberately made from the reopened saved JPEG.
            with Image.open(path) as saved:
                saved.resize((200, 150)).save(
                    self.directory / (photo_id + ".thumb.jpg"), "JPEG", quality=75
                )
            type(self).captures += 1
        self.reply(200, {"id": photo_id, "saved": True, "width": 1600, "height": 1200})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    Handler.directory = args.directory
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print("SYNTHETIC camera listening on port", args.port, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
