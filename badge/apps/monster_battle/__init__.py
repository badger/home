"""An original pocket-sized elemental battle."""

import math
import os
import random
import sys


APP_DIR = "/system/apps/monster_battle"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from monster_rules import Battle, CREATURES, move_name


badge.mode(HIRES | VSYNC)
screen.font = font.nope
screen.antialias = image.OFF
screen.fill_rule = image.EVEN_ODD

INK = color.rgb(24, 35, 51)
NIGHT = color.rgb(17, 26, 43)
PANEL = color.rgb(32, 46, 65)
MUTED = color.rgb(166, 188, 201)
WHITE = color.rgb(246, 248, 232)
GOLD = color.rgb(255, 213, 102)
SKY = color.rgb(197, 230, 222)
GROUND = color.rgb(155, 201, 168)
SHADOW = color.rgb(110, 169, 148)
GREEN = color.rgb(89, 205, 124)
RED = color.rgb(242, 105, 99)
ACCENTS = tuple(color.rgb(*creature[3]) for creature in CREATURES)

# Original 16x16 portraits: a lightning dragon, a water spirit, and a sky seer.
ART = (
    (
        "....a....a......",
        "...aba..aba.....",
        "...abaaaaba.....",
        "....abbbba......",
        "a..abdbbdba..a..",
        "aa.abbbbbba.aa..",
        "aba.abbba..aba..",
        "abbaaacaaabbba..",
        ".abbabcabbbba...",
        "..aaabcaabaa....",
        "....abccba...a..",
        "....abcbba..aba.",
        "...aabbbbaaaaba.",
        "..abbaaabbbbaa..",
        "...aa...aaaa....",
        "................",
    ),
    (
        ".......aa.......",
        "......abba......",
        ".....abccba.....",
        "....abccccba....",
        "...abccccccba...",
        "..abccccccccba..",
        "..abcdbbdcbcba..",
        "..abcdbbdcbcba..",
        "..abccccccccba..",
        "...abceecbcba...",
        "....abccccba....",
        "...abccccccba...",
        "..abcbaabcabca..",
        "...aa....aa.aa..",
        ".....a..........",
        "................",
    ),
    (
        "......aa........",
        ".....acba.......",
        "......aa........",
        ".....abbba......",
        "a...abbbbba...a.",
        "aa..abdbdba..aa.",
        "aca.abbbbba.aca.",
        "accaaabbaaaccca.",
        ".accbaccabcca...",
        "..acbaccabca....",
        "...abaccaba.....",
        "....abccba......",
        ".....abba.......",
        "....abbbba......",
        "...aa.aa.aa.....",
        "................",
    ),
)


def build_pixels(art, accent):
    palette = {"a": INK, "b": accent, "c": WHITE, "d": INK, "e": WHITE}
    return tuple(
        (x, y, palette[pixel])
        for y, row in enumerate(art)
        for x, pixel in enumerate(row)
        if pixel != "."
    )


SPRITES = tuple(build_pixels(art, accent) for art, accent in zip(ART, ACCENTS))

GAME = "pocket_rivals"

selected_creature = 0
selected_mode = 0
selected_move = 0
mode = "cpu"
battle = None
duel = None
badgelink = None
phase = "choose"
me = 0
queue = []
shown_hp = [0, 0]
event = None
event_age = 0
actor = 0
seen_battle = 0
animation_ms = 0
notice = ""
notice_ms = 0


def box(x, y, width, height, pen):
    screen.pen = pen
    screen.rectangle(int(x), int(y), int(width), int(height))


def text(label, x, y, pen=WHITE):
    screen.pen = pen
    screen.text(label, int(x), int(y))


def centre(label, y, pen=WHITE, x=None):
    width = screen.measure_text(label)[0]
    text(label, (screen.width if x is None else x * 2) / 2 - width / 2, y, pen)


def sprite(creature, x, y, scale=3, mirror=False, flash=False):
    for px, py, pen in SPRITES[creature]:
        if mirror:
            px = 15 - px
        box(x + px * scale, y + py * scale, scale, scale, WHITE if flash else pen)


def show_battle(new_battle, who):
    global battle, me, queue, shown_hp, event, phase, selected_move, notice_ms
    battle = new_battle
    me = who
    queue = []
    shown_hp = list(battle.hp)
    event = None
    phase = "moves"
    selected_move = 0
    notice_ms = 0


