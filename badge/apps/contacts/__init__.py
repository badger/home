import json

import hints
from badgeware import State
from badgeware import link as badgelink

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

GAME = "contacts"
STATE_KEY = "contacts"
BADGE_USER_FILE = "/state/badge_user.json"

OFFER_MS = 15000
SWAP_MS = 8000
DONE_MS = 2500

PALETTE = [
    (88, 58, 247),
    (22, 143, 251),
    (15, 191, 62),
    (247, 54, 120),
]
BASE_STRENGTH = 0.22

white = color.rgb(255, 255, 255)
black = color.rgb(0, 0, 0)
dim_white = color.rgb(255, 255, 255, 140)
faint_white = color.rgb(255, 255, 255, 60)
accent = color.rgb(*PALETTE[2])

name_font = font.ziplock
title_font = font.ignore
body_font = font.corset

WIDTH = 320
MARGIN = 4
TITLE_X = 8
TITLE_Y = 202
ROW_HEIGHT = 42
ROW_GAP = 4
ROW_PITCH = ROW_HEIGHT + ROW_GAP
LIST_TOP = 8
VISIBLE_ROWS = 4
QR_SIZE = 138
CARD_HEIGHT = 70

HINT_STYLE = hints.Style(white, dim_white, black)
HINT_RADIUS = 4


def shade(rgb, strength):
    return color.rgb(*(round(channel * strength) for channel in rgb))


def secret(key):
    return str(getattr(secrets, key, "") or "").strip()


def linkedin_url(value):
    value = value.strip()
    if not value:
        return ""
    if "linkedin.com/" in value:
        return value if value.startswith("https://") else "https://" + value.split("://")[-1]
    return "https://www.linkedin.com/in/" + value.strip("/")


def github_url(username):
    return "https://github.com/" + username if username else ""


def badge_user_name():
    try:
        with open(BADGE_USER_FILE) as f:
            data = json.load(f)
        return str(data.get("name") or data.get("login") or "")
    except (OSError, ValueError):
        return ""


def my_card(fallback_name):
    return {
        "name": secret("CONTACT_NAME") or badge_user_name() or fallback_name,
        "github": secret("GITHUB_USERNAME"),
        "linkedin": linkedin_url(secret("CONTACT_LINKEDIN")),
    }


def clean_card(value):
    if not isinstance(value, dict):
        return None
    card = {key: str(value.get(key, "")).strip()[:120] for key in ("name", "github", "linkedin")}
    if card["linkedin"] and not card["linkedin"].startswith("https://"):
        card["linkedin"] = ""
    if not card["name"] or not (card["github"] or card["linkedin"]):
        return None
    return card


def card_links(card):
    links = []
    if card.get("github"):
        links.append(("GitHub", github_url(card["github"])))
    if card.get("linkedin"):
        links.append(("LinkedIn", card["linkedin"]))
    return links


def fit(text, width):
    while text and screen.measure_text(text)[0] > width:
        text = text[:-1]
    return text


def centred(text, y, typeface, pen):
    screen.font = typeface
    screen.pen = pen
    text = fit(text, WIDTH - 16)
    width, _ = screen.measure_text(text)
    screen.text(text, (WIDTH - width) / 2, y)


def draw_ribbon(title):
    screen.font = title_font
    screen.pen = white
    screen.text(title, TITLE_X, TITLE_Y)


def draw_hint(label, shape, right):
    screen.font = body_font
    label_width, _ = screen.measure_text(label)
    dots_width = hints.hint_width(shape, HINT_RADIUS)
    left = right - label_width - 6 - dots_width
    hints.draw_hint(HINT_STYLE, shape, shape, left + dots_width / 2, 219, HINT_RADIUS)
    screen.pen = dim_white
    screen.text(label, left + dots_width + 6, 213)
    return left - 12


def draw_hints(*pairs):
    right = WIDTH - TITLE_X
    for label, shape in pairs:
        right = draw_hint(label, shape, right)


def draw_tile(left, top, width, height, rgb, selected):
    if selected:
        screen.pen = white
        screen.rectangle(left, top, width, height)
        screen.pen = color.rgb(*rgb)
        screen.rectangle(left + 2, top + 2, width - 4, height - 4)
    else:
        screen.pen = shade(rgb, BASE_STRENGTH)
        screen.rectangle(left, top, width, height)


