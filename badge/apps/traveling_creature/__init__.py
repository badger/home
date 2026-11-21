"""Tabi suru Petto: a pixel pet that swaps homes between Universe 2026 badges."""

import gc
import json
import math
import os
import random
import sys


APP_DIR = "/system/apps/traveling_creature"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State

try:
    from badgeware import link as badgelink
except ImportError as error:
    badgelink = None
    print("Traveling Creature: badge link unavailable:", error)


APP_KEY = "traveling_creature"
STATE_KEY = "traveling_creature"
USER_FILE = "/state/badge_user.json"
SPECIES = ("mochi", "fuwa", "koro", "peta")
PET_NAMES = {"mochi": "モチ", "fuwa": "フワ", "koro": "コロ", "peta": "ペタ"}
LEGACY_NAMES = ("Mame", "Mochi", "Pochi", "Fuwa", "Koro", "Peta")
SHEET_ROWS = {"mochi": 0, "fuwa": 1, "koro": 2, "peta": 3, "egg": 4}
HABITATS = {"mochi": "house", "fuwa": "meadow", "koro": "desert", "peta": "garden"}
STAGES = ((1, "ちびっこ"), (3, "こども"), (6, "おとな"), (10, "でんせつ"))
ITEMS = ("star", "flower", "bag", "crown", "heart", "sparkle", "note", "swirl")
ACCESSORIES = ("star", "flower", "bag", "crown")
# Accessory positions inside the 24x24 pet sprite, before scaling.
ANCHORS = {
    "mochi": {"star": (0, 7), "flower": (17, 5), "bag": (16, 16), "crown": (8, 1)},
    "fuwa": {"star": (1, 5), "flower": (16, 5), "bag": (16, 15), "crown": (8, -2)},
    "koro": {"star": (1, 8), "flower": (17, 1), "bag": (16, 16), "crown": (8, 0)},
    "peta": {"star": (0, 10), "flower": (17, 10), "bag": (16, 16), "crown": (8, -3)},
}
FLIP_TOASTS = {
    "mochi": "どてっ！",
    "fuwa": "ふわふわ〜",
    "koro": "ころころ〜",
    "peta": "ぴたっ！",
}
HINTS = (
    "← → で なでる",
    "SELECT で こうかん",
    "MENU で たびにっき",
    "さかさまに してみて",
)
HOWTO_PAGES = (
    (
        "ペットを そだてよう",
        ("たまごから ペットが うまれるよ", "← → で なでると よろこぶよ", "だいじに そだててね"),
    ),
    (
        "ともだちと こうかん",
        ("バッジを ちかづけて", "SELECT で ペットを こうかん", "1だいに すめるのは 1ぴき"),
    ),
    (
        "たびして おおきく なる",
        ("いろんな ひとに あうと", "アイテムが ふえて そだつよ", "うみのおやに あえたら おかえり！"),
    ),
    (
        "あそびかた",
        (),
    ),
)
CONTROLS = (
    ("← →", "なでる"),
    ("SELECT", "こうかん"),
    ("MENU", "たびにっき"),
    ("BACK", "もどる"),
)
MAX_OWNERS = 65
MAX_SEEN = 128
MAX_ENCOUNTERS = 200
OFFER_MS = 15000
SWAP_MS = 15000
DONE_MS = 5200
HATCH_MS = 1500
REACT_MS = 2400
TOAST_MS = 2200
FLOOR = 102

INK = color.rgb(70, 48, 62)
CARD = color.rgb(255, 255, 255, 238)
PILL = color.rgb(255, 255, 255, 205)
BAR = color.rgb(255, 255, 255, 190)
PINK = color.rgb(255, 128, 168)
GREEN = color.rgb(96, 186, 124)
PAPER = color.rgb(255, 248, 234)
RULE = color.rgb(242, 222, 214)
SHADOW = color.rgb(70, 40, 50, 60)
DOT_OFF = color.rgb(226, 206, 216)
TRACK = color.rgb(246, 226, 234)


