import gc
import os
import sys
import time

import machine

APP_DIR = "/system/apps/pocket_emu"

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State

badge.mode(HIRES | VSYNC)
badge.default_clear = None
screen.antialias = image.OFF

ROM_DIR = "roms"
SAVE_DIR = "/state/pocket_emu"
GB_FPS = 59.7275
MAX_CATCH_UP = 6
SAVE_IDLE_MS = 1000
SCRATCH_SAVE_MS = 60000
HOLD_MS = 450
TAP_FRAMES = 4
TOAST_MS = 1500

BORDER = color.rgb(12, 14, 13)
PANEL = color.rgb(28, 33, 30)
OUTLINE = color.rgb(70, 82, 74)
TEXT = color.rgb(230, 236, 232)
MUTED = color.rgb(140, 152, 145)
ACCENT = color.rgb(191, 255, 209)
ON_ACCENT = color.rgb(0, 0, 0)
WARN = color.rgb(255, 140, 120)
DIM = color.rgb(0, 0, 0, 150)

# Joypad bits and draw modes, matching tools/pocket_emu/gbcore.c.
GB_A, GB_B, GB_SELECT, GB_START = 0x01, 0x02, 0x04, 0x08
GB_RIGHT, GB_LEFT, GB_UP, GB_DOWN = 0x10, 0x20, 0x40, 0x80
MODE_1X, MODE_SHARP, MODE_SMOOTH = 0, 1, 2

DIRECT = (
    (BUTTON_UP, GB_UP),
    (BUTTON_DOWN, GB_DOWN),
    (BUTTON_LEFT, GB_LEFT),
    (BUTTON_RIGHT, GB_RIGHT),
    (BUTTON_SELECT, GB_A),
    (BUTTON_BACK, GB_B),
)

# Per-game colour palettes (OBJ0, OBJ1, BG) in RGB555, keyed by the ROM's
# title checksum. Values come from Peanut-GB's SDL example (MIT licence).
AUTO_PALETTES = {}


def _auto(keys, obj0, obj1, bg):
    for key in keys:
        AUTO_PALETTES[key] = (obj0, obj1, bg)


_auto((0x71, 0xFF), (0x7FFF, 0x7E60, 0x7C00, 0x0000), (0x7FFF, 0x7E60, 0x7C00, 0x0000), (0x7FFF, 0x7E60, 0x7C00, 0x0000))
_auto((0x15, 0xDB, 0x95), (0x7FFF, 0x7FE0, 0x7C00, 0x0000), (0x7FFF, 0x7FE0, 0x7C00, 0x0000), (0x7FFF, 0x7FE0, 0x7C00, 0x0000))
_auto((0x19,), (0x7FFF, 0x7E10, 0x48E7, 0x0000), (0x7FFF, 0x7E10, 0x48E7, 0x0000), (0x7FFF, 0x7E60, 0x7C00, 0x0000))
_auto((0x61, 0x45, 0xD8), (0x7FFF, 0x7E10, 0x48E7, 0x0000), (0x7FFF, 0x329F, 0x001F, 0x0000), (0x7FFF, 0x329F, 0x001F, 0x0000))
_auto((0x14,), (0x7FFF, 0x3FE6, 0x0200, 0x0000), (0x7FFF, 0x7E10, 0x48E7, 0x0000), (0x7FFF, 0x7E10, 0x48E7, 0x0000))
_auto((0x8B,), (0x7FFF, 0x7E10, 0x48E7, 0x0000), (0x7FFF, 0x329F, 0x001F, 0x0000), (0x7FFF, 0x3FE6, 0x0200, 0x0000))
_auto((0x27, 0x49, 0x5C, 0xB3), (0x7D8A, 0x6800, 0x3000, 0x0000), (0x001F, 0x7FFF, 0x7FEF, 0x021F), (0x527F, 0x7FE0, 0x0180, 0x0000))
_auto((0x18, 0x6A, 0x4B, 0x6B), (0x7F08, 0x7F40, 0x48E0, 0x2400), (0x7FFF, 0x2EFF, 0x7C00, 0x001F), (0x7FFF, 0x463B, 0x2951, 0x0000))
_auto((0x70,), (0x7FFF, 0x03E0, 0x1A00, 0x0120), (0x7FFF, 0x329F, 0x001F, 0x001F), (0x7FFF, 0x7E10, 0x48E7, 0x0000))
_auto((0x01, 0x10, 0x29, 0x52, 0x5D, 0x68, 0x6D, 0xF6), (0x7FFF, 0x329F, 0x001F, 0x0000), (0x7FFF, 0x3FE6, 0x0200, 0x0000), (0x7FFF, 0x7EAC, 0x40C0, 0x0000))