def start_cpu_battle():
    opponent = (selected_creature + random.randint(1, 2)) % len(CREATURES)
    show_battle(Battle(selected_creature, opponent), 0)


def cpu_turn(move):
    queue.append((0, battle.act(0, move), tuple(battle.hp)))
    if battle.winner() is None:
        queue.append((1, battle.act(1, battle.enemy_move()), tuple(battle.hp)))


def outcome():
    if shown_hp[me] == 0:
        return "lost"
    if shown_hp[1 - me] == 0:
        return "won"
    return None


def next_event():
    global actor, event, shown_hp, event_age, phase
    actor, event, hp = queue.pop(0)
    if actor != me:
        event = ("Rival " + event[0],) + tuple(event[1:])
    shown_hp = list(hp)
    event_age = 0
    phase = "resolve"


def finish_event():
    global phase, event
    if queue:
        next_event()
        return
    event = None
    if outcome():
        phase = "result"
    elif mode == "link" and duel.waiting():
        phase = "waiting"
    else:
        phase = "moves"


def open_link():
    global duel, badgelink, mode, phase, seen_battle, notice, notice_ms
    try:
        from badgeware import link as module
        from duel import Duel
        connection = module.Link(GAME)
        duel = Duel(connection, module.Proximity(connection), selected_creature)
    except (ImportError, AttributeError, OSError):
        notice = "Badge link needs newer firmware."
        notice_ms = 2400
        return
    badgelink = module
    mode = "link"
    phase = "lobby"
    seen_battle = 0


def close_link():
    global duel, mode, phase
    if duel:
        duel.close()
    duel = None
    badge.caselights(0)
    mode = "cpu"
    phase = "choose"


def sync_link(now):
    global phase, seen_battle
    duel.update(now)
    if duel.battle is not None and duel.battle_id != seen_battle:
        seen_battle = duel.battle_id
        show_battle(duel.battle, duel.me)
    queue.extend(duel.take_events())
    if duel.state == "lobby" and phase != "lobby":
        phase = "lobby"
    elif duel.state == "offer" and phase != "offer":
        phase = "offer"
    if duel.state == "lobby":
        lights = duel.proximity.lights(now)
        if lights is None:
            badge.caselights(0)
        else:
            badge.caselights(*lights)
    else:
        badge.caselights(0)


def draw_choice():
    centre("POCKET RIVALS", 13, GOLD)
    centre("Choose your creature", 37, MUTED)
    card_width = (screen.width - 20) // 3
    for index, (name, elements, hp, _) in enumerate(CREATURES):
        x = 6 + index * card_width
        chosen = index == selected_creature
        box(x, 62, card_width - 4, 125, ACCENTS[index] if chosen else PANEL)
        box(x + 2, 64, card_width - 8, 121, PANEL)
        mid = x + (card_width - 4) / 2
        bob = math.sin(animation_ms / 320 + index) * 2
        sprite(index, mid - 24, 77 + bob)
        centre(name, 132, WHITE, mid)
        centre(elements[0], 148, ACCENTS[index], mid)
        centre(elements[1], 161, ACCENTS[index], mid)
        centre("%d HP" % hp, 174, MUTED, mid)
    label = ("VS COMPUTER", "VS ANOTHER BADGE")[selected_mode]
    centre("^  " + label + "  v", 198, WHITE)
    if notice_ms > 0:
        centre(notice, 219, RED)
    else:
        centre("L/R creature  U/D mode  SELECT go", 219, GOLD)


def draw_badges(now):
    gap = 34 + math.sin(now / 400) * 22
    peer = duel.proximity.syncing()
    if peer is not None:
        gap = 6
    elif duel.proximity.cooling(now) is not None:
        gap = 60
    for side in (-1, 1):
        x = screen.width / 2 + side * (gap / 2 + 24) - 24
        box(x, 110, 48, 64, ACCENTS[selected_creature] if side < 0 else PANEL)
        box(x + 5, 116, 38, 30, INK)


