import os
import sys

APP_DIRS = ("/remote/apps/octocat_trail", "/system/apps/octocat_trail", "/apps/octocat_trail", "/octocat_trail")
for _path in APP_DIRS:
    if is_dir(_path):
        os.chdir(_path)
        sys.path.insert(0, _path)
        break

import trail_logic as tl
import trail_game as tg
import trail_hw as hw
import trail_draw as td

STATE_KEY = "octocat_trail"
BUTTONS = (
    ("up", BUTTON_UP), ("down", BUTTON_DOWN), ("left", BUTTON_LEFT), ("right", BUTTON_RIGHT),
    ("select", BUTTON_SELECT), ("back", BUTTON_BACK), ("menu", BUTTON_MENU),
)
ARROWS = BUTTONS[:4]

badge.mode(HIRES | VSYNC)


def read_keys():
    pressed = []
    held = []
    for name, button in BUTTONS:
        try:
            if badge.pressed(button):
                pressed.append(name)
        except Exception:
            pass
    for name, button in ARROWS:
        try:
            if badge.held(button):
                held.append(name)
        except Exception:
            pass
    return tg.Keys(pressed, held)


def load_save():
    data = tl.default_save()
    try:
        from badgeware import State
        State.load(STATE_KEY, data)
    except Exception:
        pass
    return tl.clean_save(data)


def persist(data):
    from badgeware import State
    State.save(STATE_KEY, data)


def seed(light):
    try:
        import time
        extra = time.ticks_us()
    except Exception:
        extra = 0
    return tl.fnv1a("trail:%d:%d:%d" % (badge.ticks, extra, light or 0))


sensors = hw.Sensors(badge)
lights = hw.CaseLights(badge)
rng = tl.Rng(seed(sensors.light()))
link = hw.IrLink(rng.randint(1, 126)).open()
game = tg.Game(load_save(), rng, badge.ticks, link, persist)
renderer = td.Renderer()

previous_clear = badge.default_clear
badge.default_clear = None
previous_rule = None
try:
    previous_rule = screen.fill_rule
    screen.fill_rule = image.EVEN_ODD
except Exception:
    pass
try:
    screen.antialias = image.OFF
except Exception:
    pass


def update():
    now = badge.ticks
    link.update(now)
    packets = link.process(now)
    if packets:
        game.receive(packets)
    game.update(now, read_keys(), sensors.imu(), sensors.light())
    lights.set(*game.lights())
    renderer.draw(game)


def on_exit():
    try:
        game.shutdown()
    except Exception:
        pass
    link.close()
    lights.off()
    badge.default_clear = previous_clear
    if previous_rule is not None:
        try:
            screen.fill_rule = previous_rule
        except Exception:
            pass


run(update)