GREEN = (0xE0F8D0, 0x88C070, 0x346856, 0x081820)
GREY = (0xFFFFFF, 0xA8A8A8, 0x545454, 0x000000)

PALETTES = ("Auto colour", "Classic green", "Grey")
PIXELS = (("Sharp", MODE_SHARP), ("Smooth", MODE_SMOOTH), ("Original size", MODE_1X))
SPEEDS = (("Normal", 1), ("Fast (2x)", 2))

settings = {"palette": 0, "pixels": 0, "speed": 0, "last": ""}
State.load("pocket_emu", settings)
for key, options in (("palette", PALETTES), ("pixels", PIXELS), ("speed", SPEEDS)):
    if not isinstance(settings.get(key), int) or not 0 <= settings[key] < len(options):
        settings[key] = 0
if not isinstance(settings.get("last"), str):
    settings["last"] = ""


class Mode:
    PICK = 1
    LOADING = 2
    PLAY = 3
    PAUSE = 4
    ERROR = 5


mode = Mode.PICK
roms = []
cursor = 0
error_lines = ()
loading_name = None
loading_drawn = False

core = None
rom = None
ram = None
save_path = None
unsaved = False
dirty_banks = 0
ram_changed_at = 0
saved_at = 0
toast = None
toast_at = 0
toast_drawn = False

owed = 0.0
taps = {}
menu_down_at = None
menu_long = False
need_border = True
pause_index = 0
pause_backdrop = True


def rgb555(value):
    r = (value >> 10) & 31
    g = (value >> 5) & 31
    b = value & 31
    return (r << 11) | (((g << 1) | (g >> 4)) << 5) | b


def rgb888(value):
    return (((value >> 19) & 31) << 11) | (((value >> 10) & 63) << 5) | ((value >> 3) & 31)


def pack(colours):
    data = bytearray(24)
    for i, value in enumerate(colours):
        data[i * 2] = value & 0xFF
        data[i * 2 + 1] = value >> 8
    return data


def palette_bytes():
    choice = settings["palette"]
    if choice == 0:
        sets = AUTO_PALETTES.get(core.colour_hash())
        if sets:
            return pack([rgb555(c) for group in sets for c in group])
        shades = GREY
    else:
        shades = GREEN if choice == 1 else GREY
    return pack([rgb888(c) for c in shades] * 3)


def frame_origin():
    if PIXELS[settings["pixels"]][1] == MODE_1X:
        return (screen.width - 160) // 2, (screen.height - 144) // 2
    return (screen.width - 240) // 2, (screen.height - 216) // 2


def apply_settings():
    x, y = frame_origin()
    core.layout(screen.width, x, y, PIXELS[settings["pixels"]][1])
    core.set_palette(palette_bytes())


def is_rom(name):
    lower = name.lower()
    return not name.startswith(".") and (lower.endswith(".gb") or lower.endswith(".gbc"))


def stem(name):
    return name.rsplit(".", 1)[0]


def pretty(name):
    text = stem(name)
    for mark in (" (", " ["):
        cut = text.find(mark)
        if cut > 0:
            text = text[:cut]
    return text.strip() or name


def find_roms():
    try:
        names = [name for name in os.listdir(ROM_DIR) if is_rom(name)]
    except OSError:
        return []
    names.sort()
    return names


