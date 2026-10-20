APP_DIR = "/system/apps/merge_conflict"

import json
import machine
import os
import random
import struct
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import replay

RECORD_ENABLED = False
STATE_PATH = "/state/merge_conflict.json"
LEGACY_STATE_PATH = "/state/micro_duel.json"

recorder = replay.start("merge_conflict", (STATE_PATH, LEGACY_STATE_PATH), RECORD_ENABLED)

import ui
from ui import ACCENT, BACKGROUND, BRIGHT, DIM, PANEL, RIVAL, TEXT, Control, centred
from pairing import Pairing

badge.mode(HIRES | VSYNC)

screen.antialias = image.OFF

SMALL = ui.BODY
LARGE = ui.TITLE
BIG = ui.HUGE
PAIRING_TEXT_Y = 160
pairing = Pairing(160, 104, 6)

PRACTICE_ENABLED = True
PRACTICE_CODE = (BUTTON_UP, BUTTON_UP, BUTTON_DOWN, BUTTON_DOWN)
PRACTICE_CODE_MS = 3000

GAME_NAME = "merge conflict"
STATE_DIR = "/state"

ROUNDS = 5
FIRST_ROUND_MS = 1500
COUNT_STEP_MS = 800
INTRO_MS = COUNT_STEP_MS * 3
RESULT_MS = 1800
REVEAL_RESULT_MS = 2600
FINAL_MS = 4500
AGAIN_MS = 10000
SCORE_WAIT_MS = 12000
LIVE_MS = 150
PING_TIMES = (200, 500, 800)

POINTS_WIN = 10
POINTS_LOSS = 3

CHART_COLS = 53
CHART_ROWS = 7
CHART_CELLS = CHART_COLS * CHART_ROWS
CHART_PACKED = (CHART_CELLS + 3) // 4
CHART_BLINK_MS = 6000

EMPTY_SQUARE = 0
LOST_SQUARE = 1
WON_SQUARE = 2

CHALLENGE_MS = 12000

LINK_GLOW = 0.6

CHART_PITCH = 6
CHART_W = CHART_COLS * CHART_PITCH - 1
CHART_H = CHART_ROWS * CHART_PITCH - 1
CHART_X = (320 - CHART_W) // 2

HEADER_ICON = 26
HEADER_X = 10
HEADER_Y = 8
HEADER_NAME_X = HEADER_X + HEADER_ICON + 8
HEADER_CHART_Y = HEADER_Y + HEADER_ICON + 6

CARD_ICON = 20
CARD_NAME_X = HEADER_X + CARD_ICON + 8
CARD_CHART_OFFSET = 22
SYNC_CARD_Y = 122
CHALLENGE_CARD_Y = 120

TALLY_ICON = 26
PRIMER_TOP = 112

AGAIN_CONTROLS = (
    Control("play again", BUTTON_LEFT, BUTTON_LEFT),
    Control("new opponent", BUTTON_SELECT, BUTTON_SELECT),
)
ACCEPT_CONTROLS = (Control("accept", BUTTON_SELECT),)
MENU_CONTROLS = (
    Control("move", (BUTTON_UP, BUTTON_DOWN)),
    Control("play", BUTTON_SELECT),
    Control("back", BUTTON_LEFT),
)
MENU_RESULT_CONTROLS = (Control("menu", BUTTON_LEFT),)

MENU_TOP = 36
MENU_ROW = 20
MENU_VISIBLE = 5
MENU_WIDTH = 304
MENU_HINT_CY = 158
MENU_HINT_RADIUS = 4
MENU_RESULT_GUARD_MS = 300
SPLASH_GLITCH_MS = 220
REVEAL_HEADLINE_Y = 6
REVEAL_TOP = 36


class Phase:
    LINKING = 0
    INTRO = 1
    PLAY = 2
    WAIT = 3
    RESULT = 4
    FINAL = 5
    CHALLENGE = 6
    AGAIN = 7
    MENU = 8


def load_record():
    data = {"points": 0, "order": [], "opponents": {}, "chart": "0" * CHART_CELLS}
    for path in (STATE_PATH, LEGACY_STATE_PATH):
        try:
            with open(path) as f:
                stored = json.loads(f.read())
            if isinstance(stored, dict):
                data.update(stored)
                break
        except (OSError, ValueError):
            pass
    cells = "".join(value if value in "012" else "0" for value in str(data.get("chart", "")))
    data["chart"] = (cells + "0" * CHART_CELLS)[:CHART_CELLS]
    if not isinstance(data.get("opponents"), dict):
        data["opponents"] = {}
    if not isinstance(data.get("order"), list):
        data["order"] = []
    data.pop("filled", None)
    return data