def draw_lobby(now):
    centre("BADGE BATTLE", 13, GOLD)
    sprite(selected_creature, 20, 40)
    text(CREATURES[selected_creature][0], 80, 50, WHITE)
    text("/".join(CREATURES[selected_creature][1]), 80, 66, ACCENTS[selected_creature])
    text("LEFT/RIGHT to change", 80, 82, MUTED)
    draw_badges(now)
    peer = duel.proximity.syncing()
    if peer is not None:
        progress = duel.proximity.progress(now)
        centre("Connecting..." if progress >= 1 else "Syncing with " + peer.name, 186, WHITE)
        box(60, 203, 200, 6, PANEL)
        box(60, 203, 200 * min(1, progress), 6, GOLD)
    elif duel.proximity.cooling(now) is not None:
        centre("Pull apart to battle again", 186, WHITE)
    else:
        centre("Hold badges back to back", 186, WHITE)
    if duel.message:
        centre(duel.message, 203, RED)
    centre("UP returns to creature choice", 224, MUTED)


def draw_offer(now):
    centre("CHALLENGER!", 13, GOLD)
    partner = duel.link.partner
    if partner is not None and badgelink is not None:
        badgelink.draw_identicon(screen, partner.id, 20, 40, 56)
    text(duel.partner_name, 88, 44, WHITE)
    if duel.their_creature is None:
        text("Choosing a creature...", 88, 62, MUTED)
    else:
        name, elements, hp, _ = CREATURES[duel.their_creature]
        text("brings " + name, 88, 62, ACCENTS[duel.their_creature])
        text("/".join(elements) + "  %d HP" % hp, 88, 78, MUTED)
        sprite(duel.their_creature, 196, 104, mirror=False)
    sprite(selected_creature, 76, 104, mirror=True)
    centre("VS", 128, GOLD)
    if duel.my_accept:
        status = "Waiting for rival..."
    elif duel.their_accept:
        status = "Rival is ready to battle!"
    else:
        status = "Battle this badge?"
    centre(status, 172, GOLD if duel.their_accept else WHITE)
    remaining = max(0, 20000 - (now - duel.state_at))
    box(60, 192, 200 * remaining / 20000, 4, MUTED)
    centre("SELECT accept   BACK decline", 214, WHITE)


def health_panel(who, x, y):
    creature = battle.creatures[who]
    name, elements, maximum, _ = CREATURES[creature]
    hp = shown_hp[who]
    box(x, y, 147, 42, WHITE)
    text(name, x + 5, y + 3, INK)
    label = "%d/%d" % (hp, maximum)
    text(label, x + 141 - screen.measure_text(label)[0], y + 3, INK)
    text("/".join(elements), x + 5, y + 16, INK)
    box(x + 5, y + 31, 137, 6, INK)
    hp_color = GREEN if hp > maximum // 2 else GOLD
    if hp <= maximum // 4:
        hp_color = RED
    box(x + 6, y + 32, 135 * hp / maximum, 4, hp_color)


def draw_arena():
    box(0, 30, screen.width, 140, SKY)
    box(0, 113, screen.width, 57, GROUND)
    box(208, 103, 87, 7, SHADOW)
    box(16, 157, 93, 7, SHADOW)
    centre("POCKET RIVALS" if mode == "cpu" else "VS " + duel.partner_name, 9, GOLD)
    health_panel(1 - me, 10, 40)
    health_panel(me, screen.width - 157, 124)
    for who, x, y in ((me, 30, 106), (1 - me, 226, 57)):
        bob = math.sin(animation_ms / 350 + who * 2) * 2
        flash = False
        if phase == "resolve" and event:
            if who == actor and event_age < 220 and event[3] != "heal":
                x += math.sin(event_age / 220 * math.pi) * (12 if who == me else -12)
            if who == event[2] and event[3] == "hit" and event_age < 450:
                x += math.sin(event_age / 24) * 3
                flash = int(event_age / 80) % 2 == 0
            if who == event[2] and event[3] == "heal" and event_age < 700:
                text("+", x + 47, y - event_age / 35, GREEN)
        if shown_hp[who] > 0 or phase == "resolve":
            sprite(battle.creatures[who], x, y + bob, mirror=who == me, flash=flash)


def move_hint():
    creature = battle.creatures[me]
    if selected_move == 0:
        return "15 power  /  always hits"
    if selected_move == 1:
        return "19 power / " + CREATURES[creature][1][0] + " / 100%"
    if selected_move == 2:
        return "28 power / " + CREATURES[creature][1][1] + " / 75%"
    return "Recover 28 HP  /  %d left" % battle.mends[me]


