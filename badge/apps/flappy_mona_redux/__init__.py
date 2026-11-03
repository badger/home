import math
import os
import sys

APP_DIR = "/system/apps/flappy_mona_redux"

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)

from badgeware import State

import effects
import ui
from course import Course
from fish import FRAMES as FISH_FRAMES
from mona import IMMORTAL_SECONDS, SIZE, Mona
from tower import ROLLER
from world import HEIGHT, WIDTH, World

STATE_KEY = "flappy_mona_redux"
MAX_FRAME_MS = 50
WARN_SECONDS = 2.0  # aura flickers when immortality is about to run out
RESTART_LOCKOUT_MS = 600  # stops a flapping thumb from instantly restarting
CAMERA_EASE = 5.0  # how eagerly the camera follows Mona up and down a tower
CAMERA_SPEED = 160  # px/s, so a drop off a tower glides instead of snapping

INTRO = 1
PLAYING = 2
GAME_OVER = 3

save = {"highscore": 0}
State.load(STATE_KEY, save)
if not isinstance(save["highscore"], int) or save["highscore"] < 0:
    save["highscore"] = 0

state = INTRO
world = World()
course = Course()
mona = Mona()
trail_clock = 0.0
new_best = False
over_at = 0
cam = 0.0  # how far the view has risen above the ground; screen y = world y + cam


def update():
    dt = min(badge.ticks_delta, MAX_FRAME_MS) / 1000
    if state == INTRO:
        intro(dt)
    elif state == PLAYING:
        play(dt)
    else:
        game_over()


def start():
    global state, course, mona, trail_clock, cam
    state = PLAYING
    course = Course()
    mona = Mona()
    mona.flap()
    trail_clock = 0.0
    cam = 0.0
    effects.clear()


def finish():
    global state, new_best, over_at
    state = GAME_OVER
    over_at = badge.ticks
    new_best = mona.score > save["highscore"]
    if new_best:
        save["highscore"] = mona.score
        try:
            State.save(STATE_KEY, save)
        except OSError:
            pass


def intro(dt):
    world.advance(dt)
    ui.pixel_mode()
    world.draw()

    t = badge.ticks / 280
    mona.x = (WIDTH - SIZE) / 2
    mona.y = 108 + math.sin(t) * 7
    mona.vy = math.cos(t) * 50
    mona.draw()

    ui.text_mode()
    ui.centered("FLAPPY MONA", 20, 38, ui.WHITE, ui.NAVY)
    ui.centered("REDUX", 62, 26, ui.GOLD, ui.NAVY)
    ui.centered("High Score: %d" % save["highscore"], 168, 15)
    if int(badge.ticks / 500) % 2:
        ui.centered("Press Select to start", 190, 15)

    if badge.pressed(BUTTON_SELECT):
        start()


def interact():
    mona.score += course.count_passed(mona.x)

    if not mona.is_immortal():
        hit = course.hits(mona.bounds(), mona.hazard_box())
        if hit == ROLLER:
            mona.flatten()
            return
        if hit is not None:
            mona.die()
            return

    fish = course.take_fish(mona.bounds())
    if fish is not None:
        mona.make_immortal()
        cx, cy = mona.center()
        effects.burst(fish.x + 24, fish.y() + 16)
        effects.show_popup("IMMORTAL!", cx, cy + int(cam) - 44)


def follow_camera(dt):
    """Rise with Mona as she climbs a tower and settle back once she is off it."""
    global cam
    tower = course.tower
    target = tower.camera_for(mona.ground_y) if mona.running and tower is not None else 0.0
    step = (target - cam) * min(1.0, CAMERA_EASE * dt)
    limit = CAMERA_SPEED * dt
    cam += max(-limit, min(limit, step))


def draw_world():
    """The scenery and course. A flattened Mona goes under the roller that squashed her."""
    world.draw(int(cam))
    if mona.flat:
        mona.draw(int(cam))
    course.draw(int(cam))


def play(dt):
    global state, trail_clock

    if not mona.is_dead():
        if badge.pressed(BUTTON_SELECT):
            mona.press()
    if not mona.is_dead() or mona.flat:
        world.advance(dt)
        course.update(dt)

    mona.update(dt, course.tower, cam)

    if not mona.is_dead():
        follow_camera(dt)
        interact()
        if mona.is_immortal():
            trail_clock += dt
            if trail_clock > 0.07:
                trail_clock = 0.0
                cx, cy = mona.center()
                effects.trail(cx - 14, cy)

    effects.update(dt)

    ui.pixel_mode()
    draw_world()
    if not mona.flat:
        if mona.is_immortal():
            draw_aura()
        mona.draw(int(cam))
    effects.draw(int(cam))
    draw_hud()

    if mona.is_done_dying():
        finish()


def game_over():
    ui.pixel_mode()
    draw_world()
    screen.pen = ui.DIM
    screen.rectangle(0, 0, WIDTH, HEIGHT)

    ui.text_mode()
    ui.centered("GAME OVER", 36, 36, ui.WHITE, ui.NAVY)
    ui.centered("Score: %d" % mona.score, 96, 22)
    if new_best:
        ui.centered("New best!", 126, 20, ui.GOLD)
    else:
        ui.centered("High Score: %d" % save["highscore"], 128, 16)
    if int(badge.ticks / 500) % 2:
        ui.centered("Press Select to retry", 180, 15)

    if badge.pressed(BUTTON_SELECT) and badge.ticks - over_at > RESTART_LOCKOUT_MS:
        start()


def draw_aura():
    if mona.immortal < WARN_SECONDS and int(badge.ticks / 110) % 2:
        return

    cx, cy = mona.center()
    cy += int(cam) + mona.lift
    pulse = 0.5 + 0.5 * math.sin(badge.ticks / 140)
    radius = 29 + 3 * pulse
    screen.antialias = image.X2
    screen.pen = color.rgb(255, 214, 80, 55 + int(35 * pulse))
    screen.shape(shape.circle(cx, cy, radius))
    screen.pen = color.rgb(255, 236, 140, 190)
    screen.shape(shape.circle(cx, cy, radius).stroke(2))
    ui.pixel_mode()


def draw_hud():
    ui.text_mode()
    label = "Score %d" % mona.score
    width, _ = ui.measure(label, 16)
    ui.panel(8, 6, width + 20, 26)
    ui.shadow_text(label, 18, 8, 16)

    if mona.is_immortal():
        left = mona.immortal
        x = WIDTH - 8 - 120
        ui.panel(x, 6, 120, 26)
        ui.shadow_text("%ds" % math.ceil(left), x + 88, 8, 16)

        ui.pixel_mode()
        screen.blit(FISH_FRAMES[0], rect(x + 6, 11, 24, 16))
        screen.pen = color.rgb(255, 255, 255, 60)
        screen.rectangle(x + 36, 16, 46, 6)
        screen.pen = ui.GOLD if left > WARN_SECONDS else color.rgb(255, 120, 80)
        screen.rectangle(x + 36, 16, int(46 * left / IMMORTAL_SECONDS), 6)

    ui.pixel_mode()


run(update)