def save_record():
    try:
        os.stat(STATE_DIR)
    except OSError:
        os.mkdir(STATE_DIR)
    temporary = STATE_PATH + ".tmp"
    with open(temporary, "w") as f:
        f.write(json.dumps(record))
    os.rename(temporary, STATE_PATH)


record = load_record()
chart = bytearray(int(value) for value in record["chart"])
new_squares = []
blink_until = 0


def plays_against(badge_id):
    entry = record["opponents"].get(badge_id_hex(badge_id))
    return entry["p"] if entry else 0


def chart_add(won, game_id):
    row = game_id % CHART_ROWS
    cells = [column * CHART_ROWS + row for column in range(CHART_COLS)]
    free = [cell for cell in cells if chart[cell] == EMPTY_SQUARE]
    if free:
        cell = free[random.randrange(len(free))]
        chart[cell] = WON_SQUARE if won else LOST_SQUARE
    elif won:
        losses = [cell for cell in cells if chart[cell] == LOST_SQUARE]
        if not losses:
            return
        cell = losses[random.randrange(len(losses))]
        chart[cell] = WON_SQUARE
    else:
        return
    new_squares.append(cell)
    record["chart"] = "".join(str(value) for value in chart)


def pack_chart(cells):
    data = bytearray(CHART_PACKED)
    for cell in range(CHART_CELLS):
        data[cell >> 2] |= cells[cell] << ((cell & 3) * 2)
    return bytes(data)


def unpack_chart(data):
    cells = bytearray(CHART_CELLS)
    for cell in range(CHART_CELLS):
        cells[cell] = (data[cell >> 2] >> ((cell & 3) * 2)) & 3
    return cells