class Book:
    def __init__(self):
        saved = {"cards": []}
        State.load(STATE_KEY, saved)
        self.cards = []
        for entry in saved["cards"] if isinstance(saved["cards"], list) else []:
            card = clean_card(entry)
            if card is not None:
                card["badge"] = str(entry.get("badge", ""))
                self.cards.append(card)

    def add(self, card, badge_id):
        card = dict(card)
        card["badge"] = badgelink.badge_id_hex(badge_id)
        self.cards = [existing for existing in self.cards if existing["badge"] != card["badge"]]
        self.cards.insert(0, card)
        State.save(STATE_KEY, {"cards": self.cards})


class Swap:
    def __init__(self, card, partner_id):
        self.partner_id = partner_id
        self.outgoing = json.dumps(card).encode()
        self.chunks = None
        self.sent = 0
        self.parts = {}
        self.total = None
        self.card = None
        self.acked = False

    def pump(self, link):
        if self.chunks is None:
            size = max(1, link.capacity() - 3)
            self.chunks = [self.outgoing[index:index + size] for index in range(0, len(self.outgoing), size)]
        while self.sent < len(self.chunks):
            chunk = b"C" + bytes((self.sent, len(self.chunks))) + self.chunks[self.sent]
            if not link.send(chunk):
                return
            self.sent += 1

    def receive(self, message, link):
        kind = message[:1]
        if kind == b"K":
            self.acked = True
        elif kind == b"C" and len(message) >= 3 and self.card is None:
            self.total = message[2]
            self.parts[message[1]] = message[3:]
            if len(self.parts) == self.total:
                try:
                    card = clean_card(json.loads(b"".join(self.parts[index] for index in range(self.total))))
                except (KeyError, ValueError):
                    card = None
                if card is not None:
                    self.card = card
                    link.send(b"K")

    @property
    def done(self):
        return self.card is not None and self.acked