def fit(text, width):
    if screen.measure_text(text)[0] <= width:
        return text
    while text and screen.measure_text(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."


def centred(text, y, pen):
    width, _ = screen.measure_text(text)
    screen.pen = pen
    screen.text(text, (screen.width - width) // 2, y)


def fail(*lines):
    global mode, error_lines
    error_lines = lines
    mode = Mode.ERROR


def ensure_save_dir():
    for path in ("/state", SAVE_DIR):
        try:
            os.mkdir(path)
        except OSError:
            pass


def write_save():
    global unsaved, dirty_banks, saved_at, toast, toast_at, toast_drawn
    unsaved = False
    dirty_banks = 0
    saved_at = badge.ticks
    if save_path is None or not ram:
        return
    try:
        ensure_save_dir()
        temp = save_path + ".tmp"
        with open(temp, "wb") as file:
            file.write(ram)
        os.rename(temp, save_path)
        toast = "SAVED"
    except OSError as error:
        print("pocket_emu: save failed", error)
        toast = "SAVE!"
    toast_at = badge.ticks
    toast_drawn = False


def read_save(name):
    # Prefer the badge's own save; fall back to a .sav copied next to the ROM.
    for path in (save_path, ROM_DIR + "/" + stem(name) + ".sav"):
        try:
            with open(path, "rb") as file:
                file.readinto(ram)
            return
        except OSError:
            pass


def save_due(now):
    # Writing a save stalls the badge for about half a second. Large saves whose
    # only changes are in bank 0 (some games use it as scratch space for sprites)
    # are written at most once a minute; real save data goes out promptly.
    if not unsaved or now - ram_changed_at < SAVE_IDLE_MS:
        return False
    if len(ram) <= 0x2000 or dirty_banks & ~1:
        return True
    return now - saved_at >= SCRATCH_SAVE_MS


def on_exit():
    if unsaved:
        write_save()


def quit_app():
    on_exit()
    reset()


def start(name):
    global mode, loading_name, loading_drawn
    loading_name = name
    loading_drawn = False
    mode = Mode.LOADING


def load(name):
    global core, rom, ram, save_path, mode, owed, need_border, unsaved, dirty_banks, saved_at
    try:
        import gbcore
    except Exception as error:
        fail("The emulator core did not load.", "It needs the Universe 2026", "badge firmware.", str(error)[:40])
        return
    core = gbcore

    rom = None
    gc.collect()
    try:
        with open(ROM_DIR + "/" + name, "rb") as file:
            rom = file.read()
    except MemoryError:
        fail("Not enough memory for", pretty(name))
        return
    except OSError as error:
        fail("Could not read", pretty(name), str(error))
        return

    if len(rom) < 0x150:
        fail("This file is too small", "to be a game ROM.")
        return
    if rom[0x143] == 0xC0:
        fail(pretty(name), "is a colour-only game,", "which this emulator cannot run.")
        return

    result = core.load(rom)
    if result == 1:
        fail("This cartridge type is", "not supported.")
        return
    if result == 2:
        fail("The game file is damaged", "(header checksum failed).")
        return

    size = core.save_size()
    ram = bytearray(size)
    save_path = SAVE_DIR + "/" + stem(name) + ".sav" if size else None
    if save_path:
        read_save(name)
    core.set_ram(ram)

    now = time.localtime()
    core.set_rtc(now[7] - 1, now[3], now[4], now[5])

    apply_settings()
    settings["last"] = name
    State.save("pocket_emu", settings)

    owed = 0.0
    unsaved = False
    dirty_banks = 0
    saved_at = badge.ticks
    need_border = True
    mode = Mode.PLAY
    wait_for_release()


def is_down(action):
    return badge.pressed(action) or badge.held(action)


def wait_for_release():
    global taps, menu_down_at
    taps = {}
    menu_down_at = None
    for action, bit in DIRECT:
        if is_down(action):
            taps[bit] = -1


def read_joypad(now):
    global menu_down_at, menu_long
    bits = 0
    for action, bit in DIRECT:
        down = is_down(action)
        if taps.get(bit, 0) < 0:
            # Ignore a button carried over from the picker or pause menu until it is released.
            if not down:
                taps[bit] = 0
            continue
        if badge.pressed(action):
            taps[bit] = TAP_FRAMES
        if down:
            bits |= bit

    # MENU is START when tapped and SELECT while held.
    if badge.pressed(BUTTON_MENU) and menu_down_at is None:
        menu_down_at = now
        menu_long = False
    if menu_down_at is not None:
        if is_down(BUTTON_MENU) and not badge.released(BUTTON_MENU):
            if now - menu_down_at >= HOLD_MS:
                menu_long = True
            if menu_long:
                bits |= GB_SELECT
        else:
            if not menu_long:
                taps[GB_START] = TAP_FRAMES
            menu_down_at = None

    for bit, frames in taps.items():
        if frames > 0:
            bits |= bit
    return 0xFF ^ bits


def spend_taps(frames):
    for bit in list(taps):
        if taps[bit] > 0:
            taps[bit] = max(0, taps[bit] - frames)


def fill(pen):
    screen.pen = pen
    screen.rectangle(0, 0, screen.width, screen.height)


def draw_toast():
    global toast, toast_drawn
    if toast is None:
        return
    x = screen.width - 38
    y = screen.height - 18
    if badge.ticks - toast_at > TOAST_MS:
        screen.pen = BORDER
        screen.rectangle(x - 2, y - 2, 40, 20)
        toast = None
        return
    if toast_drawn:
        return
    screen.font = font.nope
    screen.pen = BORDER
    screen.rectangle(x - 2, y - 2, 40, 20)
    screen.pen = ACCENT if toast == "SAVED" else WARN
    screen.text(toast, x, y)
    toast_drawn = True


def play():
    global owed, need_border, unsaved, dirty_banks, ram_changed_at, mode, pause_index, pause_backdrop
    now = badge.ticks

    if badge.pressed(BUTTON_HOME):
        if unsaved:
            write_save()
        mode = Mode.PAUSE
        pause_index = 0
        pause_backdrop = True
        return

    joypad = read_joypad(now)

    owed += badge.ticks_delta * GB_FPS * SPEEDS[settings["speed"]][1] / 1000
    if owed > MAX_CATCH_UP:
        owed = MAX_CATCH_UP
    frames = int(owed)
    owed -= frames

    if need_border:
        fill(BORDER)
        need_border = False
        frames = max(frames, 1)

    if frames:
        error = core.run(frames, joypad, screen)
        spend_taps(frames)
        if error:
            write_save()
            kind = ("an unknown error", "an invalid opcode", "an invalid read", "an invalid write")
            fail("The game stopped with", kind[min(error, 4) - 1], "at 0x%04X." % core.error_addr())
            return

    banks = core.ram_dirty()
    if banks:
        unsaved = True
        dirty_banks |= banks
        ram_changed_at = now
    if save_due(now):
        write_save()

    draw_toast()


PAUSE_ITEMS = ("Resume", "Colours", "Pixels", "Speed", "Save and quit")
PAUSE_SETTINGS = {1: ("palette", PALETTES), 2: ("pixels", PIXELS), 3: ("speed", SPEEDS)}


def pause_value(index):
    if index not in PAUSE_SETTINGS:
        return None
    key, options = PAUSE_SETTINGS[index]
    value = options[settings[key]]
    return value if isinstance(value, str) else value[0]


def change_setting(index, step):
    global pause_backdrop
    if index not in PAUSE_SETTINGS:
        return
    key, options = PAUSE_SETTINGS[index]
    settings[key] = (settings[key] + step) % len(options)
    apply_settings()
    pause_backdrop = True


def resume():
    global mode, need_border, owed
    State.save("pocket_emu", settings)
    mode = Mode.PLAY
    need_border = True
    owed = 0.0
    wait_for_release()


def pause():
    global pause_index, pause_backdrop

    if pause_backdrop:
        # Repaint the game (one emulated frame) so setting changes show behind the panel.
        fill(BORDER)
        core.run(1, 0xFF, screen)
        fill(DIM)
        pause_backdrop = False

    if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_HOME):
        resume()
        return
    if badge.pressed(BUTTON_UP):
        pause_index = (pause_index - 1) % len(PAUSE_ITEMS)
    elif badge.pressed(BUTTON_DOWN):
        pause_index = (pause_index + 1) % len(PAUSE_ITEMS)
    elif badge.pressed(BUTTON_LEFT):
        change_setting(pause_index, -1)
    elif badge.pressed(BUTTON_RIGHT):
        change_setting(pause_index, 1)
    elif badge.pressed(BUTTON_SELECT):
        if pause_index == 0:
            resume()
            return
        if pause_index == len(PAUSE_ITEMS) - 1:
            State.save("pocket_emu", settings)
            quit_app()
            return
        change_setting(pause_index, 1)

    if not pause_backdrop:
        draw_pause_panel()


def draw_pause_panel():
    width, height = 224, 160
    x = (screen.width - width) // 2
    y = (screen.height - height) // 2
    screen.pen = OUTLINE
    screen.shape(shape.rounded_rectangle(x - 2, y - 2, width + 4, height + 4, 8))
    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(x, y, width, height, 6))

    screen.font = font.ziplock
    centred("Paused", y + 6, ACCENT)

    screen.font = font.sins
    row_y = y + 34
    row_h = 22
    for index, label in enumerate(PAUSE_ITEMS):
        selected = index == pause_index
        if selected:
            screen.pen = ACCENT
            screen.shape(shape.rounded_rectangle(x + 8, row_y - 4, width - 16, row_h - 2, 4))
        screen.pen = ON_ACCENT if selected else TEXT
        screen.text(label, x + 16, row_y)
        value = pause_value(index)
        if value:
            value_w, _ = screen.measure_text(value)
            screen.pen = ON_ACCENT if selected else MUTED
            screen.text(value, x + width - 16 - value_w, row_y)
        row_y += row_h

    screen.font = font.nope
    centred("LEFT/RIGHT change   BACK resume", y + height - 16, MUTED)


