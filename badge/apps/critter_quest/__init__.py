import os
import sys

APP_DIR = "/system/apps/critter_quest"

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import random

from badgeware import State

import art
import data
import ui
from battle import Battle
from ui import box, fill, text, cursor, hp_bar

STATE_KEY = "critter_quest"
STEP_MS = 230
ENCOUNTER_CHANCE = 14
DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
BUTTON_DIRS = (
    (BUTTON_UP, "up"),
    (BUTTON_DOWN, "down"),
    (BUTTON_LEFT, "left"),
    (BUTTON_RIGHT, "right"),
)


def fresh_save():
    return {
        "started": False,
        "x": data.START[0],
        "y": data.START[1],
        "facing": "down",
        "party": [],
        "orbs": 3,
        "potions": 2,
        "gift": False,
        "caught": 0,
    }


class Game:
    def __init__(self):
        self.save = fresh_save()
        State.load(STATE_KEY, self.save)
        self.mode = "title"
        self.title_i = 0
        self.dlg = ui.Dialog()
        self.overlay = None  # "start", "team", "bag"
        self.overlay_i = 0
        self.overlay_owner = None
        self.battle = None
        self.trans = None  # (kind, start_ms)
        self.reset_world()

    # ------------------------------------------------------------ setup

    def reset_world(self):
        s = self.save
        self.x, self.y = s["x"], s["y"]
        self.facing = s["facing"]
        self.pal = (self.x, self.y)  # partner tile, hidden under the player
        self.pal_from = self.pal
        self.pal_facing = self.facing
        self.walking = False
        self.walk_t = 0.0
        self.step_n = 0
        self.turn_until = 0
        self.npc_facing = "left"
        self.heart_until = 0

    def persist(self):
        s = self.save
        s["x"], s["y"], s["facing"] = self.x, self.y, self.facing
        State.save(STATE_KEY, s)

    def new_game(self):
        self.save = fresh_save()
        self.save["started"] = True
        self.save["party"] = [data.new_critter("VOLTPUP", 5)]
        self.reset_world()
        self.mode = "world"
        self.dlg.say(
            "Welcome to the world of critters!",
            "Your partner VOLTPUP refuses to ride in a CAPTURE ORB, so it "
            "follows you everywhere.",
            "Walk through tall grass to meet wild critters. Press MENU to see "
            "your team and bag.",
            self.persist,
        )

    def heal_all(self):
        for c in self.save["party"]:
            c["hp"] = data.max_hp(c)
        self.persist()

    # ------------------------------------------------------------ main loop

    def update(self):
        screen.font = ui.FONT
        if self.mode == "title":
            self.update_title()
        elif self.mode == "battle":
            if self.overlay:
                self.battle.draw()
                self.update_overlay()
            else:
                self.battle.update()
                if self.battle.result and not self.trans:
                    self.trans = ("out", badge.ticks)
            self.draw_transition()
        else:
            self.update_world()
            self.draw_transition()

    # ------------------------------------------------------------ title

    def update_title(self):
        fill(0, 0, 160, 120, 1)
        fill(0, 6, 160, 30, 3)
        fill(0, 8, 160, 26, 0)
        screen.font = font.ziplock
        title = "CRITTER QUEST"
        tw = ui.text_w(title)
        text(title, (160 - tw) // 2 + 1, 12, 1)
        text(title, (160 - tw) // 2, 11, 3)
        screen.font = ui.FONT
        sub = "Sunshine Edition"
        text(sub, (160 - ui.text_w(sub)) // 2, 38, 3)

        bob = 2 if (badge.ticks // 300) % 2 else 0
        has_save = self.save["started"] and self.save["party"]
        options = ("CONTINUE", "NEW GAME") if has_save else ("NEW GAME",)
        mx = 92 if len(options) > 1 else 56
        fill(mx - 4, 92, 56, 6, 2)
        screen.blit(art.FRONT["VOLTPUP"], rect(mx, 46 - bob, 48, 48))

        if len(options) > 1:
            if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
                self.title_i ^= 1
            box(4, 66, 82, 34)
            for i, label in enumerate(options):
                text(label, 18, 73 + i * 12)
                if i == self.title_i:
                    cursor(10, 74 + i * 12)
        elif (badge.ticks // 500) % 2:
            label = "Press SELECT"
            text(label, (160 - ui.text_w(label)) // 2, 106, 3)

        if badge.pressed(BUTTON_SELECT):
            if options[self.title_i if len(options) > 1 else 0] == "CONTINUE":
                self.reset_world()
                self.mode = "world"
            else:
                self.new_game()

    # ------------------------------------------------------------ world

    def blocked(self, x, y):
        if data.tile(x, y) not in data.WALKABLE:
            return True
        return (x, y) == data.NPC_POS

    def update_world(self):
        dt = badge.ticks_delta
        if self.walking:
            self.walk_t += dt / STEP_MS
            if self.walk_t >= 1:
                self.walking = False
                self.walk_t = 0.0
                self.after_step()

        was_open = self.overlay
        if self.overlay:
            pass
        elif self.dlg.active():
            self.dlg.update()
        elif not self.walking and not self.trans:
            self.world_input()

        self.draw_world()
        if was_open and self.overlay:
            self.update_overlay()
        elif not self.overlay:
            self.dlg.draw()

    def world_input(self):
        if badge.pressed(BUTTON_MENU):
            self.open_overlay("start")
            return
        if badge.pressed(BUTTON_SELECT):
            self.interact()
            return
        want = None
        for button, name in BUTTON_DIRS:
            if badge.held(button):
                want = name
                break
        if not want:
            return
        if want != self.facing:
            self.facing = want
            self.turn_until = badge.ticks + 90
            return
        if badge.ticks < self.turn_until:
            return
        dx, dy = DIRS[want]
        nx, ny = self.x + dx, self.y + dy
        t = data.tile(nx, ny)
        if t in "DC":
            self.enter_door(t)
            return
        if self.blocked(nx, ny):
            return
        self.pal_from = self.pal
        self.pal = (self.x, self.y)
        if self.pal != self.pal_from:
            self.pal_facing = self.direction(self.pal_from, self.pal)
        self.prev = (self.x, self.y)
        self.x, self.y = nx, ny
        self.walking = True
        self.walk_t = 0.0
        self.step_n += 1

    def direction(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx < 0:
            return "left"
        if dx > 0:
            return "right"
        return "up" if dy < 0 else "down"

    def after_step(self):
        self.pal_from = self.pal
        if data.tile(self.x, self.y) == "," and self.can_battle():
            if random.randint(1, 100) <= ENCOUNTER_CHANCE:
                self.start_battle(data.encounter(self.y))

    def can_battle(self):
        return any(c["hp"] > 0 for c in self.save["party"])

    def interact(self):
        dx, dy = DIRS[self.facing]
        fx, fy = self.x + dx, self.y + dy
        t = data.tile(fx, fy)
        lead = self.save["party"][0]["sp"] if self.save["party"] else "VOLTPUP"
        if (fx, fy) == self.pal and self.pal != (self.x, self.y):
            self.heart_until = badge.ticks + 1800
            mood = "happy" if self.save["party"][0]["hp"] > 0 else "tired, but glad you're here"
            self.dlg.say("%s looks %s!" % (lead, mood))
        elif (fx, fy) == data.NPC_POS:
            self.npc_facing = {"up": "down", "down": "up", "left": "right", "right": "left"}[self.facing]
            if not self.save["gift"]:
                def gift():
                    self.save["gift"] = True
                    self.save["orbs"] += 5
                    self.save["potions"] += 2
                    self.persist()
                self.dlg.say(
                    "Oh! A trainer with a critter that walks beside them!",
                    "Take these. You'll need them out on the route.",
                    gift,
                    "You received 5 CAPTURE ORBS and 2 POTIONS!",
                    "Weaken a wild critter before throwing an orb. It's "
                    "easier to catch!",
                )
            else:
                self.dlg.say(
                    "Critters you catch get stronger as they battle.",
                    "You've caught %d critter%s so far!" % (
                        self.save["caught"], "" if self.save["caught"] == 1 else "s"),
                )
        elif t == "S":
            self.dlg.say(data.SIGNS.get((fx, fy), "It's a sign."))
        elif t in "DC":
            self.enter_door(t)
        elif t == "~":
            self.dlg.say("The water is calm and sparkling.")
        elif t == "T":
            self.dlg.say("A sturdy old tree.")

    def enter_door(self, t):
        if t == "D":
            self.dlg.say(
                "MOM: Welcome home, dear!",
                "You and your critters look worn out. Have a rest.",
                self.heal_all,
                "Your critters are fully rested!",
            )
        else:
            self.dlg.say(
                "Welcome to the CRITTER CLINIC!",
                "We'll restore your critters to full health.",
                self.heal_all,
                "...All done! We hope to see you again!",
            )

    # ------------------------------------------------------------ battle

    def start_battle(self, enemy):
        self.pending = enemy
        self.trans = ("in", badge.ticks)

    def end_battle(self):
        result = self.battle.result
        self.battle = None
        self.mode = "world"
        if result == "lose":
            self.x, self.y = data.START
            self.facing = "down"
            self.pal = self.pal_from = (self.x, self.y)
            for c in self.save["party"]:
                c["hp"] = data.max_hp(c)
            self.dlg.say("MOM: Oh my! Rest up, and try again.")
        elif result == "catch":
            self.save["caught"] += 1
        self.persist()

    def draw_transition(self):
        if not self.trans:
            return
        kind, start = self.trans
        t = badge.ticks - start
        if kind == "in":
            # Flash, then close horizontal blinds over the field.
            if t < 480:
                if (t // 80) % 2:
                    fill(0, 0, 160, 120, 3)
                return
            p = min(1, (t - 480) / 420)
            for row in range(0, 120, 8):
                fill(0, row, 160, max(1, int(8 * p)), 3)
            if p >= 1:
                self.battle = Battle(self, self.pending)
                self.mode = "battle"
                self.trans = ("open", badge.ticks)
        elif kind == "open":
            p = min(1, t / 300)
            fill(0, 0, 160, int(60 * (1 - p)), 3)
            fill(0, 60 + int(60 * p), 160, 60, 3)
            if p >= 1:
                self.trans = None
        elif kind == "out":
            p = min(1, t / 400)
            fill(0, 0, 160, int(120 * p), 3)
            if p >= 1:
                self.end_battle()
                self.trans = ("fade", badge.ticks)
        elif kind == "fade":
            p = min(1, t / 300)
            fill(0, int(120 * p), 160, 120, 3)
            if p >= 1:
                self.trans = None

    # ------------------------------------------------------------ overlays

    def open_overlay(self, kind, owner=None):
        self.overlay = kind
        self.overlay_i = 0
        self.overlay_owner = owner
        self.overlay_pick = None

    def open_team(self, owner):
        self.open_overlay("team", owner)

    def open_bag(self, owner):
        self.open_overlay("bag", owner)

    def close_overlay(self):
        self.overlay = None
        self.overlay_owner = None

    def update_overlay(self):
        if self.overlay == "start":
            self.overlay_start()
        elif self.overlay == "team":
            self.overlay_team()
        elif self.overlay == "bag":
            self.overlay_bag()

    def nav(self, count):
        if badge.pressed(BUTTON_UP):
            self.overlay_i = (self.overlay_i - 1) % count
        if badge.pressed(BUTTON_DOWN):
            self.overlay_i = (self.overlay_i + 1) % count

    def overlay_start(self):
        items = ("TEAM", "BAG", "SAVE", "CLOSE")
        if not self.dlg.active():
            self.nav(len(items))
        box(100, 0, 60, 14 + 12 * len(items))
        for i, label in enumerate(items):
            text(label, 114, 7 + i * 12)
            if i == self.overlay_i:
                cursor(106, 8 + i * 12)
        if self.dlg.active():
            return
        if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_MENU):
            self.close_overlay()
        elif badge.pressed(BUTTON_SELECT):
            choice = items[self.overlay_i]
            if choice == "TEAM":
                self.open_overlay("team")
            elif choice == "BAG":
                self.open_overlay("bag")
            elif choice == "SAVE":
                self.close_overlay()
                self.persist()
                self.dlg.say("Your progress was saved!")
            else:
                self.close_overlay()

    def overlay_team(self):
        party = self.save["party"]
        owner = self.overlay_owner
        picking = self.overlay_pick
        if not self.dlg.active():
            self.nav(len(party))
        fill(0, 0, 160, 120, 0)
        for i, c in enumerate(party):
            y = 2 + i * 20
            sel = i == self.overlay_i
            bob = 1 if sel and (badge.ticks // 250) % 2 else 0
            screen.blit(art.FRONT[c["sp"]], vec2(12, y + 1 - bob))
            text(c["sp"], 32, y)
            lv = "Lv%d" % c["lv"]
            text(lv, 156 - ui.text_w(lv), y)
            top = data.max_hp(c)
            hp_bar(46, y + 14, 48, c["hp"], top)
            hp_txt = "%d/%d" % (c["hp"], top)
            text(hp_txt, 156 - ui.text_w(hp_txt), y + 10)
            if sel:
                cursor(3, y + 4)
        if self.dlg.active():
            self.dlg.update()
            self.dlg.draw()
            return
        if not owner and not picking and len(party) < 6:
            box(0, 100, 160, 20)
            text("SEL: lead  BACK: exit", 8, 104)
        if badge.pressed(BUTTON_BACK):
            if owner:
                self.close_overlay()
                owner.mode = "menu"
            elif picking:
                self.open_overlay("bag")
            else:
                self.open_overlay("start")
                self.overlay_i = 0
        elif badge.pressed(BUTTON_SELECT):
            i = self.overlay_i
            if owner:
                self.close_overlay()
                owner.picked_team(i)
            elif picking == "potions":
                c = party[i]
                top = data.max_hp(c)
                if c["hp"] <= 0:
                    self.dlg.say("%s has fainted. Rest at home or the clinic." % c["sp"])
                elif c["hp"] >= top:
                    self.dlg.say("It won't have any effect.")
                else:
                    gained = min(20, top - c["hp"])
                    c["hp"] += gained
                    self.save["potions"] -= 1
                    self.persist()
                    self.dlg.say("%s recovered %d HP!" % (c["sp"], gained))
                    if self.save["potions"] <= 0:
                        self.dlg.say(self.close_overlay)
            elif i > 0:
                party.insert(0, party.pop(i))
                self.overlay_i = 0
                self.persist()
                self.dlg.say("%s will lead the team and walk with you!" % party[0]["sp"])

    def overlay_bag(self):
        s = self.save
        owner = self.overlay_owner
        items = (("CAPTURE ORB", "orbs"), ("POTION", "potions"), ("CANCEL", None))
        if not self.dlg.active():
            self.nav(len(items))
        box(28, 16, 132, 50)
        for i, (label, key) in enumerate(items):
            y = 23 + i * 13
            text(label, 42, y)
            if key:
                count = "x%d" % s[key]
                text(count, 152 - ui.text_w(count), y)
            if i == self.overlay_i:
                cursor(34, y + 1)
        if self.dlg.active():
            self.dlg.update()
            self.dlg.draw()
            return
        if badge.pressed(BUTTON_BACK):
            if owner:
                self.close_overlay()
                owner.mode = "menu"
            else:
                self.open_overlay("start")
                self.overlay_i = 1
            return
        if not badge.pressed(BUTTON_SELECT):
            return
        label, key = items[self.overlay_i]
        if key is None:
            if owner:
                self.close_overlay()
                owner.mode = "menu"
            else:
                self.open_overlay("start")
                self.overlay_i = 1
        elif s[key] <= 0:
            self.dlg.say("You don't have any %sS." % label)
        elif owner:
            self.close_overlay()
            owner.picked_item(key)
        elif key == "orbs":
            self.dlg.say("Use CAPTURE ORBS on wild critters in battle.")
        else:
            self.open_overlay("team")
            self.overlay_pick = "potions"

    # ------------------------------------------------------------ drawing

    def draw_world(self):
        p = self.walk_t if self.walking else 1.0
        if self.walking:
            fx, fy = self.prev
        else:
            fx, fy = self.x, self.y
        px = (fx + (self.x - fx) * p) * 16
        py = (fy + (self.y - fy) * p) * 16
        cam_x = int(px) - 72
        cam_y = int(py) - 52

        water = art.WATER_ALT if (badge.ticks // 600) % 2 else art.TILES["~"]
        tx0, ty0 = cam_x // 16, cam_y // 16
        for ty in range(ty0, ty0 + 9):
            for tx in range(tx0, tx0 + 11):
                t = data.tile(tx, ty)
                img = water if t == "~" else art.TILES[t]
                screen.blit(img, vec2(tx * 16 - cam_x, ty * 16 - cam_y))

        # NPC
        nx, ny = data.NPC_POS
        side = self.npc_facing in ("left", "right")
        npc = art.NPC["side" if side else self.npc_facing]
        sx, sy = nx * 16 - cam_x, ny * 16 - cam_y - 4
        if self.npc_facing == "right":
            screen.blit(npc, rect(sx, sy, -16, 16))
        else:
            screen.blit(npc, vec2(sx, sy))

        # Partner critter follows one tile behind.
        party = self.save["party"]
        if party and (self.walking or self.pal != (self.x, self.y)):
            ax, ay = self.pal_from
            bx, by = self.pal
            qx = (ax + (bx - ax) * p) * 16 - cam_x
            qy = (ay + (by - ay) * p) * 16 - cam_y
            if (qx, qy) != (px - cam_x, py - cam_y):
                hop = 2 if self.walking and p < 0.5 else 0
                sp = party[0]["sp"]
                img = art.BACK.get(sp, art.FRONT[sp]) if self.pal_facing == "up" else art.FRONT[sp]
                if self.pal_facing == "left":
                    screen.blit(img, rect(qx, qy - 2 - hop, -16, 16))
                else:
                    screen.blit(img, vec2(qx, qy - 2 - hop))
                if data.tile(bx, by) == "," and not self.walking:
                    screen.blit(art.TALL_OVERLAY, vec2(qx, qy))
                if badge.ticks < self.heart_until:
                    screen.blit(art.HEART, vec2(qx + 4, qy - 12))

        # Player
        side = self.facing in ("left", "right")
        frames = art.PLAYER["side" if side else self.facing]
        stepping = self.walking and p < 0.5
        img = frames[1] if stepping else frames[0]
        sx, sy = px - cam_x, py - cam_y - 4
        flip = self.facing == "right" or (not side and stepping and self.step_n % 2)
        if flip:
            screen.blit(img, rect(sx, sy, -16, 16))
        else:
            screen.blit(img, vec2(sx, sy))
        if data.tile(self.x, self.y) == "," and not self.walking:
            screen.blit(art.TALL_OVERLAY, vec2(sx, sy + 4))


game = Game()


def update():
    game.update()


def on_exit():
    if game.mode != "title" and game.save["started"]:
        game.persist()


run(update)