class Contacts:
    HOME = 0
    OFFER = 1
    SWAP = 2
    DONE = 3
    LIST = 4
    DETAIL = 5

    def __init__(self):
        self.link = badgelink.Link(GAME)
        self.proximity = badgelink.Proximity(self.link)
        self.book = Book()
        self.card = my_card(self.link.name)
        self.mode = self.HOME
        self.mode_at = 0
        self.was_linked = False
        self.my_accept = False
        self.their_accept = False
        self.swap = None
        self.saved = None
        self.message = ""
        self.cursor = 0
        self.top_row = 0
        self.link_index = 0
        self.qr = None
        self.qr_url = None

    @property
    def card_ready(self):
        return bool(card_links(self.card))

    def set_mode(self, mode, now):
        self.mode = mode
        self.mode_at = now

    def part(self, now, message=""):
        partner = self.link.partner
        self.proximity.rest(partner.id if partner else None, now)
        self.link.leave()
        self.swap = None
        self.message = message
        self.set_mode(self.HOME, now)

    def update(self, now):
        self.link.pump()
        linked = self.link.linked
        if linked and not self.was_linked:
            if self.mode == self.HOME:
                self.my_accept = False
                self.their_accept = False
                self.message = ""
                self.set_mode(self.OFFER, now)
            else:
                self.link.leave()
        if self.was_linked and not linked and self.mode in (self.OFFER, self.SWAP):
            self.proximity.clear()
            if self.swap is not None and self.swap.card is not None:
                self.finish(now)
            else:
                self.message = "they walked away"
                self.swap = None
                self.set_mode(self.HOME, now)
        self.was_linked = linked

        if linked:
            for message in self.link.receive():
                self.handle(message, now)

        if self.mode == self.HOME:
            self.home_frame(now)
        elif self.mode == self.OFFER:
            self.offer_frame(now)
        elif self.mode == self.SWAP:
            self.swap_frame(now)
        elif self.mode == self.DONE:
            if now - self.mode_at > DONE_MS:
                self.set_mode(self.HOME, now)
        elif self.mode == self.LIST:
            self.list_frame(now)
        elif self.mode == self.DETAIL:
            self.detail_frame(now)
        self.link.update()

        lights = self.proximity.lights(now) if self.mode == self.HOME else None
        badge.caselights(*(lights or (0.5 if self.mode in (self.OFFER, self.SWAP) else 0,)))

    def handle(self, message, now):
        if message == b"A":
            self.their_accept = True
        elif message == b"D":
            self.part(now, "they said no thanks")
        elif self.swap is not None:
            self.swap.receive(message, self.link)

    def home_frame(self, now):
        if self.card_ready:
            self.proximity.update(now)
        if badge.pressed(BUTTON_SELECT) and self.book.cards:
            self.proximity.clear()
            self.cursor = 0
            self.top_row = 0
            self.set_mode(self.LIST, now)
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
            reset()

    def offer_frame(self, now):
        if badge.pressed(BUTTON_SELECT) and not self.my_accept:
            self.my_accept = True
            self.swap = Swap(self.card, self.link.partner.id)
            self.link.send(b"A")
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
            self.link.send(b"D")
            self.part(now)
            return
        if self.my_accept and self.their_accept:
            self.set_mode(self.SWAP, now)
        elif now - self.mode_at > OFFER_MS:
            self.link.send(b"D")
            self.part(now, "swap timed out")

    def swap_frame(self, now):
        self.swap.pump(self.link)
        if self.swap.done:
            self.finish(now)
        elif now - self.mode_at > SWAP_MS:
            self.part(now, "swap failed, try again")

    def finish(self, now):
        self.saved = self.swap.card
        self.book.add(self.saved, self.swap.partner_id)
        self.part(now)
        self.set_mode(self.DONE, now)

    def list_frame(self, now):
        count = len(self.book.cards)
        if badge.pressed(BUTTON_DOWN) or badge.pressed(BUTTON_RIGHT):
            self.cursor = (self.cursor + 1) % count
        if badge.pressed(BUTTON_UP):
            self.cursor = (self.cursor - 1) % count
        self.top_row = max(min(self.top_row, self.cursor), self.cursor - VISIBLE_ROWS + 1)
        if badge.pressed(BUTTON_SELECT):
            self.link_index = 0
            self.qr_url = None
            self.set_mode(self.DETAIL, now)
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
            self.set_mode(self.HOME, now)

    def detail_frame(self, now):
        links = card_links(self.book.cards[self.cursor])
        if badge.pressed(BUTTON_RIGHT) and len(links) > 1:
            self.link_index = (self.link_index + 1) % len(links)
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
            self.set_mode(self.LIST, now)
            return
        url = links[self.link_index][1]
        if url != self.qr_url:
            self.qr = image.qr(url, image.QR_LOW, 2)
            self.qr_url = url

    def draw(self, now):
        screen.pen = black
        screen.clear()
        if self.mode == self.HOME:
            self.draw_home(now)
        elif self.mode == self.OFFER:
            self.draw_offer(now)
        elif self.mode == self.SWAP:
            self.draw_partner("swapping cards...", dim_white)
            draw_ribbon("contacts")
        elif self.mode == self.DONE:
            self.draw_done()
        elif self.mode == self.LIST:
            self.draw_list()
        elif self.mode == self.DETAIL:
            self.draw_detail()

    def draw_my_card(self, top):
        draw_tile(MARGIN, top, WIDTH - MARGIN * 2, CARD_HEIGHT, PALETTE[0], False)
        badgelink.draw_identicon(screen, self.link.id, MARGIN + 8, top + 8, 55)
        screen.font = name_font
        screen.pen = white
        screen.text(fit(self.card["name"], WIDTH - 90), MARGIN + 72, top + 6)
        screen.font = body_font
        screen.pen = dim_white
        lines = [label + " " + (self.card["github"] if label == "GitHub" else url.split("linkedin.com/")[-1]) for label, url in card_links(self.card)]
        for index, line in enumerate(lines or ["no links yet"]):
            screen.text(fit(line, WIDTH - 90), MARGIN + 72, top + 32 + index * 16)

    def draw_home(self, now):
        self.draw_my_card(LIST_TOP)
        if not self.card_ready:
            centred("add your GitHub or LinkedIn", 100, name_font, white)
            centred("in Settings to swap cards", 128, body_font, dim_white)
        else:
            peer = self.proximity.syncing()
            remaining = self.proximity.cooling(now)
            if peer is not None:
                progress = self.proximity.progress(now)
                centred("connecting..." if progress >= 1.0 else "syncing with " + peer.name, 98, name_font, white)
                screen.pen = faint_white
                screen.rectangle(TITLE_X, 128, WIDTH - TITLE_X * 2, 8)
                screen.pen = accent
                screen.rectangle(TITLE_X, 128, int((WIDTH - TITLE_X * 2) * progress), 8)
            elif remaining is not None:
                centred("pull apart to swap again", 104, name_font, dim_white)
            else:
                centred("hold badges back to back", 98, name_font, white)
                centred("to swap contact cards", 126, body_font, dim_white)
        if self.message:
            centred(self.message, 150, body_font, dim_white)
        count = len(self.book.cards)
        centred("%d contact%s" % (count, "" if count == 1 else "s"), 174, body_font, dim_white)
        draw_ribbon("contacts")
        if count:
            draw_hints(("contacts", (BUTTON_SELECT,)), ("menu", (BUTTON_LEFT,)))
        else:
            draw_hints(("menu", (BUTTON_LEFT,)))

    def draw_partner(self, status, pen):
        partner = self.link.partner
        if partner is None:
            return
        badgelink.draw_identicon(screen, partner.id, (WIDTH - 70) // 2, 14, 70)
        centred(partner.name, 94, name_font, white)
        centred(status, 122, body_font, pen)

    def draw_offer(self, now):
        if self.my_accept:
            status = "waiting for them..."
        elif self.their_accept:
            status = "they want to swap cards"
        else:
            status = "swap contact cards?"
        self.draw_partner(status, accent if self.their_accept else dim_white)
        remaining = max(0, OFFER_MS - (now - self.mode_at))
        screen.pen = faint_white
        screen.rectangle(TITLE_X, 156, int((WIDTH - TITLE_X * 2) * remaining / OFFER_MS), 4)
        draw_ribbon("contacts")
        if self.my_accept:
            draw_hints(("cancel", (BUTTON_LEFT,)))
        else:
            draw_hints(("swap", (BUTTON_SELECT,)), ("no thanks", (BUTTON_LEFT,)))

    def draw_done(self):
        centred("saved", 72, body_font, dim_white)
        centred(self.saved["name"], 94, name_font, white)
        draw_ribbon("contacts")

    def draw_list(self):
        cards = self.book.cards
        for slot in range(VISIBLE_ROWS):
            row = self.top_row + slot
            if row >= len(cards):
                break
            card = cards[row]
            top = LIST_TOP + slot * ROW_PITCH
            selected = row == self.cursor
            draw_tile(MARGIN, top, WIDTH - MARGIN * 2, ROW_HEIGHT, PALETTE[row % len(PALETTE)], selected)
            screen.font = name_font
            screen.pen = white if selected else dim_white
            screen.text(fit(card["name"], WIDTH - 30), MARGIN + 10, top + 2)
            screen.font = body_font
            screen.text(fit(" / ".join(label for label, _ in card_links(card)), WIDTH - 30), MARGIN + 10, top + 24)
        draw_ribbon("%d of %d" % (self.cursor + 1, len(cards)))
        draw_hints(("show", (BUTTON_SELECT,)), ("back", (BUTTON_LEFT,)))

    def draw_detail(self):
        card = self.book.cards[self.cursor]
        links = card_links(card)
        label, url = links[self.link_index]
        if self.qr is not None:
            screen.pen = white
            screen.rectangle((WIDTH - QR_SIZE) // 2 - 4, 4, QR_SIZE + 8, QR_SIZE + 8)
            screen.blit(self.qr, rect(0, 0, self.qr.width, self.qr.height), rect((WIDTH - QR_SIZE) // 2, 8, QR_SIZE, QR_SIZE))
        centred(card["name"], 154, name_font, white)
        centred(url.split("://")[-1], 180, body_font, dim_white)
        draw_ribbon(label.lower())
        if len(links) > 1:
            draw_hints(("next", (BUTTON_RIGHT,)), ("back", (BUTTON_LEFT,)))
        else:
            draw_hints(("back", (BUTTON_LEFT,)))


app = Contacts()


def update():
    now = badge.ticks
    app.update(now)
    app.draw(now)


def on_exit():
    badge.caselights(0)
    app.link.close()


run(update)