def draw_picker():
    fill(BORDER)

    screen.font = font.ziplock
    centred("Pocket Emu", 8, ACCENT)
    screen.font = font.sins

    if not roms:
        lines = (
            "No games found.",
            "",
            "Copy your .gb game files to",
            "apps/pocket_emu/roms on the",
            "BADGER drive (USB Disk Mode),",
            "then open this app again.",
        )
        y = 52
        for line in lines:
            centred(line, y, TEXT)
            y += 20
        screen.font = font.nope
        centred("BACK or HOME to exit", screen.height - 20, MUTED)
        return

    row_h = 24
    visible = (screen.height - 100) // row_h
    first = max(0, min(cursor - visible // 2, len(roms) - visible))
    y = 40
    for index in range(first, min(len(roms), first + visible)):
        selected = index == cursor
        if selected:
            screen.pen = ACCENT
            screen.shape(shape.rounded_rectangle(20, y - 4, screen.width - 40, row_h - 2, 5))
        screen.pen = ON_ACCENT if selected else TEXT
        screen.text(fit(pretty(roms[index]), screen.width - 64), 32, y)
        y += row_h

    screen.font = font.nope
    y = screen.height - 34
    for line in ("SELECT = A    BACK = B    MENU = START", "hold MENU = SELECT    HOME = pause and quit"):
        centred(line, y, MUTED)
        y += 14


def pick():
    global cursor
    if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_HOME):
        quit_app()
        return
    if roms:
        if badge.pressed(BUTTON_UP):
            cursor = (cursor - 1) % len(roms)
        elif badge.pressed(BUTTON_DOWN):
            cursor = (cursor + 1) % len(roms)
        elif badge.pressed(BUTTON_SELECT):
            start(roms[cursor])
            return
    draw_picker()


def loading():
    global loading_drawn
    if not loading_drawn:
        # Show the message for one frame before the (blocking) ROM load.
        fill(BORDER)
        screen.font = font.sins
        centred("Loading", screen.height // 2 - 20, MUTED)
        centred(fit(pretty(loading_name), screen.width - 40), screen.height // 2 + 4, TEXT)
        loading_drawn = True
        return
    load(loading_name)


def show_error():
    fill(BORDER)
    screen.font = font.sins
    y = 60
    for line in error_lines:
        centred(fit(line, screen.width - 24), y, TEXT)
        y += 22
    screen.font = font.nope
    centred("BACK or HOME to exit", screen.height - 20, MUTED)
    if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_HOME):
        quit_app()


def update():
    if mode == Mode.PLAY:
        play()
    elif mode == Mode.PAUSE:
        pause()
    elif mode == Mode.PICK:
        pick()
    elif mode == Mode.LOADING:
        loading()
    else:
        show_error()


roms = find_roms()
if settings["last"] in roms:
    cursor = roms.index(settings["last"])
if len(roms) == 1:
    start(roms[0])

# HOME opens the pause menu (which has Save and quit) instead of leaving
# immediately, so a game is never closed with unsaved progress.
machine.Pin.board.BUTTON_HOME.irq(handler=None, trigger=0)

run(update)
