import random

import art
import data
import ui
from ui import box, fill, text, cursor, hp_bar


class Battle:
    """A wild critter battle, run as a queue of steps.

    Steps are ("msg", text), ("fn", callable returning more steps to run
    next), ("wait", ms), ("blink", side, ms) or ("hp",) which waits for the HP
    bars to finish draining.
    """

    def __init__(self, game, enemy):
        self.game = game
        self.party = game.save["party"]
        self.enemy = enemy
        self.me = self._first_alive()
        self.dlg = ui.Dialog()
        self.queue = []
        self.mode = "steps"
        self.menu_i = 0
        self.move_i = 0
        self.result = None
        self.stages = {"p": {"atk": 0, "def": 0}, "e": {"atk": 0, "def": 0}}
        self.shown = {"p": False, "e": True}
        self.disp = {"p": float(self.mine()["hp"]), "e": float(enemy["hp"])}
        self.blink = None
        self.wait_until = 0
        self.orb = None
        self.intro_t = 0
        self.participants = {self.me}
        self.push(
            ("wait", 650),
            ("msg", "A wild %s appeared!" % enemy["sp"]),
            ("fn", lambda: self.send_out(self.me)),
        )

    # ------------------------------------------------------------ helpers

    def _first_alive(self):
        for i, c in enumerate(self.party):
            if c["hp"] > 0:
                return i
        return 0

    def mine(self):
        return self.party[self.me]

    def side(self, s):
        return self.mine() if s == "p" else self.enemy

    def name(self, s):
        c = self.side(s)
        return c["sp"] if s == "p" else "Wild " + c["sp"]

    def push(self, *steps):
        self.queue.extend(steps)

    def send_out(self, index):
        self.me = index
        self.participants.add(index)
        self.stages["p"] = {"atk": 0, "def": 0}
        self.disp["p"] = float(self.mine()["hp"])
        self.shown["p"] = True
        return [("msg", "Go! %s!" % self.mine()["sp"])]

    def multiplier(self, stage):
        return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)

    # ------------------------------------------------------------ turns

    def player_turn(self, steps):
        # Run the player's chosen steps followed by the enemy's move.
        self.push(*steps)
        self.push(("fn", self.enemy_turn))

    def enemy_turn(self):
        if self.enemy["hp"] <= 0 or self.mine()["hp"] <= 0:
            return []
        moves = self.enemy["moves"]
        return self.attack("e", moves[random.randint(0, len(moves) - 1)])

    def attack(self, s, move):
        if self.side(s)["hp"] <= 0:
            return []
        return [
            ("msg", "%s used %s!" % (self.name(s), move)),
            ("fn", lambda: self.resolve(s, move)),
        ]

    def resolve(self, s, move):
        t = "e" if s == "p" else "p"
        user, target = self.side(s), self.side(t)
        mtype, power, accuracy, effect = data.MOVES[move]
        if random.randint(1, 100) > accuracy:
            return [("msg", "%s's attack missed!" % self.name(s))]
        if effect:
            stat, delta = effect
            who = s if delta > 0 else t
            stage = self.stages[who][stat]
            label = "ATTACK" if stat == "atk" else "DEFENSE"
            if -4 < stage + delta < 4:
                self.stages[who][stat] = stage + delta
                verb = "rose" if delta > 0 else "fell"
                return [("blink", t, 300), ("msg", "%s's %s %s!" % (self.name(who), label, verb))]
            return [("msg", "Nothing happened!")]

        atk = data.stat(user, 2) * self.multiplier(self.stages[s]["atk"])
        dfn = data.stat(target, 3) * self.multiplier(self.stages[t]["def"])
        eff = data.effectiveness(mtype, data.SPECIES[target["sp"]][0])
        same_type = 1.5 if mtype == data.SPECIES[user["sp"]][0] else 1
        base = (2 * user["lv"] / 5 + 2) * power * atk / dfn / 50 + 2
        crit = random.randint(1, 16) == 1
        dmg = int(base * eff * same_type * (1.5 if crit else 1) * random.randint(85, 100) / 100)
        dmg = max(1, dmg)
        target["hp"] = max(0, target["hp"] - dmg)

        steps = [("blink", t, 450), ("hp",)]
        if crit:
            steps.append(("msg", "A critical hit!"))
        if eff > 1:
            steps.append(("msg", "It's super effective!"))
        elif eff < 1:
            steps.append(("msg", "It's not very effective..."))
        steps.append(("fn", lambda: self.check_faint(t)))
        return steps

    def check_faint(self, t):
        if self.side(t)["hp"] > 0:
            return []
        if t == "e":
            self.queue = []
            return [
                ("hide", "e"),
                ("msg", "Wild %s fainted!" % self.enemy["sp"]),
                ("fn", self.gain_xp),
            ]
        self.queue = []
        return [
            ("hide", "p"),
            ("msg", "%s fainted!" % self.mine()["sp"]),
            ("fn", self.after_faint),
        ]

    def after_faint(self):
        self.participants.discard(self.me)
        for i, c in enumerate(self.party):
            if c["hp"] > 0:
                return [("fn", lambda: self.send_out(i))]
        return [
            ("msg", "You have no critters left to fight!"),
            ("msg", "You hurried home to rest..."),
            ("fn", lambda: self.finish("lose")),
        ]

    def gain_xp(self):
        species = data.SPECIES[self.enemy["sp"]]
        alive = [i for i in self.participants if self.party[i]["hp"] > 0]
        if not alive:
            return [("fn", lambda: self.finish("win"))]
        amount = max(1, species[5] * self.enemy["lv"] // 7 // len(alive))
        steps = []
        for i in alive:
            c = self.party[i]
            c["xp"] += amount
            steps.append(("msg", "%s gained %d EXP. Points!" % (c["sp"], amount)))
            while c["lv"] < 50 and c["xp"] >= data.xp_for(c["lv"] + 1):
                old_max = data.max_hp(c)
                c["lv"] += 1
                c["hp"] += data.max_hp(c) - old_max
                steps.append(("msg", "%s grew to level %d!" % (c["sp"], c["lv"])))
                for lv, move in data.SPECIES[c["sp"]][6]:
                    if lv == c["lv"] and move not in c["moves"]:
                        if len(c["moves"]) >= 4:
                            c["moves"].pop(0)
                        c["moves"].append(move)
                        steps.append(("msg", "%s learned %s!" % (c["sp"], move)))
        steps.append(("fn", lambda: self.finish("win")))
        return steps

    def finish(self, result):
        self.result = result
        return []

    # ------------------------------------------------------------ actions

    def choose_move(self, move):
        mine, foe = self.mine(), self.enemy
        foe_move = foe["moves"][random.randint(0, len(foe["moves"]) - 1)]
        me_first = data.stat(mine, 4) >= data.stat(foe, 4)
        if me_first:
            self.push(*self.attack("p", move))
            self.push(("fn", lambda: self.attack("e", foe_move)))
        else:
            self.push(*self.attack("e", foe_move))
            self.push(("fn", lambda: self.attack("p", move)))
        self.mode = "steps"

    def throw_orb(self):
        save = self.game.save
        if len(self.party) >= 6:
            self.push(("msg", "Your team is full! You can carry six critters."))
            return
        if save["orbs"] <= 0:
            self.push(("msg", "You don't have any CAPTURE ORBS!"))
            return
        save["orbs"] -= 1
        e = self.enemy
        chance = (1 - 0.66 * e["hp"] / data.max_hp(e)) * 0.85
        caught = random.random() < chance
        wobbles = 3 if caught else random.randint(0, 2)

        def hide_enemy():
            self.orb = 0
            self.shown["e"] = False
            return []

        def wobble(n):
            def run():
                self.orb = n
                return [("wait", 550)]
            return run

        steps = [("msg", "You threw a CAPTURE ORB!"), ("fn", hide_enemy), ("wait", 500)]
        for n in range(1, wobbles + 1):
            steps.append(("fn", wobble(n)))
        if caught:
            def keep():
                self.party.append(self.enemy)
                return []
            steps += [
                ("msg", "Gotcha! %s was caught!" % e["sp"]),
                ("fn", keep),
                ("msg", "%s joined your team!" % e["sp"]),
                ("fn", lambda: self.finish("catch")),
            ]
            self.push(*steps)
        else:
            def escape():
                self.orb = None
                self.shown["e"] = True
                return []
            steps += [("fn", escape), ("msg", "Oh no! It broke free!")]
            self.player_turn(steps)

    def use_potion(self):
        save = self.game.save
        c = self.mine()
        if save["potions"] <= 0:
            self.push(("msg", "You don't have any POTIONS!"))
            return
        top = data.max_hp(c)
        if c["hp"] >= top:
            self.push(("msg", "It won't have any effect."))
            return
        save["potions"] -= 1
        gained = min(20, top - c["hp"])
        c["hp"] += gained
        self.player_turn([("hp",), ("msg", "%s recovered %d HP!" % (c["sp"], gained))])

    def switch_to(self, index):
        if index == self.me:
            self.push(("msg", "%s is already out!" % self.mine()["sp"]))
            return
        if self.party[index]["hp"] <= 0:
            self.push(("msg", "%s has no energy left to fight!" % self.party[index]["sp"]))
            return
        old = self.mine()["sp"]

        def recall():
            self.shown["p"] = False
            return []

        self.player_turn([
            ("msg", "Come back, %s!" % old),
            ("fn", recall),
            ("wait", 300),
            ("fn", lambda: self.send_out(index)),
        ])

    def run_away(self):
        mine, foe = self.mine(), self.enemy
        if data.stat(mine, 4) >= data.stat(foe, 4) or random.randint(1, 100) <= 60:
            self.push(("msg", "Got away safely!"), ("fn", lambda: self.finish("run")))
        else:
            self.player_turn([("msg", "Couldn't get away!")])

    # ------------------------------------------------------------ update

    def hp_settled(self):
        return all(abs(self.disp[s] - self.side(s)["hp"]) < 0.01 for s in ("p", "e"))

    def update(self):
        dt = badge.ticks_delta
        self.intro_t += dt
        for s in ("p", "e"):
            target = self.side(s)["hp"]
            rate = max(12, data.max_hp(self.side(s)) * 1.2) * dt / 1000
            if self.disp[s] < target:
                self.disp[s] = min(target, self.disp[s] + rate)
            else:
                self.disp[s] = max(target, self.disp[s] - rate)

        if self.mode == "steps":
            self.run_steps()
        elif self.mode == "menu":
            self.update_menu()
        elif self.mode == "fight":
            self.update_fight()
        self.draw()

    def run_steps(self):
        if self.dlg.active():
            self.dlg.update(self.hp_settled())
            if self.dlg.active():
                return
        while self.queue:
            if self.result:
                return
            step = self.queue[0]
            kind = step[0]
            if kind == "wait":
                if not self.wait_until:
                    self.wait_until = badge.ticks + step[1]
                if badge.ticks < self.wait_until:
                    return
                self.wait_until = 0
            elif kind == "blink":
                if not self.blink:
                    self.blink = (step[1], badge.ticks + step[2])
                if badge.ticks < self.blink[1]:
                    return
                self.blink = None
            elif kind == "hp":
                if not self.hp_settled():
                    return
            elif kind == "hide":
                self.shown[step[1]] = False
            elif kind == "msg":
                self.queue.pop(0)
                self.dlg.say(step[1])
                return
            elif kind == "fn":
                self.queue.pop(0)
                more = step[1]() or []
                self.queue = list(more) + self.queue
                continue
            self.queue.pop(0)
        if not self.result:
            self.mode = "menu"

    def update_menu(self):
        i = self.menu_i
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            i ^= 1
        if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
            i ^= 2
        self.menu_i = i
        if badge.pressed(BUTTON_SELECT):
            if i == 0:
                self.mode = "fight"
                self.move_i = min(self.move_i, len(self.mine()["moves"]) - 1)
            elif i == 1:
                self.game.open_team(self)
            elif i == 2:
                self.game.open_bag(self)
            else:
                self.mode = "steps"
                self.run_away()

    def update_fight(self):
        moves = self.mine()["moves"]
        i = self.move_i
        if badge.pressed(BUTTON_UP):
            i = (i - 1) % len(moves)
        if badge.pressed(BUTTON_DOWN):
            i = (i + 1) % len(moves)
        self.move_i = i
        if badge.pressed(BUTTON_BACK):
            self.mode = "menu"
        elif badge.pressed(BUTTON_SELECT):
            self.choose_move(moves[self.move_i])

    # Called by the team and bag screens.
    def picked_team(self, index):
        self.mode = "steps"
        self.switch_to(index)

    def picked_item(self, item):
        self.mode = "steps"
        if item == "orbs":
            self.throw_orb()
        else:
            self.use_potion()

    # ------------------------------------------------------------ draw

    def draw_critter(self, s, x, y):
        if not self.shown[s]:
            return
        if self.blink and self.blink[0] == s and (badge.ticks // 70) % 2:
            return
        c = self.side(s)
        if s == "e":
            screen.blit(art.FRONT[c["sp"]], rect(x, y, 32, 32))
        elif c["sp"] in art.BACK:
            screen.blit(art.BACK[c["sp"]], rect(x, y, 32, 32))
        else:
            screen.blit(art.FRONT[c["sp"]], rect(x, y, -32, 32))

    def draw(self):
        screen.font = ui.FONT
        fill(0, 0, 160, 120, 0)

        # Enemy slides in from the left as the battle opens.
        slide = max(0, 1 - self.intro_t / 600)
        ex = 112 - int(slide * 160)
        fill(ex - 8, 36, 48, 5, 1)
        if self.orb is not None:
            wob = (-2, 2, -2, 0)[self.orb % 4] if self.orb else 0
            screen.blit(art.ORB, rect(ex + 12 + wob, 24, 8, 8))
        self.draw_critter("e", ex, 6)

        px = 16 + int(slide * 160)
        fill(px - 8, 74, 48, 5, 1)
        self.draw_critter("p", px, 44)

        if slide == 0:
            e = self.enemy
            text(e["sp"], 6, 3)
            text("Lv%d" % e["lv"], 50, 12)
            hp_bar(20, 22, 50, round(self.disp["e"]), data.max_hp(e))
            fill(4, 13, 1, 15, 3)
            fill(4, 28, 70, 1, 3)

            if self.shown["p"]:
                m = self.mine()
                top = data.max_hp(m)
                text(m["sp"], 80, 44)
                text("Lv%d" % m["lv"], 124, 52)
                hp_bar(98, 62, 54, round(self.disp["p"]), top)
                hp_txt = "%d/%d" % (round(self.disp["p"]), top)
                text(hp_txt, 152 - ui.text_w(hp_txt), 66)
                fill(155, 54, 1, 24, 3)
                fill(84, 78, 72, 1, 3)

        box(0, 82, 160, 38)
        if self.mode == "menu":
            box(62, 82, 98, 38)
            labels = ("FIGHT", "TEAM", "BAG", "RUN")
            for i, label in enumerate(labels):
                x = 76 + (i % 2) * 46
                y = 88 + (i // 2) * 14
                text(label, x, y)
                if i == self.menu_i:
                    cursor(x - 8, y + 3)
        elif self.mode == "fight":
            moves = self.mine()["moves"]
            box(0, 66, 64, 30)
            mtype = data.MOVES[moves[self.move_i]][0]
            text("TYPE/", 6, 70)
            text(mtype, 4, 80)
            box(62, 60, 98, 60)
            for i, move in enumerate(moves):
                y = 65 + i * 13
                text(move, 75, y)
                if i == self.move_i:
                    cursor(67, y + 3)
        else:
            self.dlg.draw()