class ChartView:
    PENS = (PANEL, ui.GREEN_5, ui.GREEN_2)

    def __init__(self, pitch):
        self.pitch = pitch
        self.width = CHART_COLS * pitch - 1
        self.height = CHART_ROWS * pitch - 1
        self.image = image(self.width, self.height)
        self.image.antialias = image.OFF
        self.key = 0

    def origin(self, cell):
        return (cell // CHART_ROWS) * self.pitch, (cell % CHART_ROWS) * self.pitch

    def draw(self, cells, key, x, y, highlight=()):
        if key != self.key:
            self.key = key
            self.image.pen = BACKGROUND
            self.image.clear()
            for cell in range(CHART_CELLS):
                left, top = self.origin(cell)
                self.image.pen = self.PENS[min(2, cells[cell]) if cells else EMPTY_SQUARE]
                self.image.rectangle(left, top, self.pitch - 1, self.pitch - 1)
        screen.blit(self.image, vec2(x, y))
        if highlight:
            screen.pen = BRIGHT
            for cell in highlight:
                left, top = self.origin(cell)
                screen.rectangle(x + left, y + top, self.pitch - 1, self.pitch - 1)


my_view = ChartView(CHART_PITCH)
rival_view = ChartView(CHART_PITCH)
final_view = ChartView(5)

games = None
link = None
mona = None
badge_id_hex = None
draw_identicon = None
effects = ui.Effects()
splash = ui.Splash(random)


def load_steps():
    global games, link, proximity, mona, badge_id_hex, draw_identicon
    import games
    yield
    from badgeware import link as badgelink
    badge_id_hex = badgelink.badge_id_hex
    draw_identicon = badgelink.draw_identicon
    yield
    link = badgelink.Link(GAME_NAME)
    link.journal = recorder.journal
    proximity = badgelink.Proximity(link)
    yield
    mona = ui.Mona()
    yield
    games.load_icons()
    yield


LOAD_STEPS = 5
loader = load_steps()
loaded_steps = 0

outbox = []
phase = Phase.LINKING
phase_at = 0
linked_at = 0
round_done_at = 0
rival_detail = None
round_number = 0
game = None
game_id = 0
start_at = 0
order = []
host_score = None
guest_score = None
round_winner = None
wins = [0, 0]
rtt = None
pings_sent = len(PING_TIMES)
live_at = 0
next_round_at = 0
final_until = 0
earned = 0
new_opponent = False
was_linked = False
glow = 0.0
proximity = None
rival_chart = None
my_accept = False
their_accept = False
my_again = None
their_again = None
practice = False
practice_index = 0
practice_choice = None
menu_cursor = 0
secret = []


def me_index():
    return 0 if link.central else 1


def rival_id():
    return link.partner.id if link.partner else None


def queue(message):
    outbox.append(message)


def flush():
    capacity = link.capacity()
    index = 0
    while index < len(outbox):
        message = outbox[index]
        if len(message) > capacity:
            index += 1
            continue
        if not link.send(message):
            return
        outbox.pop(index)


def set_phase(value, now):
    global phase, phase_at
    if value not in (Phase.INTRO, Phase.PLAY):
        recorder.idle()
    if phase == Phase.PLAY and value != Phase.PLAY:
        badge.autorotate(True)
    if value == Phase.PLAY:
        badge.autorotate(False)
    phase = value
    phase_at = now


def enter_challenge(now):
    global outbox, rival_chart, my_accept, their_accept, glow
    recorder.keep()
    outbox = []
    rival_chart = None
    my_accept = False
    their_accept = False
    glow = LINK_GLOW
    mona.react("heart", now)
    queue(b"H" + pack_chart(chart))
    set_phase(Phase.CHALLENGE, now)


def challenge_frame(now):
    global my_accept
    if badge.pressed(BUTTON_SELECT) and not my_accept:
        my_accept = True
        queue(b"A")
    if my_accept and their_accept:
        start_session(now)
    elif now - phase_at > CHALLENGE_MS:
        part_ways(now)


def part_ways(now):
    proximity.rest(rival_id(), now)
    link.leave()


def start_session(now):
    global round_number, game, order, wins, rtt, pings_sent, linked_at, next_round_at, host_score, guest_score
    global my_again, their_again
    round_number = 0
    game = None
    order = list(range(len(games.GAMES)))
    for index in range(len(order) - 1, 0, -1):
        swap = random.randint(0, index)
        order[index], order[swap] = order[swap], order[index]
    wins = [0, 0]
    new_squares[:] = []
    rtt = None
    pings_sent = 0
    linked_at = now
    next_round_at = now + FIRST_ROUND_MS
    host_score = None
    guest_score = None
    my_again = None
    their_again = None
    set_phase(Phase.LINKING, now)


def result_duration():
    return REVEAL_RESULT_MS if game is not None and game.REVEAL else RESULT_MS


def begin_round(chosen, seed, when, now):
    global game, game_id, start_at, host_score, guest_score, round_winner, rival_detail
    rival_detail = None
    game_id = chosen
    game = games.GAMES[chosen](seed, link.id, rival_id() or link.id)
    start_at = when
    host_score = None
    guest_score = None
    round_winner = None
    mona.react("code", now, INTRO_MS)
    set_phase(Phase.INTRO, now)


def host_next_round(now):
    global round_number
    if round_number >= ROUNDS:
        queue(b"E" + bytes((wins[0], wins[1])))
        enter_final(now)
        return
    round_number += 1
    chosen = order[(round_number - 1) % len(order)]
    seed = random.getrandbits(30)
    queue(b"G" + struct.pack("<BBIH", round_number, chosen, seed, INTRO_MS))
    begin_round(chosen, seed, now + INTRO_MS, now)


def record_round(winner):
    if winner == games.TIE:
        wins[0] += 1
        wins[1] += 1
        chart_add(True, game_id)
    else:
        wins[winner] += 1
        chart_add(winner == me_index(), game_id)


def resolve(now, forfeit=False):
    global round_winner, next_round_at, guest_score
    if forfeit:
        round_winner = games.HOST_WINS
        guest_score = games.NO_SCORE
    else:
        round_winner = game.compare(host_score, guest_score)
    record_round(round_winner)
    queue(b"W" + struct.pack("<BBHH", round_number, round_winner, host_score, guest_score) + game.detail())
    show_result(now)
    next_round_at = now + result_duration()


def show_result(now):
    global glow
    set_phase(Phase.RESULT, now)
    if round_winner == games.TIE:
        mona.react("heart", now)
    elif round_winner == me_index():
        glow = LINK_GLOW
        mona.react("dance", now)
    else:
        effects.oops(now, 500)
        mona.react("eating", now)


def match_outcome():
    mine, theirs = wins[me_index()], wins[1 - me_index()]
    if mine == theirs:
        return "draw"
    return "won" if mine > theirs else "lost"


def enter_final(now):
    global final_until, earned, new_opponent
    set_phase(Phase.FINAL, now)
    final_until = now + FINAL_MS
    outcome = match_outcome()
    mona.react("dead" if outcome == "lost" else "dance", now, FINAL_MS)

    partner = rival_id()
    key = badge_id_hex(partner) if partner else "unknown"
    entry = record["opponents"].get(key)
    new_opponent = entry is None
    if entry is None:
        entry = {"n": link.partner.name if link.partner else "?", "p": 0, "w": 0, "l": 0, "t": 0}
        record["opponents"][key] = entry
        record["order"].append(key)
    base = POINTS_LOSS if outcome == "lost" else POINTS_WIN
    earned = max(1, base >> entry["p"])
    entry["p"] += 1
    if outcome == "lost":
        entry["l"] += 1
    else:
        entry["w"] += 1
        if outcome == "draw":
            entry["t"] += 1
    record["points"] += earned
    save_record()


def again_frame(now):
    global my_again
    if my_again is None:
        if badge.pressed(BUTTON_LEFT):
            my_again = True
            queue(b"R")
        elif badge.pressed(BUTTON_SELECT):
            my_again = False
            queue(b"N")
    if my_again is False or their_again is False or now - phase_at > AGAIN_MS:
        flush()
        part_ways(now)
    elif my_again and their_again:
        start_session(now)


def handle(message, now):
    global rtt, guest_score, round_winner, round_number, next_round_at, rival_chart, their_accept, their_again, rival_detail
    kind = message[:1]
    body = message[1:]

    if kind == b"H" and len(body) == CHART_PACKED:
        rival_chart = unpack_chart(body)
    elif kind == b"A":
        their_accept = True
    elif kind == b"R":
        their_again = True
    elif kind == b"N":
        their_again = False
    elif kind == b"P" and len(body) == 4:
        queue(b"Q" + body)
    elif kind == b"Q" and len(body) == 4:
        sample = (now - struct.unpack("<I", body)[0]) & 0xFFFFFFFF
        rtt = sample if rtt is None else min(rtt, sample)
    elif kind == b"G" and len(body) == 8 and not link.central:
        number, chosen, seed, delay = struct.unpack("<BBIH", body)
        if chosen < len(games.GAMES):
            round_number = number
            begin_round(chosen, seed, now + delay - (rtt or 0) // 2, now)
    elif kind == b"Z" and len(body) >= 3 and link.central:
        number, score = struct.unpack_from("<BH", body)
        if number == round_number and guest_score is None and phase in (Phase.INTRO, Phase.PLAY, Phase.WAIT):
            guest_score = score
            rival_detail = bytes(body[3:])
    elif kind == b"W" and len(body) >= 6 and not link.central:
        number, winner, host, guest = struct.unpack_from("<BBHH", body)
        if number == round_number and winner <= games.TIE:
            round_winner = winner
            rival_detail = bytes(body[6:])
            record_round(winner)
            if game is not None:
                game.score = guest
                game.rival_score = host
            show_result(now)
    elif kind == b"E" and len(body) == 2 and not link.central:
        wins[0], wins[1] = body[0], body[1]
        enter_final(now)
    elif kind == b"C" and len(body) == 2 and game is not None:
        game.rival_live = struct.unpack("<H", body)[0]


def host_frame(now):
    if phase in (Phase.LINKING, Phase.RESULT) and now >= next_round_at and order:
        host_next_round(now)
    if phase == Phase.WAIT and host_score is not None:
        if guest_score is not None:
            resolve(now)
        elif now - phase_at > SCORE_WAIT_MS:
            resolve(now, True)


def guest_frame(now):
    global pings_sent
    if pings_sent < len(PING_TIMES) and now - linked_at >= PING_TIMES[pings_sent]:
        pings_sent += 1
        queue(b"P" + struct.pack("<I", now & 0xFFFFFFFF))


def play_frame(now):
    global host_score, live_at, round_done_at
    if phase == Phase.INTRO and now >= start_at:
        game.start(now)
        set_phase(Phase.PLAY, now)
    if phase != Phase.PLAY:
        return
    if not game.done:
        game.update(now)
        if game.oops_pending:
            game.oops_pending = False
            effects.oops(now)
            mona.react("eating", now)
        if hasattr(game, "live") and now - live_at >= LIVE_MS:
            live_at = now
            link.send(b"C" + struct.pack("<H", game.live()))
        if game.done:
            round_done_at = now
        return
    if now - round_done_at >= game.HOLD_MS:
        if practice:
            mona.react("dance", now)
            set_phase(Phase.RESULT, now)
            return
        if link.central:
            host_score = game.score
        else:
            queue(b"Z" + struct.pack("<BH", round_number, game.score) + game.detail())
        set_phase(Phase.WAIT, now)


def watch_secret(now):
    for action in (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT):
        if badge.pressed(action):
            secret.append((action, now))
    del secret[:max(0, len(secret) - len(PRACTICE_CODE))]
    if tuple(action for action, _at in secret) == PRACTICE_CODE and now - secret[0][1] <= PRACTICE_CODE_MS:
        secret.clear()
        return True
    return False


def next_practice(now):
    global practice_index
    chosen = practice_index % len(games.GAMES) if practice_choice is None else practice_choice
    practice_index += 1
    begin_round(chosen, random.getrandbits(30), now + INTRO_MS, now)


def start_practice(now):
    global practice
    recorder.keep()
    practice = True
    proximity.clear()
    set_phase(Phase.MENU, now)


def stop_practice(now):
    global practice
    practice = False
    set_phase(Phase.LINKING, now)


def menu_entries():
    return ["all games"] + [game_class.NAME.lower() for game_class in games.GAMES]


def menu_frame(now):
    global menu_cursor, practice_choice, practice_index
    count = len(games.GAMES) + 1
    if badge.pressed(BUTTON_UP):
        menu_cursor = (menu_cursor - 1) % count
    if badge.pressed(BUTTON_DOWN):
        menu_cursor = (menu_cursor + 1) % count
    if badge.pressed(BUTTON_LEFT):
        stop_practice(now)
    elif badge.pressed(BUTTON_SELECT):
        practice_choice = None if menu_cursor == 0 else menu_cursor - 1
        practice_index = 0
        next_practice(now)


def practice_frame(now):
    if badge.buttons.pressed(BUTTON_HOME):
        stop_practice(now)
        return
    if phase == Phase.MENU:
        menu_frame(now)
        return
    if phase == Phase.RESULT:
        if now - phase_at >= MENU_RESULT_GUARD_MS and badge.pressed(BUTTON_LEFT):
            set_phase(Phase.MENU, now)
            return
        if now - phase_at >= result_duration():
            next_practice(now)
            return
    play_frame(now)


def draw_hint_labels(controls, cy, pen):
    upside_down = ui.flipped()
    shape = ui.actions_for(controls, upside_down)
    radius = 5
    widget_w = ui.hint_width(shape, radius, upside_down)
    screen.font = SMALL
    shown = [control for control in controls if control.actions(upside_down)]
    widths = [widget_w + 6 + screen.measure_text(control.label)[0] for control in shown]
    gap = 14
    x = (ui.MONA_LEFT - sum(widths) - gap * (len(widths) - 1)) / 2
    for control, width in zip(shown, widths):
        ui.draw_hint(shape, control.actions(upside_down), x + widget_w / 2, cy, radius, upside_down)
        _w, text_h = screen.measure_text(control.label)
        ui.text_at(control.label, x + widget_w + 6, cy - text_h / 2, SMALL, pen)
        x += width + gap


def draw_menu(now):
    ui.clear()
    ui.text_at("practice", 14, 8, LARGE, BRIGHT)
    entries = menu_entries()
    top = max(0, min(menu_cursor - MENU_VISIBLE // 2, len(entries) - MENU_VISIBLE))
    for slot, index in enumerate(range(top, min(len(entries), top + MENU_VISIBLE))):
        y = MENU_TOP + slot * MENU_ROW
        selected = index == menu_cursor
        if selected:
            screen.pen = ACCENT
            screen.rectangle(8, y - 2, MENU_WIDTH, MENU_ROW - 2)
        ui.text_at(entries[index], 16, y, SMALL, BACKGROUND if selected else TEXT)
    draw_hint_row(MENU_CONTROLS, MENU_HINT_CY, TEXT)


def draw_hint_row(controls, cy, pen):
    upside_down = ui.flipped()
    shape = ui.actions_for(controls, upside_down)
    shown = ui.active_controls(controls, upside_down)
    radius = MENU_HINT_RADIUS
    height = ui.hint_height(shape, radius, upside_down)
    slot = ui.MONA_LEFT / len(shown)
    screen.font = SMALL
    for index, control in enumerate(shown):
        cx = slot * index + slot / 2
        ui.draw_hint(shape, control.actions(upside_down), cx, cy, radius, upside_down)
        text_w, _text_h = screen.measure_text(control.label)
        ui.text_at(control.label, cx - text_w / 2, cy + height / 2 + 3, SMALL, pen)


def draw_practice_result():
    ui.clear()
    if game.REVEAL:
        centred(game.describe(game.score), REVEAL_HEADLINE_Y, LARGE, BRIGHT)
        game.draw_reveal(game.detail(), None, REVEAL_TOP)
        draw_tally()
        return
    centred(game.NAME, 30, SMALL, DIM)
    centred(game.describe(game.score), 70, BIG, BRIGHT)
    centred("practice", 120, SMALL, DIM)
    draw_hint_labels(MENU_RESULT_CONTROLS, 158, DIM)
    draw_tally()


def draw_header(now):
    draw_identicon(screen, link.id, HEADER_X, HEADER_Y, HEADER_ICON, BRIGHT, PANEL)
    ui.text_at(link.name, HEADER_NAME_X, HEADER_Y, LARGE, BRIGHT)
    highlight = new_squares if now < blink_until and int(now / 300) % 2 else ()
    my_view.draw(chart, record["chart"], CHART_X, HEADER_CHART_Y, highlight)


def draw_card(badge_id, name, cells, key, y):
    draw_identicon(screen, badge_id, HEADER_X, y, CARD_ICON, RIVAL, PANEL)
    name_w = ui.text_at(name, CARD_NAME_X, y - 1, SMALL, RIVAL)
    plays = plays_against(badge_id)
    label = "new" if plays == 0 else "played %dx" % plays
    screen.font = SMALL
    w, _h = screen.measure_text(label)
    right = screen.width - HEADER_X
    if CARD_NAME_X + name_w + 10 + w > right:
        label = "new" if plays == 0 else "%dx" % plays
        w, _h = screen.measure_text(label)
    ui.text_at(label, right - w, y - 1, SMALL, ACCENT if plays == 0 else DIM)
    rival_view.draw(cells, key, CHART_X, y + CARD_CHART_OFFSET)


def draw_prompt(controls, text, pen, cy):
    upside_down = ui.flipped()
    shape = ui.actions_for(controls, upside_down)
    radius = 5
    screen.font = SMALL
    text_w, text_h = screen.measure_text(text)
    widget_w = ui.hint_width(shape, radius, upside_down)
    left = (ui.MONA_LEFT - widget_w - 12 - text_w) / 2
    ui.draw_hint(shape, shape, left + widget_w / 2, cy, radius, upside_down)
    ui.text_at(text, left + widget_w + 12, cy - text_h / 2, SMALL, pen)


def draw_lobby(now):
    ui.clear()
    draw_header(now)
    peer = proximity.syncing()
    remaining = proximity.cooling(now)
    if peer is None and remaining is not None:
        centred("ready again in %ds" % ((remaining + 999) // 1000), 98, BIG, TEXT)
        width = screen.width - HEADER_X * 2
        screen.pen = PANEL
        screen.rectangle(HEADER_X, 132, width, 6)
        screen.pen = DIM
        screen.rectangle(HEADER_X, 132, int(width * remaining / proximity.cooldown_ms), 6)
        centred("or pull apart and try again", 146, SMALL, DIM)
        return
    if peer is None:
        screen.antialias = image.X2
        pairing.draw_loop(now)
        screen.antialias = image.OFF
        centred("hold badges", PAIRING_TEXT_Y, LARGE, TEXT)
        centred("back to back", PAIRING_TEXT_Y + 22, LARGE, TEXT)
        return
    progress = proximity.progress(now)
    centred("connecting..." if progress >= 1.0 else "syncing", 84, SMALL, TEXT)
    screen.pen = PANEL
    screen.rectangle(HEADER_X, 106, screen.width - HEADER_X * 2, 10)
    screen.pen = ACCENT
    screen.rectangle(HEADER_X, 106, int((screen.width - HEADER_X * 2) * progress), 10)
    draw_card(peer.id, peer.name, None, None, SYNC_CARD_Y)


def draw_challenge(now):
    ui.clear()
    draw_header(now)
    centred("CHALLENGE", 86, BIG, ACCENT if int(now / 400) % 2 else BRIGHT)
    partner = link.partner
    if partner is not None:
        key = bytes(rival_chart) if rival_chart else None
        draw_card(partner.id, partner.name, rival_chart, key, CHALLENGE_CARD_Y)
    if my_accept:
        centred("waiting for them...", 192, SMALL, DIM)
    else:
        text, pen = ("they're in!", ACCENT) if their_accept else ("to accept", TEXT)
        draw_prompt(ACCEPT_CONTROLS, text, pen, 204)
    ui.timer_bar(now, phase_at, CHALLENGE_MS, screen.height - 4)


def draw_tally():
    if practice:
        draw_identicon(screen, link.id, ui.HINT_X, ui.STRIP_CY - TALLY_ICON // 2, TALLY_ICON, BRIGHT, PANEL)
        label = "practice %d/%d" % (practice_index, len(games.GAMES)) if practice_choice is None else "practice #%d" % practice_index
        ui.text_at(label, ui.HINT_X + TALLY_ICON + 10, ui.STRIP_CY - 10, SMALL, TEXT)
        return
    partner = rival_id()
    draw_identicon(screen, link.id, ui.HINT_X, ui.STRIP_CY - TALLY_ICON // 2, TALLY_ICON, BRIGHT, PANEL)
    x = ui.HINT_X + TALLY_ICON + 10
    score = "%d - %d" % (wins[me_index()], wins[1 - me_index()])
    w = ui.text_at(score, x, ui.STRIP_CY - 12, LARGE, TEXT)
    if partner is not None:
        draw_identicon(screen, partner, x + w + 10, ui.STRIP_CY - TALLY_ICON // 2, TALLY_ICON, RIVAL, PANEL)


def draw_intro(now):
    ui.clear()
    left = max(0, start_at - now)
    count = max(1, (left + COUNT_STEP_MS - 1) // COUNT_STEP_MS)
    centred("%d" % count, 2, BIG, ACCENT, 2)
    centred(game.NAME, 62, LARGE, BRIGHT)
    centred(game.HINT, 88, SMALL, TEXT)
    ui.draw_primer(game.CONTROLS, PRIMER_TOP, now, game.TILT_TEXT)
    draw_tally()


def draw_play(now):
    game.draw(now)
    if game.SHOW_HINT:
        ui.draw_controls_hint(game.CONTROLS, now)


def draw_wait():
    ui.clear()
    centred(game.NAME, 30, SMALL, DIM)
    centred(game.describe(game.score), 70, BIG, BRIGHT)
    centred("waiting for them...", 120, SMALL, DIM)
    draw_tally()


def draw_result():
    ui.clear()
    if round_winner == games.TIE:
        headline, pen = "It's a draw!", TEXT
    elif round_winner == me_index():
        headline, pen = "You win!", ACCENT
    else:
        headline, pen = "They win!", RIVAL
    if game.REVEAL:
        centred(headline, REVEAL_HEADLINE_Y, LARGE, pen)
        game.draw_reveal(game.detail(), rival_detail, REVEAL_TOP)
        draw_tally()
        return
    centred(game.NAME, 12, SMALL, DIM)
    centred(headline, 44, BIG, pen)
    mine = host_score if link.central else game.score
    theirs = guest_score if link.central else getattr(game, "rival_score", None)
    centred("you  " + game.describe(mine), 100, SMALL, BRIGHT)
    if theirs is not None:
        centred("them  " + game.describe(theirs), 128, SMALL, RIVAL)
    draw_tally()


def draw_final(now):
    ui.clear()
    outcome = match_outcome()
    headline, pen = {"won": ("YOU WIN", ACCENT), "lost": ("THEY WIN", RIVAL), "draw": ("YOU BOTH WIN", TEXT)}[outcome]
    centred(headline, 8, BIG, pen)
    centred("%d - %d" % (wins[me_index()], wins[1 - me_index()]), 46, LARGE, TEXT)
    centred("+%d points" % earned, 80, SMALL, TEXT)
    if new_opponent:
        centred("new opponent!", 104, SMALL, ACCENT)
    highlight = new_squares if int(now / 300) % 2 else ()
    final_view.draw(chart, record["chart"], (screen.width - final_view.width) // 2, 134, highlight)


def draw_again(now):
    ui.clear()
    centred("rematch?", 14, LARGE, TEXT)
    upside_down = ui.flipped()
    shape = ui.actions_for(AGAIN_CONTROLS, upside_down)
    for index, control in enumerate(AGAIN_CONTROLS):
        box_w = (screen.width - 30) // 2
        x = 10 + index * (box_w + 10)
        chosen = my_again is not None and my_again == (index == 0)
        screen.pen = ACCENT if chosen else PANEL
        screen.rectangle(x, 52, box_w, 70)
        screen.font = SMALL
        w, h = screen.measure_text(control.label)
        ui.text_at(control.label, x + (box_w - w) / 2, 52 + (70 - h) / 2, SMALL, BACKGROUND if chosen else BRIGHT)
        ui.draw_hint(shape, control.actions(upside_down), x + box_w / 2, 146, 6, upside_down)
    if their_again:
        centred("they want a rematch!", 166, SMALL, ACCENT)
    elif my_again:
        centred("waiting for them...", 166, SMALL, DIM)
    ui.timer_bar(now, phase_at, AGAIN_MS, ui.STRIP_Y - 2)


def draw(now):
    if phase == Phase.MENU:
        draw_menu(now)
    elif practice and phase == Phase.RESULT:
        draw_practice_result()
    elif phase == Phase.CHALLENGE:
        draw_challenge(now)
    elif phase == Phase.LINKING:
        ui.clear()
        centred("get ready...", 90, LARGE, TEXT)
        draw_tally()
    elif phase == Phase.INTRO:
        draw_intro(now)
    elif phase == Phase.PLAY:
        draw_play(now)
    elif phase == Phase.WAIT:
        draw_wait()
    elif phase == Phase.RESULT:
        draw_result()
    elif phase == Phase.FINAL:
        draw_final(now)
    elif phase == Phase.AGAIN:
        draw_again(now)


def splash_frame(now):
    global splash, loaded_steps
    if splash.started is None:
        splash.start(now)
    elif loaded_steps < LOAD_STEPS:
        next(loader)
        loaded_steps += 1
    splash.update(now, loaded_steps / LOAD_STEPS)
    for _word in splash.smashes(now):
        effects.oops(now, SPLASH_GLITCH_MS)
    if loaded_steps == LOAD_STEPS and (splash.done(now) or badge.pressed()):
        splash = None
        return False
    splash.draw(now)
    effects.apply(now)
    return True


def update():
    global was_linked, glow, blink_until

    now = badge.ticks
    if splash is not None and splash_frame(now):
        return
    link.pump()
    linked = link.linked

    if linked and not was_linked:
        enter_challenge(now)
    if was_linked and not linked:
        proximity.rest(rival_id(), now)
        proximity.clear()
        if phase in (Phase.FINAL, Phase.AGAIN):
            blink_until = now + CHART_BLINK_MS
        else:
            save_record()
        set_phase(Phase.LINKING, now)
    was_linked = linked

    if linked:
        for message in link.receive():
            handle(message, now)
        if phase == Phase.CHALLENGE:
            challenge_frame(now)
        elif phase == Phase.AGAIN:
            again_frame(now)
        elif link.central:
            host_frame(now)
        else:
            guest_frame(now)
        if phase == Phase.FINAL and now >= final_until:
            set_phase(Phase.AGAIN, now)
        play_frame(now)
        flush()
        link.update()
        draw(now)
        if phase == Phase.PLAY and hasattr(game, "lights"):
            glow = max(glow, game.lights(now))
        mona.set_mood("default")
    elif practice:
        practice_frame(now)
        draw(now)
        mona.set_mood("default")
    else:
        if PRACTICE_ENABLED and watch_secret(now):
            start_practice(now)
            draw(now)
        else:
            recorder.idle()
            proximity.update(now)
            draw_lobby(now)
        mona.set_mood("notify" if proximity.sync_id else "default")

    if not (phase == Phase.PLAY and game is not None and game.hides_mona()):
        mona.draw(now)
    effects.apply(now)

    glow *= 0.85
    lights = None if linked else proximity.lights(now)
    if lights is None:
        badge.caselights(min(1.0, glow))
    else:
        badge.caselights(*(max(level, glow) for level in lights))


def on_exit():
    badge.caselights(0)
    badge.autorotate(True)
    try:
        save_record()
    except OSError:
        pass
    if link is not None:
        link.close()
    recorder.close()


def home_pressed(_pin):
    if practice:
        return
    on_exit()
    reset()


machine.Pin.board.BUTTON_HOME.irq(trigger=machine.Pin.IRQ_FALLING, handler=home_pressed)

run(update)
