import os
import sys

import machine

APP_DIR = "/system/apps/rogue"

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
badge.default_clear = None
screen.antialias = image.OFF

import render
import save
from content import BLACK
from game import Game

FILTER_PATH = "/state/rogue_filter"
REPEAT_DELAY_MS = 300
REPEAT_MS = 110
QUIT_HOLD_MS = 1000
MENU_DEBOUNCE_MS = 180
BLINK_MS = 500
SAVE_IDLE_MS = 800
MOVES = ((BUTTON_LEFT, -1, 0), (BUTTON_RIGHT, 1, 0), (BUTTON_UP, 0, -1), (BUTTON_DOWN, 0, 1))
CONTROLS = (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_UP, BUTTON_DOWN, BUTTON_SELECT, BUTTON_MENU, BUTTON_HOME, BUTTON_BACK)

screen.font = render.small_font


class Mode:
    INTRO = 1
    PLAYING = 2
    DEAD = 3
    ESCAPED = 4


def menu_pressed():
    return badge.pressed(BUTTON_MENU) or badge.pressed(BUTTON_HOME)


def visible_enemies(area):
    return sum(1 for enemy in area.enemies if area.visible[enemy.y][enemy.x])


class Menu:
    def __init__(self):
        self.open = False
        self.tab = "pack"
        self.toggled_at = 0
        self.saving = False

    def toggle(self):
        if badge.ticks - self.toggled_at < MENU_DEBOUNCE_MS:
            return False
        self.open = not self.open
        self.toggled_at = badge.ticks
        if self.open:
            self.tab = "pack"
        return True