def draw_moves():
    cell_width = (screen.width - 16) // 2
    for index in range(4):
        x = 6 + index % 2 * (cell_width + 4)
        y = 175 + index // 2 * 23
        chosen = index == selected_move
        box(x, y, cell_width, 21, GOLD if chosen else PANEL)
        label = move_name(battle.creatures[me], index)
        if index == 3:
            label += " x%d" % battle.mends[me]
        pen = INK if chosen else WHITE
        if not battle.available(me, index):
            pen = RED
        text(("> " if chosen else "  ") + label, x + 4, y + 5, pen)
    centre(notice if notice_ms > 0 else move_hint(), 224, MUTED)


def draw_waiting():
    dots = "." * (1 + animation_ms // 400 % 3)
    centre(move_name(battle.creatures[me], selected_move) + " is ready!", 184, GOLD)
    centre("Waiting for rival" + dots, 204, WHITE)
    centre("BACK leaves the battle", 224, MUTED)


def draw_event():
    text(event[0], 10, 181, GOLD)
    text(event[1], 10, 201, WHITE)
    centre("SELECT to continue", 224, MUTED)


def draw_result():
    won = outcome() == "won"
    centre("VICTORY!" if won else "DEFEAT - TRY AGAIN!", 179, GOLD if won else RED)
    if mode == "cpu":
        centre("SELECT rematch   UP choose", 202, WHITE)
        centre("HOME returns to the badge menu", 224, MUTED)
        return
    if duel.my_again:
        status = "Waiting for rival..."
    elif duel.their_again:
        status = "Rival wants a rematch!"
    else:
        status = "SELECT rematch   UP leave"
    centre(status, 202, WHITE)
    centre("Rematches pick a fresh seed", 224, MUTED)


def update():
    global selected_creature, selected_mode, selected_move, phase, animation_ms
    global event_age, notice, notice_ms
    dt = max(0, badge.ticks_delta)
    now = badge.ticks
    animation_ms = (animation_ms + dt) % 100000
    notice_ms = max(0, notice_ms - dt)
    box(0, 0, screen.width, screen.height, NIGHT)

    if mode == "link":
        sync_link(now)
        if phase in ("moves", "waiting") and queue:
            next_event()

    if phase == "choose":
        if badge.pressed(BUTTON_LEFT):
            selected_creature = (selected_creature - 1) % len(CREATURES)
        elif badge.pressed(BUTTON_RIGHT):
            selected_creature = (selected_creature + 1) % len(CREATURES)
        elif badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
            selected_mode ^= 1
        elif badge.pressed(BUTTON_SELECT):
            if selected_mode:
                open_link()
            else:
                start_cpu_battle()
    elif phase == "lobby":
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_UP):
            close_link()
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            step = -1 if badge.pressed(BUTTON_LEFT) else 1
            selected_creature = (selected_creature + step) % len(CREATURES)
            duel.creature = selected_creature
    elif phase == "offer":
        if badge.pressed(BUTTON_SELECT):
            duel.accept()
        elif badge.pressed(BUTTON_BACK):
            duel.decline(now)
            phase = "lobby"
    elif phase == "moves":
        if badge.pressed(BUTTON_BACK):
            if mode == "link":
                duel.decline(now)
                phase = "lobby"
            else:
                phase = "choose"
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            selected_move ^= 1
        elif badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
            selected_move ^= 2
        elif badge.pressed(BUTTON_SELECT):
            if not battle.available(me, selected_move):
                notice = "No mends left - choose an attack."
                notice_ms = 1600
            elif mode == "cpu":
                cpu_turn(selected_move)
                next_event()
            elif duel.choose(selected_move):
                phase = "waiting"
    elif phase == "waiting":
        if badge.pressed(BUTTON_BACK):
            duel.decline(now)
            phase = "lobby"
    elif phase == "resolve":
        event_age += dt
        if event_age >= 1400 or (event_age >= 250 and badge.pressed(BUTTON_SELECT)):
            finish_event()
    elif phase == "result":
        if badge.pressed(BUTTON_SELECT):
            if mode == "cpu":
                start_cpu_battle()
            else:
                duel.rematch()
        elif badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_UP):
            if mode == "cpu":
                phase = "choose"
            else:
                duel.decline(now)
                phase = "lobby"

    if phase == "choose":
        draw_choice()
    elif phase == "lobby":
        draw_lobby(now)
    elif phase == "offer":
        draw_offer(now)
    else:
        draw_arena()
        if phase == "moves":
            draw_moves()
        elif phase == "waiting":
            draw_waiting()
        elif phase == "resolve":
            draw_event()
        else:
            draw_result()


def on_exit():
    if duel:
        duel.close()
    badge.caselights(0)


run(update)