class Glyphs:
    """Draws the bundled k8x12 Japanese bitmap font from a glyph atlas."""

    def __init__(self):
        with open("assets/font.txt", "rb") as file:
            data = file.read().decode("utf-8")
        rows, chars = data.split("\n", 1)
        self.index = {}
        for position, char in enumerate(chars):
            self.index[char] = position
        self.sheets = {}
        for tone in ("ink", "white"):
            self.sheets[tone] = image.load("assets/font_%s.png" % tone).spritesheet(
                32, int(rows)
            )
        self.cache = {}

    def sprite(self, char, tone):
        key = tone + char
        sprite = self.cache.get(key)
        if sprite is None:
            position = self.index.get(char, self.index.get("?", 0))
            sprite = self.sheets[tone].sprite(position % 32, position // 32)
            self.cache[key] = sprite
        return sprite

    def width(self, text, scale=1):
        total = 0
        for char in text:
            total += 4 if ord(char) < 128 else 8
        return total * scale

    def draw(self, text, x, y, tone="ink", scale=1):
        x = int(x)
        y = int(y)
        for char in text:
            if char != " ":
                screen.blit(self.sprite(char, tone), rect(x, y, 8 * scale, 12 * scale))
            x += (4 if ord(char) < 128 else 8) * scale

    def center(self, text, y, tone="ink", scale=1, cx=None):
        if cx is None:
            cx = screen.width // 2
        self.draw(text, cx - self.width(text, scale) // 2, y, tone, scale)

    def fit(self, text, width):
        if self.width(text) <= width:
            return text
        while text and self.width(text + "…") > width:
            text = text[:-1]
        return text + "…"


class Art:
    """Owns sprite sheets and keeps only one background image in memory."""

    def __init__(self):
        pets = image.load("assets/pets.png").spritesheet(4, 5)
        items = image.load("assets/items.png").spritesheet(len(ITEMS), 1)
        self.pets = {}
        for name, row in SHEET_ROWS.items():
            self.pets[name] = [pets.sprite(column, row) for column in range(4)]
        self.items = {}
        for column, name in enumerate(ITEMS):
            self.items[name] = items.sprite(column, 0)
        self.bg_name = None
        self.bg = None

    def background(self, name):
        if name != self.bg_name:
            self.bg = None
            gc.collect()
            self.bg = image.load("assets/bg_%s.png" % name)
            self.bg_name = name
        screen.blit(self.bg, vec2(0, 0))


def blit(sprite, x, y, size, flip_x=False, flip_y=False):
    # A negative rect size mirrors the sprite inside the same box.
    size = int(size)
    width = -size if flip_x else size
    height = -size if flip_y else size
    screen.blit(sprite, rect(int(x), int(y), width, height))


def rounded(x, y, width, height, radius, pen):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(int(x), int(y), int(width), int(height), radius))


def pill(text, x, y, pen=PILL, tone="ink"):
    width = glyphs.width(text) + 8
    rounded(x, y, width, 15, 6, pen)
    glyphs.draw(text, x + 4, y + 2, tone)
    return width


def _rand(low, high):
    return low + (high - low) * random.getrandbits(10) / 1023


def _text(value, limit=48):
    return str(value or "").strip()[:limit]


def _device_name(fallback):
    try:
        with open(USER_FILE) as file:
            data = json.load(file)
        name = _text(data.get("name") or data.get("login"), 32)
        if name:
            return name
    except (OSError, ValueError, AttributeError):
        pass
    return _text(fallback, 32) or "あなた"


def _clean_owner(owner):
    if not isinstance(owner, dict):
        return None
    badge_id = _text(owner.get("id"), 32)
    name = _text(owner.get("name"), 32)
    if not badge_id or not name:
        return None
    return {"id": badge_id, "name": name}


def _clean_pet(pet):
    if not isinstance(pet, dict):
        return None
    species = pet.get("species")
    if species not in SPECIES:
        return None
    pet_id = _text(pet.get("id"), 40)
    parent = _text(pet.get("parent"), 32)
    name = _text(pet.get("name"), 20)
    if not pet_id or not parent or not name:
        return None
    if name in LEGACY_NAMES:
        name = PET_NAMES[species]
    owners = []
    for entry in pet.get("owners", [])[:MAX_OWNERS] if isinstance(
        pet.get("owners"), list
    ) else []:
        owner = _clean_owner(entry)
        if owner is not None:
            owners.append(owner)
    seen = []
    for badge_id in pet.get("seen", [])[:MAX_SEEN] if isinstance(
        pet.get("seen"), list
    ) else []:
        badge_id = _text(badge_id, 32)
        if badge_id and badge_id not in seen:
            seen.append(badge_id)
    if parent not in seen:
        seen.insert(0, parent)
    return {
        "id": pet_id,
        "name": name,
        "species": species,
        "parent": parent,
        "parent_name": _text(pet.get("parent_name"), 32) or "だれか",
        "owners": owners,
        "seen": seen[:MAX_SEEN],
        "hosts": _bounded_int(pet.get("hosts"), 0, 9999),
        "older": _bounded_int(pet.get("older"), 0, 999999),
        "marks": _bounded_int(pet.get("marks"), 0, 999999),
        "hatched": bool(pet.get("hatched", True)),
    }


def _bounded_int(value, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return minimum


def _stage(hosts, hatched=True):
    result = "あかちゃん" if hatched else "たまご"
    if hatched:
        for threshold, name in STAGES:
            if hosts >= threshold:
                result = name
    return result


class PetBook:
    def __init__(self):
        saved = {"pet": None, "encounters": [], "tutorial": False}
        State.load(STATE_KEY, saved)
        self.encounters = []
        if isinstance(saved.get("encounters"), list):
            self.encounters = saved["encounters"][-MAX_ENCOUNTERS:]
        self.pet = _clean_pet(saved.get("pet"))
        self.tutorial = bool(saved.get("tutorial", False))

    def save(self):
        State.save(
            STATE_KEY,
            {
                "pet": self.pet,
                "encounters": self.encounters[-MAX_ENCOUNTERS:],
                "tutorial": self.tutorial,
            },
        )

    def hatch(self, badge_id, owner_name):
        species = SPECIES[random.getrandbits(8) % len(SPECIES)]
        pet_id = "%s-%04x-%04x" % (
            badge_id[-8:],
            badge.ticks & 0xFFFF,
            random.getrandbits(16),
        )
        self.pet = {
            "id": pet_id,
            "name": PET_NAMES[species],
            "species": species,
            "parent": badge_id,
            "parent_name": owner_name,
            "owners": [{"id": badge_id, "name": owner_name}],
            "seen": [badge_id],
            "hosts": 0,
            "older": 0,
            "marks": 0,
            "hatched": False,
        }
        self.save()

    def accept(self, pet, badge_id, owner_name):
        old = self.pet
        previous = None
        if old is not None:
            previous = next(
                (entry for entry in self.encounters if entry.get("id") == pet["id"]),
                None,
            )
            self.encounters = [
                entry for entry in self.encounters if entry.get("id") != pet["id"]
            ]
            self.encounters.insert(
                0,
                {
                    "id": old["id"],
                    "name": old["name"],
                    "species": old["species"],
                    "hosts": old["hosts"],
                    "owners": old["owners"][-4:],
                },
            )
            self.encounters = self.encounters[:MAX_ENCOUNTERS]

        pet = _clean_pet(pet)
        if pet is None:
            return None, None
        if badge_id not in pet["seen"]:
            pet["seen"].append(badge_id)
            pet["seen"] = pet["seen"][-MAX_SEEN:]
            pet["hosts"] += 1
            pet["marks"] += 1
            pet["owners"].append({"id": badge_id, "name": owner_name})
            if len(pet["owners"]) > MAX_OWNERS:
                # Keep the birth parent and the 64 most recent hosts.
                if pet["owners"][0]["id"] == pet["parent"]:
                    pet["owners"].pop(1)
                else:
                    pet["owners"].pop(0)
                pet["older"] += 1
        self.pet = pet
        self.save()
        if pet["parent"] == badge_id:
            return "home", previous
        if previous is not None:
            return "remember", previous
        return "new", None


class PetTransfer:
    def __init__(self, pet):
        self.outgoing = json.dumps(pet).encode()
        self.chunks = None
        self.sent = 0
        self.parts = {}
        self.total = None
        self.pet = None
        self.acked = False
        self.ack_pending = False

    def pump(self, link):
        if self.chunks is None:
            chunk_size = max(1, link.capacity() - 3)
            self.chunks = [
                self.outgoing[index : index + chunk_size]
                for index in range(0, len(self.outgoing), chunk_size)
            ]
            if len(self.chunks) > 255:
                raise ValueError("pet history is too large to transfer")
        while self.sent < len(self.chunks):
            packet = b"C" + bytes((self.sent, len(self.chunks))) + self.chunks[self.sent]
            if not link.send(packet):
                break
            self.sent += 1
        if self.ack_pending and link.send(b"K"):
            self.ack_pending = False

    def receive(self, message):
        if message == b"K":
            self.acked = True
            return
        if message[:1] != b"C" or len(message) < 3 or self.pet is not None:
            return
        total = message[2]
        if total < 1 or message[1] >= total:
            return
        if self.total is None:
            self.total = total
        if self.total != total:
            return
        self.parts[message[1]] = message[3:]
        if len(self.parts) == self.total:
            try:
                self.pet = _clean_pet(
                    json.loads(
                        b"".join(self.parts[index] for index in range(self.total))
                    )
                )
            except (KeyError, ValueError, TypeError):
                self.pet = None
            if self.pet is not None:
                self.ack_pending = True

    @property
    def progress(self):
        sent = self.sent / len(self.chunks) if self.chunks else 0
        received = len(self.parts) / self.total if self.total else 0
        return min(1, (sent + received) / 2)

    @property
    def done(self):
        return self.pet is not None and self.acked and not self.ack_pending


class TravelingCreature:
    HOME = 0
    OFFER = 1
    TRANSFER = 2
    DIARY = 3
    DONE = 4
    TITLE = 5
    HOWTO = 6

    def __init__(self):
        self.link = badgelink.Link(APP_KEY) if badgelink is not None else None
        self.proximity = (
            badgelink.Proximity(self.link) if self.link is not None else None
        )
        self.book = PetBook()
        self.mode = self.TITLE
        self.mode_at = 0
        self.page = 0
        self.was_linked = False
        self.my_accept = False
        self.their_accept = False
        self.transfer = None
        self.event = ""
        self.event_previous = None
        self.event_from = ""
        self.toast = ""
        self.toast_at = -TOAST_MS
        self.diary_top = 0
        self.last_flip = badge.upside_down()
        self.flip_at = -REACT_MS
        self.pet_at = -REACT_MS
        self.hatch_at = None
        self.hatched_at = -REACT_MS
        self.spawn_at = 0
        self.particles = []
        self.owner_id = (
            badgelink.badge_id_hex(self.link.id) if self.link is not None else "simulator"
        )
        self.owner_name = _device_name(self.link.name if self.link is not None else "")
        if self.book.pet is None:
            self.book.hatch(self.owner_id, self.owner_name)

    # ----- state changes -------------------------------------------------

    def set_mode(self, mode, now):
        self.mode = mode
        self.mode_at = now

    def say(self, text, now):
        self.toast = text
        self.toast_at = now

    def leave(self, now, message=""):
        if self.link is not None:
            partner = self.link.partner
            self.proximity.rest(partner.id if partner else None, now)
            self.link.leave()
        self.transfer = None
        self.my_accept = False
        self.their_accept = False
        if message:
            self.say(message, now)
        self.set_mode(self.HOME, now)

    def update_link(self, now):
        if self.link is None:
            return
        self.link.pump()
        linked = self.link.linked
        if linked and not self.was_linked and self.mode == self.HOME:
            self.my_accept = False
            self.their_accept = False
            self.set_mode(self.OFFER, now)
        if self.was_linked and not linked and self.mode in (self.OFFER, self.TRANSFER):
            self.transfer = None
            self.say("つうしんが きれたよ", now)
            self.set_mode(self.HOME, now)
        self.was_linked = linked
        if linked:
            for message in self.link.receive():
                self.handle(message, now)
        self.link.update()

    def handle(self, message, now):
        if message == b"A":
            self.their_accept = True
        elif message == b"D":
            self.leave(now, "こうかんは やめたよ")
        elif self.transfer is not None:
            self.transfer.receive(message)

    def begin_transfer(self, now):
        self.transfer = PetTransfer(self.book.pet)
        self.set_mode(self.TRANSFER, now)

    def complete_transfer(self, now):
        if self.transfer is None or self.transfer.pet is None:
            return
        incoming = self.transfer.pet
        owners = incoming["owners"]
        self.event_from = owners[-1]["name"] if owners else incoming["parent_name"]
        self.event, self.event_previous = self.book.accept(
            incoming, self.owner_id, self.owner_name
        )
        self.transfer = None
        self.my_accept = False
        self.their_accept = False
        self.particles = []
        self.set_mode(self.DONE, now)

    @property
    def hatched(self):
        return bool(self.book.pet.get("hatched", False))

    def finish_hatch(self, now):
        self.hatch_at = None
        self.book.pet["hatched"] = True
        self.book.save()
        self.hatched_at = now
        self.spawn("sparkle", 8, 80, FLOOR - 30, 34, 40)
        self.say("うまれたよ！", now)

    def react_to_flip(self, now):
        self.flip_at = now
        if self.hatched:
            self.say(FLIP_TOASTS[self.book.pet["species"]], now)
        else:
            self.say("ゆらゆら…", now)

    # ----- particles -----------------------------------------------------

    def spawn(self, kind, count, x, y, spread=20, rise=30):
        now = badge.ticks
        for _ in range(count):
            self.particles.append(
                [
                    kind,
                    x + _rand(-spread, spread),
                    y + _rand(-6, 6),
                    _rand(-10, 10),
                    -_rand(rise * 0.6, rise),
                    now,
                    int(_rand(900, 1500)),
                ]
            )
        self.particles = self.particles[-24:]

    def update_particles(self, now, step):
        alive = []
        for particle in self.particles:
            if now - particle[5] < particle[6]:
                particle[1] += particle[3] * step
                particle[2] += particle[4] * step
                alive.append(particle)
        self.particles = alive

    def draw_particles(self, now, scale=1):
        for kind, x, y, _, _, born, life in self.particles:
            if now - born > life - 240 and (now // 60) % 2:
                continue
            blit(art.items[kind], x - 4 * scale, y - 4 * scale, 8 * scale)

    # ----- update --------------------------------------------------------

    def update(self):
        now = badge.ticks
        step = badge.ticks_delta / 1000
        upside_down = badge.upside_down()
        if upside_down != self.last_flip:
            self.last_flip = upside_down
            if self.mode == self.HOME:
                self.react_to_flip(now)

        self.update_link(now)
        self.update_particles(now, step)
        if self.hatch_at is not None and now - self.hatch_at >= HATCH_MS:
            self.finish_hatch(now)

        if self.mode == self.TITLE:
            if badge.pressed(BUTTON_SELECT) and self.book.tutorial:
                self.start_game(now)
            elif badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_MENU):
                self.page = 0
                self.set_mode(self.HOWTO, now)
        elif self.mode == self.HOWTO:
            self.update_howto(now)
        elif self.mode == self.HOME:
            self.update_home(now)
        elif self.mode == self.OFFER:
            if badge.pressed(BUTTON_SELECT) and not self.my_accept:
                self.my_accept = True
                self.link.send(b"A")
            elif badge.pressed(BUTTON_BACK):
                self.link.send(b"D")
                self.leave(now, "こうかんは やめたよ")
                return
            if self.my_accept and self.their_accept:
                self.begin_transfer(now)
            elif now - self.mode_at > OFFER_MS:
                self.link.send(b"D")
                self.leave(now, "じかんぎれ。ペットは そのまま")
        elif self.mode == self.TRANSFER:
            self.transfer.pump(self.link)
            if self.transfer.done:
                self.complete_transfer(now)
            elif now - self.mode_at > SWAP_MS:
                self.leave(now, "じかんぎれ。ペットは そのまま")
        elif self.mode == self.DIARY:
            count = len(self.diary_rows())
            if badge.pressed(BUTTON_DOWN):
                self.diary_top = min(max(0, count - 6), self.diary_top + 1)
            elif badge.pressed(BUTTON_UP):
                self.diary_top = max(0, self.diary_top - 1)
            elif badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_MENU):
                self.set_mode(self.HOME, now)
        elif self.mode == self.DONE:
            self.update_done(now)

    def update_howto(self, now):
        last = len(HOWTO_PAGES) - 1
        if badge.pressed(BUTTON_SELECT) or badge.pressed(BUTTON_RIGHT):
            if self.page < last:
                self.page += 1
            else:
                self.start_game(now)
        elif badge.pressed(BUTTON_LEFT) and self.page > 0:
            self.page -= 1
        elif badge.pressed(BUTTON_BACK):
            if self.page > 0:
                self.page -= 1
            elif self.book.tutorial:
                self.start_game(now)
            else:
                self.set_mode(self.TITLE, now)

    def start_game(self, now):
        if not self.book.tutorial:
            self.book.tutorial = True
            self.book.save()
        self.set_mode(self.HOME, now)
        if not self.hatched:
            self.say("たまごが あるよ", now)

    def update_home(self, now):
        if self.link is not None:
            self.proximity.update(now)
        if badge.pressed(BUTTON_MENU):
            self.diary_top = 0
            self.set_mode(self.DIARY, now)
        elif badge.pressed(BUTTON_SELECT):
            if not self.hatched:
                if self.hatch_at is None:
                    self.hatch_at = now
                    self.say("あっ！ うまれそう…", now)
            elif self.link is not None and self.link.linked:
                self.set_mode(self.OFFER, now)
            else:
                self.say("ちかくに バッジが ないよ", now)
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            self.pet_at = now
            if self.hatched:
                self.spawn("heart", 3, 80, FLOOR - 24 * self.pet_scale(), 22, 34)
                self.say("うれしそう！", now)
            else:
                self.say("なかで うごいてる…", now)

    def update_done(self, now):
        elapsed = now - self.mode_at
        if now - self.spawn_at > 320 and elapsed < DONE_MS - 600:
            self.spawn_at = now
            kind = {"home": "heart", "remember": "sparkle"}.get(self.event, "note")
            self.spawn(kind, 2, 80, FLOOR - 36, 54, 30)
        if elapsed >= DONE_MS or (elapsed > 1000 and badge.pressed(BUTTON_SELECT)):
            self.particles = []
            self.set_mode(self.HOME, now)

    # ----- pet drawing ---------------------------------------------------

    def pet_scale(self):
        if self.mode == self.HOME and self.book.pet["hosts"] >= 6:
            return 3
        return 2

    def pose(self, now):
        """Return x, y, column, flip_x, flip_y, show_items, shadow."""
        pet = self.book.pet
        scale = self.pet_scale()
        size = 24 * scale
        x = 80 - size / 2
        floor_y = FLOOR - size
        y = floor_y
        column = 1 if now % 3200 < 140 else 0
        flip_x = flip_y = False
        show_items = True
        shadow = 1.0
        if now - self.pet_at < 1200:
            column = 2
        elapsed = now - self.flip_at
        species = pet["species"]
        if elapsed < REACT_MS:
            if species == "mochi":
                fall = min(1, elapsed / 520)
                y = 16 + (floor_y - 16) * fall * fall
                if elapsed > 520:
                    column = 3
                    squash = max(0, 1 - (elapsed - 520) / 260)
                    y += 3 * squash
                shadow = 0.4 + 0.6 * fall
            elif species == "fuwa":
                progress = elapsed / REACT_MS
                y = 14 + (floor_y - 8 - 14) * progress
                x += 20 * math.sin(elapsed / 240)
                column = 2
                shadow = 0.4
            elif species == "koro":
                roll = min(1, elapsed / 1400)
                ease = 1 - (1 - roll) * (1 - roll)
                x = -size + (x + size) * ease
                if roll < 1:
                    column = 3
                    show_items = False
                    phase = (now // 110) % 4
                    flip_x = phase in (1, 2)
                    flip_y = phase in (2, 3)
                    y += abs(math.sin(elapsed / 90)) * 2
                elif elapsed < 1900:
                    column = 3
                    show_items = False
            elif species == "peta":
                if elapsed < 1400:
                    y = 14
                    flip_y = True
                    show_items = False
                    column = 2
                    shadow = 0.3
                else:
                    fall = min(1, (elapsed - 1400) / 380)
                    y = 14 + (floor_y - 14) * fall * fall
                    shadow = 0.3 + 0.7 * fall
        else:
            if species == "mochi":
                y -= abs(math.sin(now / 420)) * 2
            elif species == "fuwa":
                y -= 10 + 3 * math.sin(now / 450)
                shadow = 0.6
            elif species == "koro":
                x += 34 * math.sin(now / 2600)
                y -= abs(math.sin(now / 120)) * 1.5
                flip_x = math.cos(now / 2600) < 0
            elif species == "peta":
                phase = now % 2400
                if phase < 420:
                    y -= math.sin(math.pi * phase / 420) * 12
                    shadow = 0.7
        return x, y, column, flip_x, flip_y, show_items, shadow

    def draw_pet_at(self, pet, x, y, scale, column, flip_x=False, flip_y=False,
                    show_items=True, shadow=1.0, now=0):
        size = 24 * scale
        if shadow:
            screen.pen = SHADOW
            screen.shape(
                shape.ellipse(x + size / 2, FLOOR + 1, 9 * scale * shadow, 2 * scale)
            )
        if not pet.get("hatched", True):
            blit(art.pets["egg"][column], x, y, size)
            return
        blit(art.pets[pet["species"]][column], x, y, size, flip_x, flip_y)
        if not show_items:
            return
        anchors = ANCHORS[pet["species"]]
        for name in ACCESSORIES[: min(len(ACCESSORIES), pet["marks"])]:
            ax, ay = anchors[name]
            if flip_x:
                ax = 16 - ax
            blit(art.items[name], x + ax * scale, y + ay * scale, 8 * scale)
        if pet["hosts"] >= 10:
            for index in range(2):
                angle = now / 500 + index * math.pi
                if (now // 260 + index) % 3:
                    blit(
                        art.items["sparkle"],
                        x + size / 2 + math.cos(angle) * size * 0.62 - 4 * scale,
                        y + size / 2 + math.sin(angle) * size * 0.42 - 4 * scale,
                        8 * scale,
                    )

    def draw_home_pet(self, now):
        pet = self.book.pet
        scale = self.pet_scale()
        size = 24 * scale
        if not self.hatched:
            x = 80 - size / 2
            y = FLOOR - size
            column = 0
            if self.hatch_at is not None:
                elapsed = now - self.hatch_at
                column = 1 + min(2, elapsed * 3 // HATCH_MS)
                x += math.sin(elapsed / 28) * (1 + elapsed / 500)
            elif now - self.flip_at < 900 or now - self.pet_at < 700:
                x += math.sin(now / 45) * 3
            elif now % 4000 < 300:
                x += math.sin(now / 40) * 1.5
            self.draw_pet_at(pet, x, y, scale, column, now=now)
            return
        x, y, column, flip_x, flip_y, show_items, shadow = self.pose(now)
        self.draw_pet_at(pet, x, y, scale, column, flip_x, flip_y, show_items, shadow, now)
        elapsed = now - self.flip_at
        if pet["species"] == "mochi" and 520 < elapsed < REACT_MS:
            blit(art.items["swirl"], x + size / 2 - 6, y - 10, 12, (now // 160) % 2)
        flash = now - self.hatched_at
        if flash < 420:
            screen.pen = color.rgb(255, 255, 255, int(255 * (1 - flash / 420)))
            screen.rectangle(screen.clip)

    # ----- screens -------------------------------------------------------

    def draw_bar(self, text=None, left=None, right=None):
        screen.pen = BAR
        screen.rectangle(0, 106, screen.width, 14)
        if text:
            glyphs.center(glyphs.fit(text, screen.width - 8), 107)
        if left:
            glyphs.draw(left, 4, 107)
        if right:
            glyphs.draw(right, screen.width - 4 - glyphs.width(right), 107)

    def draw_toast(self, now, y=21):
        age = now - self.toast_at
        if not self.toast or age > TOAST_MS:
            return
        text = glyphs.fit(self.toast, screen.width - 24)
        width = glyphs.width(text) + 12
        lift = max(0, 4 - age // 30)
        rounded((screen.width - width) // 2, y + lift, width, 16, 7, CARD)
        glyphs.center(text, y + 2 + lift)

    def draw_status(self):
        pet = self.book.pet
        stage = _stage(pet["hosts"], self.hatched)
        name = pet["name"] if self.hatched else "？？？"
        pill("%s  %s" % (name, stage), 3, 3)
        if self.hatched:
            text = "であい %dにん" % pet["hosts"]
            width = glyphs.width(text) + 18
            x = screen.width - 3 - width
            rounded(x, 3, width, 15, 6, PILL)
            blit(art.items["heart"], x + 4, 7, 8)
            glyphs.draw(text, x + 14, 5)

    def draw_home(self, now):
        pet = self.book.pet
        art.background(HABITATS[pet["species"]])
        self.draw_home_pet(now)
        self.draw_particles(now)
        self.draw_status()
        if self.mode == self.OFFER:
            self.draw_offer(now)
            return
        if self.mode == self.TRANSFER:
            self.draw_transfer(now)
            return
        self.draw_toast(now)
        if not self.hatched:
            hint = "SELECT で うまれるよ"
        else:
            hint = HINTS[(now // 2600) % len(HINTS)]
        self.draw_bar(hint)

    def partner_name(self):
        if self.link is None or self.link.partner is None:
            return "だれか"
        return _text(self.link.partner.name, 16) or "だれか"

    def draw_offer(self, now):
        rounded(10, 26, 140, 66, 8, CARD)
        glyphs.center(glyphs.fit(self.partner_name(), 90) + " さんと", 32)
        glyphs.center("ペットを こうかんする？", 47)
        if self.my_accept:
            dots = "…" if (now // 400) % 2 else ""
            glyphs.center("あいての へんじを まってるよ" + dots, 64)
        else:
            glyphs.center("SELECT する   BACK しない", 64)
        remaining = max(0, 1 - (now - self.mode_at) / OFFER_MS)
        rounded(24, 82, 112, 4, 2, TRACK)
        if remaining > 0.02:
            rounded(24, 82, int(112 * remaining), 4, 2, PINK)
        self.draw_bar("こうかんすると ペットが いれかわるよ")

    def draw_transfer(self, now):
        rounded(10, 26, 140, 66, 8, CARD)
        glyphs.center("こうかんちゅう…", 34)
        glyphs.center("バッジを はなさないでね", 50)
        progress = self.transfer.progress if self.transfer is not None else 0
        rounded(24, 72, 112, 6, 3, TRACK)
        rounded(24, 72, max(6, int(112 * progress)), 6, 3, PINK)
        bob = int(abs(math.sin(now / 150)) * 3)
        blit(art.items["heart"], 76, 80 - bob, 8)
        self.draw_bar("じかんぎれなら ペットは そのまま")

    def draw_done(self, now):
        pet = self.book.pet
        elapsed = now - self.mode_at
        art.background(HABITATS[pet["species"]])
        scale = 2
        size = 24 * scale
        x = 80 - size / 2
        y = FLOOR - size - abs(math.sin(elapsed / 170)) * 6
        self.draw_pet_at(pet, x, y, scale, 2 if pet.get("hatched", True) else 0, now=now)
        self.draw_particles(now)
        if self.event == "home":
            headline = "おかえり！"
            detail = "%dにんと たびしたよ" % pet["hosts"]
            names = [owner["name"] for owner in pet["owners"][1:-1]][-3:]
            footer = "・".join(names) if names else "また いっしょだね"
        elif self.event == "remember":
            headline = "あ！ おぼえてる！"
            before = self.event_previous.get("hosts", 0) if self.event_previous else 0
            detail = "まえ %dにん → いま %dにん" % (before, pet["hosts"])
            footer = "また あえたね！"
        else:
            headline = "はじめまして！"
            detail = glyphs.fit(self.event_from, 72) + " さんから きたよ"
            footer = "よろしくね！"
        pop = max(0, 6 - elapsed // 40)
        rounded(8, 4, 144, 30, 8, CARD)
        glyphs.center(headline, 7 - pop, "ink", 2)
        width = glyphs.width(detail) + 12
        rounded((screen.width - width) // 2, 37, width, 16, 7, PILL)
        glyphs.center(detail, 39)
        self.draw_bar(glyphs.fit(footer, screen.width - 8))

    def diary_rows(self):
        # Returns (number, owner) pairs; None marks the trimmed older hosts.
        pet = self.book.pet
        owners = pet["owners"]
        older = pet["older"]
        rows = []
        start = 0
        if older and owners and owners[0]["id"] == pet["parent"]:
            rows.append((1, owners[0]))
            start = 1
        if older:
            rows.append((0, None))
        for offset, owner in enumerate(owners[start:]):
            rows.append((older + start + offset + 1, owner))
        return rows

    def draw_diary(self):
        pet = self.book.pet
        screen.pen = PAPER
        screen.rectangle(screen.clip)
        screen.pen = PINK
        screen.rectangle(0, 0, screen.width, 17)
        glyphs.draw("%sの たびにっき" % pet["name"], 5, 3, "white")
        count = "%dにん" % (len(pet["owners"]) + pet["older"])
        glyphs.draw(count, screen.width - 5 - glyphs.width(count), 3, "white")
        rows = self.diary_rows()
        for slot, (number, row) in enumerate(rows[self.diary_top : self.diary_top + 6]):
            y = 20 + slot * 14
            screen.pen = RULE
            screen.rectangle(4, y + 13, screen.width - 8, 1)
            if row is None:
                glyphs.draw("… ほか %dにん" % pet["older"], 8, y)
                continue
            glyphs.draw("%02d" % number, 6, y)
            tag = None
            if row["id"] == pet["parent"]:
                tag, pen = "うみのおや", PINK
            elif row["id"] == self.owner_id:
                tag, pen = "いま ここ", GREEN
            room = screen.width - 26 - (glyphs.width(tag) + 10 if tag else 0)
            glyphs.draw(glyphs.fit(row["name"], room), 18, y)
            if tag:
                width = glyphs.width(tag) + 8
                rounded(screen.width - 5 - width, y, width, 12, 5, pen)
                glyphs.draw(tag, screen.width - 1 - width, y, "white")
        self.draw_bar("↑↓ みる   BACK もどる")

    def draw_title(self, now):
        art.background("title")
        glyphs.draw("たびする ペット", 21, 15, "white", 2)
        glyphs.draw("たびする ペット", 20, 14, "ink", 2)
        glyphs.center("バッジから バッジへ", 42)
        if (now // 500) % 2 == 0:
            rounded(38, 56, 84, 15, 7, CARD)
            glyphs.center("SELECT で はじめる", 58)
        for index, species in enumerate(SPECIES):
            hop = abs(math.sin(now / 300 + index * 0.9)) * 4
            column = 1 if (now + index * 900) % 3000 < 140 else 0
            blit(art.pets[species][column], 14 + index * 36, 74 - hop, 24)
        if self.book.tutorial:
            rounded(44, 103, 72, 15, 7, CARD)
            glyphs.center("MENU で せつめい", 104)

    def draw_howto(self, now):
        art.background(HABITATS[self.book.pet["species"]])
        rounded(6, 3, 148, 101, 9, CARD)
        title, lines = HOWTO_PAGES[self.page]
        width = glyphs.width(title) + 20
        rounded((screen.width - width) // 2, 8, width, 16, 7, PINK)
        glyphs.center(title, 10, "white")
        if self.page == 3:
            for row, (key, label) in enumerate(CONTROLS):
                y = 30 + row * 15
                glyphs.draw(key, 22, y)
                glyphs.draw(label, 70, y)
            glyphs.center("さかさまに すると…？", 90)
        else:
            self.draw_howto_picture(now)
            for row, line in enumerate(lines):
                glyphs.center(line, 60 + row * 14)
        if self.page > 0:
            left = "← もどる"
        elif self.book.tutorial:
            left = "BACK とばす"
        else:
            left = None
        last = self.page == len(HOWTO_PAGES) - 1
        self.draw_bar(left=left, right="SELECT はじめる" if last else "SELECT つぎへ")
        for index in range(len(HOWTO_PAGES)):
            screen.pen = PINK if index == self.page else DOT_OFF
            screen.shape(shape.circle(70 + index * 7, 113, 2))

    def draw_howto_picture(self, now):
        bob = abs(math.sin(now / 260)) * 3
        if self.page == 0:
            blit(art.pets["egg"][0], 36, 30, 24)
            glyphs.draw("→", 70, 36)
            blit(art.pets["mochi"][2], 92, 30 - bob, 24)
            blit(art.items["heart"], 118, 34 - bob * 2, 8)
        elif self.page == 1:
            blit(art.pets["mochi"][0], 34, 30, 24)
            glyphs.draw("→", 76, 30)
            glyphs.draw("←", 76, 40)
            blit(art.pets["fuwa"][0], 102, 30 - bob, 24)
        else:
            for index, name in enumerate(ACCESSORIES):
                blit(art.items[name], 40 + index * 22, 32 - (bob if index % 2 else 0), 16)

    def draw(self):
        now = badge.ticks
        if self.mode == self.TITLE:
            self.draw_title(now)
        elif self.mode == self.HOWTO:
            self.draw_howto(now)
        elif self.mode == self.DIARY:
            self.draw_diary()
        elif self.mode == self.DONE:
            self.draw_done(now)
        else:
            self.draw_home(now)


glyphs = Glyphs()
art = Art()
app = TravelingCreature()


def update():
    app.update()
    app.draw()


def on_exit():
    if app.link is not None:
        app.link.close()


run(update)