class App:
    def __init__(self):
        self.mode = Mode.INTRO
        self.game = None
        self.menu = Menu()
        self.dirty = True
        self.repeat_button = None
        self.repeat_at = 0
        self.repeat_halted = False
        self.home_down_at = None
        self.unsaved = False
        self.input_at = 0
        self.resume = True if save.has_save() else None
        try:
            with open(FILTER_PATH) as file:
                self.filter_index = render.FILTERS.index(file.read().strip())
        except (OSError, ValueError):
            self.filter_index = 0

    def start(self, game=None):
        if game is None:
            save.delete_save()
            game = Game(badge.ticks)
        self.game = game
        self.menu.open = False
        self.mode = Mode.PLAYING
        self.dirty = True

    def update(self):
        self.watch_home_hold()
        if self.menu.saving:
            self.write_save()
            quit_rogue()
        if self.mode == Mode.INTRO:
            self.update_intro()
        elif self.mode == Mode.PLAYING:
            self.update_playing()
            if self.dirty:
                self.unsaved = True
                self.input_at = badge.ticks
            if self.game.dead or self.game.escaped:
                self.mode = Mode.DEAD if self.game.dead else Mode.ESCAPED
                save.delete_save()
                self.unsaved = False
                self.resume = None
            elif self.unsaved and badge.ticks - self.input_at >= SAVE_IDLE_MS and not self.holding_move():
                self.write_save()
        elif badge.pressed(BUTTON_SELECT):
            self.start()

        if self.dirty:
            if self.mode == Mode.INTRO:
                render.draw_intro(self.filter_index, int(badge.ticks / BLINK_MS) % 2, self.resume)
            elif self.mode == Mode.PLAYING:
                render.draw_game(self.game, self.menu)
            elif self.mode == Mode.ESCAPED:
                render.draw_escaped(self.game, self.menu)
            else:
                render.draw_dead(self.game, self.menu)
            render.apply_filter(self.filter_index)
            self.dirty = False

    def update_intro(self):
        if badge.pressed(BUTTON_SELECT):
            try:
                with open(FILTER_PATH, "w") as file:
                    file.write(render.FILTERS[self.filter_index])
            except OSError:
                pass
            self.start(save.load_game() if self.resume else None)
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            step = 1 if badge.pressed(BUTTON_RIGHT) else -1
            self.filter_index = (self.filter_index + step) % len(render.FILTERS)
            self.dirty = True
        elif self.resume is not None and (badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN)):
            self.resume = not self.resume
            self.dirty = True
        elif int(badge.ticks / BLINK_MS) != int((badge.ticks - badge.ticks_delta) / BLINK_MS):
            self.dirty = True

    def update_playing(self):
        game = self.game
        if game.player.sleep > 0 and any(badge.pressed(button) for button in CONTROLS):
            game.sleep_turn()
            self.dirty = True
        elif self.menu.open:
            self.update_menu()
        elif menu_pressed():
            self.dirty = self.menu.toggle()
        elif self.update_moves():
            self.dirty = True
        elif badge.pressed(BUTTON_SELECT):
            game.take_turn(0, 0)
            self.dirty = True

    def update_menu(self):
        game = self.game
        menu = self.menu
        pack = game.player.pack

        if menu_pressed():
            self.dirty = menu.toggle()
            return
        if menu.tab == "map":
            if badge.pressed(BUTTON_DOWN):
                menu.tab = "pack"
                self.dirty = True
            elif badge.pressed(BUTTON_SELECT):
                menu.saving = True
                self.dirty = True
            return

        if badge.pressed(BUTTON_BACK):
            menu.open = False
            if game.drop_selected():
                game.end_turn()
        elif badge.pressed(BUTTON_LEFT):
            pack.cursor = max(0, pack.cursor - 1)
        elif badge.pressed(BUTTON_RIGHT):
            pack.cursor = min(pack.slots - 1, pack.cursor + 1)
        elif badge.pressed(BUTTON_UP):
            if pack.cursor < render.PACK_COLS:
                menu.tab = "map"
            else:
                pack.cursor -= render.PACK_COLS
        elif badge.pressed(BUTTON_DOWN):
            pack.cursor = min(pack.slots - 1, pack.cursor + render.PACK_COLS)
        elif badge.pressed(BUTTON_SELECT):
            menu.open = False
            if game.use_selected():
                game.end_turn()
        else:
            return
        self.dirty = True

    def update_moves(self):
        now = badge.ticks
        for button, dx, dy in MOVES:
            if badge.pressed(button):
                self.repeat_button = button
                self.repeat_at = now + REPEAT_DELAY_MS
                self.repeat_halted = False
                self.move(dx, dy)
                return True

        if self.repeat_button is None:
            return False
        if not badge.held(self.repeat_button):
            self.repeat_button = None
            return False
        if self.repeat_halted or now < self.repeat_at:
            return False

        self.repeat_at = now + REPEAT_MS
        for button, dx, dy in MOVES:
            if button == self.repeat_button:
                self.move(dx, dy)
                return True
        return False

    def move(self, dx, dy):
        game = self.game
        messages = game.log.count
        hp = game.player.hp
        seen = visible_enemies(game.area)
        game.take_turn(dx, dy)
        if game.log.count != messages or game.player.hp < hp or visible_enemies(game.area) > seen:
            self.repeat_halted = True

    def holding_move(self):
        return self.repeat_button is not None and badge.held(self.repeat_button)

    def write_save(self):
        save.save_game(self.game)
        self.unsaved = False
        self.resume = True

    def watch_home_hold(self):
        if not badge.buttons.held(BUTTON_HOME):
            self.home_down_at = None
        elif self.home_down_at is None:
            self.home_down_at = badge.ticks
        elif badge.ticks - self.home_down_at >= QUIT_HOLD_MS:
            quit_rogue()


def quit_rogue():
    on_exit()
    reset()


def on_exit():
    if app.mode == Mode.PLAYING and app.unsaved:
        app.write_save()
    badge.default_clear = BLACK


def home_irq(_pin):
    if app.mode != Mode.PLAYING:
        quit_rogue()


app = App()
machine.Pin.board.BUTTON_HOME.irq(trigger=machine.Pin.IRQ_FALLING, handler=home_irq)
run(app.update)
