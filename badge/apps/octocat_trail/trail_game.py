"""Screen flow for The Octocat Trail.

A pure controller: update() takes the clock, a Keys snapshot and optional
sensor readings, drives the rules in trail_logic across the venue map in
trail_map, and describes each screen as a View for trail_draw to render. It
never touches the badge runtime, so CPython tests can play the whole game
with fake keys.
"""

import trail_logic as tl
import trail_map as tm

TOAST_MS = 3500
MAX_DT = 250
CAMP_DAY_MS = 2000
MAX_CAMP_DAYS = 3
CROSS_MS = 1800
EVENT_PAGE = 3
STOP_PAGE = 2
SAVE_EVERY_DAYS = 15
WALK_FRAME_MS = 120

# (key name, dx, dy), also the order that breaks ties between held keys.
DIRS = (("up", 0, -1), ("down", 0, 1), ("left", -1, 0), ("right", 1, 0))
# (supply key, singular unit, plural suffix) for store notes.
UNITS = (("brew", "Cold Brew Keg", "s"), ("lgtm", "LGTM Stamp", "s"), ("patches", "Hotfix Patch", "es"))
# (stop, counter name) for every stop that sells supplies.
STORE_NAMES = (
    (0, "Gatehouse General Store"),
    (1, "The GitHub Shop"),
    (9, "Makerspace Parts Counter"),
    (6, "Firehouse Supply Locker"),
)
MONITORS = ("Color", "Green")
PACE_NOTES = (
    "A steady clip. Nobody burns out.",
    "Long days. Health slips a little.",
    "Ship at any cost. Health drops fast.",
)
RATION_NOTES = (
    "Nitro cold brew. The party thrives.",
    "Plain drip. Steady and sensible.",
    "Decaf saves kegs but saps morale.",
)
SPEAKERS = (
    "A maintainer",
    "A Hubber",
    "A first-time contributor",
    "A Copilot power user",
    "A security researcher",
    "A Universe volunteer",
)
HELP = (
    ("The Octocat Trail", (
        "Lead the Studio party 2,000 steps across Fort Mason, from the Gatehouse to the GitHub Universe Mainstage.",
        "The GitHub Ducky pulls the wagon. Mona rides up front and hunts the bugs.",
    )),
    ("Getting around", (
        "Walk the venue with the D-pad. Every step passes time and drinks cold brew.",
        "Press SELECT to stop and look around: wagon, map, pace, rations, camp and stores.",
    )),
    ("Production Deployments", (
        "The piers sit across open water. Deploy a gangway from each dock to cross.",
        "YOLO the ford, ship with 2 LGTMs, pay Copilot to ferry you or wait for review.",
    )),
    ("Sprints and sensors", (
        "Shake the badge, or press BACK, for a turbo sprint. Sprints drink extra brew.",
        "Turn off the lights and the party makes Dark Mode Camp. MENU swaps the monitor.",
    )),
    ("Beaming over IR", (
        "Point your badge at a friend's and press SELECT on a tombstone or victory to beam it.",
        "Beams only reach badges that are running The Octocat Trail.",
    )),
)


def supply_label(key):
    for supply, label in tl.SUPPLIES:
        if supply == key:
            return label
    return key


def unit(key, count):
    for supply, word, suffix in UNITS:
        if supply == key:
            return tl.plural(count, word, suffix)
    return str(count)


def kegs(amount):
    """Format a keg amount to one decimal place, e.g. 1.5."""
    return tl.tenths(int(amount * 10 + 0.5))


class Keys:
    """One frame of input: names in pressed fired this frame, names in
    held are down now. Names: up, down, left, right, select, back, menu."""

    def __init__(self, pressed=(), held=()):
        self.pressed = pressed
        self.held = held

    def hit(self, name):
        return name in self.pressed

    def down(self, name):
        return name in self.held


NO_KEYS = Keys()


class View:
    """What to draw. kind is title, menu, store, roam, card, stop, supplies,
    map, river, crossing, hunt, camp, tombstone, victory or help. options
    are (label, value, enabled) rows, progress is 0-1 or None, rows are
    (label, value) pairs and data carries screen-specific extras."""

    def __init__(self, kind, title="", lines=(), options=(), cursor=-1, hint="", progress=None):
        self.kind = kind
        self.title = title
        self.lines = lines
        self.options = options
        self.cursor = cursor
        self.hint = hint
        self.progress = progress
        self.note = ""
        self.foot = ()
        self.rows = ()
        self.data = None


class Game:
    def __init__(self, save, rng, now=0, link=None, persist=None):
        self.save = save
        self.rng = rng
        self.now = int(now)
        self.link = link
        self.persist_fn = persist
        self.trail = None
        self.resume = None
        self.over = False
        self.screen = "title"
        self.cursor = 0
        self.note = ""
        self.origin = "roam"
        self.menu_cursor = 0
        self.card_title = ""
        self.card_lines = [""]
        self.card_page = 0
        self.card_after = "title"
        self.card_back = None
        self.stop_lines = []
        self.stop_page = 0
        self.walk = None
        self.stride = 0
        self.last_dir = None
        self.bump = ""
        self.want_menu = False
        self.saved_day = 0
        self.hunt = None
        self.cross_stop = -1
        self.cross_option = 0
        self.cross_lines = []
        self.cross_failed = False
        self.cross_ms = 0
        self.cross_name = ""
        self.toasts = []
        self.camp_auto = False
        self.camp_days = 0
        self.camp_timer = 0
        self.camp_origin = "roam"
        self.shaker = tl.ShakeDetector()
        self.darkness = tl.DarkDetector()
        self.dark_room = False
        self.want_camp = False
        self.light = None
        self.shakes = 0
        self.store_from = "start"
        self.warned = False
        self.record = None
        self.result = None
        self.stone = 0
        self.help_page = 0
        self.saves = 0
        self.go("title")

    # ----- plumbing -------------------------------------------------------------
    def go(self, screen, cursor=None):
        if cursor is None:
            cursor = self.menu_cursor if screen == "menu" else 0
        self.screen = screen
        self.cursor = cursor
        self.note = ""
        self.want_menu = False
        if screen == "title":
            self.trail = None
            self.walk = None
            self.hunt = None
            self.over = False
            self.resume = None
            if self.save.get("run") is not None:
                self.resume = tl.Trail.from_dict(self.save["run"], self.rng)
                if self.resume is None:
                    self.save["run"] = None

    def persist(self):
        if self.persist_fn is None:
            return
        try:
            self.persist_fn(self.save)
            self.saves += 1
        except Exception:
            pass

    def save_run(self):
        trail = self.trail
        if trail is not None and not self.over and not trail.all_dead() and not trail.finished():
            self.save["run"] = trail.to_dict()
            self.saved_day = trail.day
        self.persist()

    def shutdown(self):
        trail = self.trail
        if trail is not None and not self.over and self.walk is not None:
            # Finish the step in progress so the save lands on a whole tile.
            self.walk = None
            _lines, outcome = trail.after_step()
            if outcome == "game_over":
                self.game_over()
                return
            if outcome == "victory":
                self.win()
                return
        if trail is not None and not self.over:
            self.save_run()
        else:
            self.persist()

    def toast(self, text):
        self.toasts.append([text, self.now + TOAST_MS])
        if len(self.toasts) > 3:
            self.toasts.pop(0)

    def current_toast(self):
        for index in range(len(self.toasts) - 1, -1, -1):
            text, until = self.toasts[index]
            if until > self.now:
                return text
        return None

    def visual(self):
        return self.save["visual"]

    def dark(self):
        return self.screen == "camp" or (self.dark_room and self.save["auto_camp"])

    def toggle_visual(self):
        self.save["visual"] = 1 - self.save["visual"]
        self.toast("Monitor: " + MONITORS[self.save["visual"]])
        self.persist()

    def menu_input(self, keys, options):
        count = len(options)
        if count == 0:
            return None
        if keys.hit("up"):
            self.cursor = (self.cursor - 1) % count
            self.note = ""
        if keys.hit("down"):
            self.cursor = (self.cursor + 1) % count
            self.note = ""
        if self.cursor >= count:
            self.cursor = count - 1
        if self.cursor < 0:
            self.cursor = 0
        return options[self.cursor]

    # ----- frame ----------------------------------------------------------------
    def update(self, now, keys=None, imu=None, light=None):
        if keys is None:
            keys = NO_KEYS
        now = int(now)
        dt = now - self.now
        if dt < 0:
            dt = 0
        elif dt > MAX_DT:
            dt = MAX_DT
        self.now = now
        self.sense(now, dt, imu, light)
        if keys.hit("menu"):
            self.toggle_visual()
        getattr(self, "_" + self.screen)(dt, keys)
        kept = []
        for toast in self.toasts:
            if toast[1] > now:
                kept.append(toast)
        self.toasts = kept

    def sense(self, now, dt, imu, light):
        if imu is not None and self.shaker.update(now, imu[0], imu[1], imu[2]):
            self.shakes += 1
            if self.screen == "roam":
                self.sprint(True)
        if light is not None:
            self.light = light
            change = self.darkness.update(now, dt, light)
            if change == "dark":
                self.dark_room = True
                self.want_camp = bool(self.save["auto_camp"])
            elif change == "light":
                self.dark_room = False
                self.want_camp = False

    # ----- run lifecycle ----------------------------------------------------------
    def reset_run(self):
        self.walk = None
        self.stride = 0
        self.last_dir = None
        self.bump = ""
        self.hunt = None
        self.over = False
        self.record = None
        self.result = None
        self.camp_auto = False
        self.saved_day = self.trail.day if self.trail is not None else 0

    def new_run(self, role):
        self.trail = tl.Trail(role, self.rng)
        self.reset_run()
        self.save["runs"] += 1
        self.save_run()
        self.store_from = "start"
        self.warned = False
        self.show_card("Your Studio party", (
            "Fresh in from Localhost, MO: Markus, Mona, Cameron, Hubot and Tufty.",
            "The GitHub Ducky pulls the wagon. Mona rides up front.",
            "It is %s. The Mainstage is %s steps away." % (
                self.trail.date_text(), tl.commas(tl.TRAIL_STEPS)),
        ), "store")

    def resume_run(self):
        trail = self.resume
        self.resume = None
        if trail is None:
            self.toast("That saved run could not be loaded.")
            self.go("title")
            return
        self.trail = trail
        self.reset_run()
        if trail.at == 0 and trail.steps == 0:
            self.open_store("start")
        elif trail.at_kind("river"):
            self.go("river")
        elif trail.at >= 0:
            self.open_menu("roam")
        else:
            self.go("roam")

    def game_over(self):
        trail = self.trail
        self.over = True
        self.walk = None
        record = trail.tombstone(self.rng.randint(0, len(tl.EPITAPHS) - 1))
        tl.add_tombstone(self.save, record)
        self.record = record
        self.save["run"] = None
        self.persist()

    def win(self):
        trail = self.trail
        self.over = True
        self.walk = None
        score = trail.score()
        best = score > self.save["best"]
        if best:
            self.save["best"] = score
        self.save["victories"] += 1
        self.result = (score, trail.living_count(), trail.day, trail.role, best)
        self.save["run"] = None
        self.persist()

    def show_card(self, title, lines, after, back=None):
        """Show paged event text, then go to after. back names the screen
        drawn behind the card ("roam" or "camp"), or None for a full page."""
        self.card_title = title
        self.card_lines = list(lines) if lines else [""]
        self.card_page = 0
        self.card_after = after
        self.card_back = back
        self.go("event")

    def card_pages(self):
        return max(1, (len(self.card_lines) + EVENT_PAGE - 1) // EVENT_PAGE)

    # ----- title ------------------------------------------------------------------
    def title_options(self):
        options = []
        if self.resume is not None:
            options.append(("Continue your run", "Step " + tl.commas(self.resume.steps), True, "continue"))
        options.append(("Start a new run", "", True, "new"))
        stones = len(self.save["tombstones"])
        options.append(("Visit the graveyard", str(stones), stones > 0, "graveyard"))
        options.append(("Monitor", MONITORS[self.save["visual"]], True, "visual"))
        options.append(("Dark Mode Camp sensor", "On" if self.save["auto_camp"] else "Off", True, "sensor"))
        options.append(("Learn how to play", "", True, "help"))
        return options

    def _title(self, dt, keys):
        option = self.menu_input(keys, self.title_options())
        action = option[3]
        toggle = action in ("visual", "sensor") and (keys.hit("left") or keys.hit("right"))
        if not (keys.hit("select") or toggle):
            return
        if not option[2]:
            self.note = "No tombstones yet. Give it time."
        elif action == "continue":
            self.resume_run()
        elif action == "new":
            self.go("role")
        elif action == "graveyard":
            self.stone = len(self.save["tombstones"]) - 1
            self.go("graveyard")
        elif action == "visual":
            self.toggle_visual()
        elif action == "sensor":
            self.save["auto_camp"] = not self.save["auto_camp"]
            if not self.save["auto_camp"]:
                self.want_camp = False
            self.persist()
        elif action == "help":
            self.help_page = 0
            self.go("help")

    def _view_title(self):
        save = self.save
        options = []
        for label, value, enabled, _action in self.title_options():
            options.append((label, value, enabled))
        lines = ("Gatehouse to the Universe Mainstage",
                 "Best %s   Runs %d   Wins %d" % (tl.commas(save["best"]), save["runs"], save["victories"]))
        view = View("title", "The Octocat Trail", lines, options, self.cursor, "UP/DOWN choose  SELECT go")
        view.note = self.note
        return view

    # ----- role -------------------------------------------------------------------
    def _role(self, dt, keys):
        self.menu_input(keys, tl.ROLES)
        if keys.hit("back"):
            self.go("title")
        elif keys.hit("select"):
            self.new_run(self.cursor)

    def _view_role(self):
        options = []
        for title, handle, _credits, _mult, _perk in tl.ROLES:
            options.append((title + " " + handle, "", True))
        role = tl.ROLES[self.cursor]
        view = View("menu", "Choose a role", ("Who leads the Studio party to the Mainstage?", "You can be:"),
                    options, self.cursor, "UP/DOWN choose  SELECT start  BACK title")
        view.foot = ("%s credits to start. Score x%d at the end." % (tl.commas(role[2]), role[3]), role[4])
        return view

    # ----- stores -----------------------------------------------------------------
    def open_store(self, origin):
        self.store_from = origin
        self.warned = False
        self.go("store")

    def store_name(self):
        at = self.trail.at
        for stop, name in STORE_NAMES:
            if stop == at:
                return name
        return "General Store"

    def store_options(self):
        trail = self.trail
        options = []
        for key in trail.store_keys():
            options.append((supply_label(key), tl.commas(int(trail.supplies[key])), True))
        options.append(("Hit the trail" if self.store_from == "start" else "Leave the store", "", True))
        return options

    def _store(self, dt, keys):
        trail = self.trail
        stock = trail.store_keys()
        self.menu_input(keys, self.store_options())
        index = self.cursor
        if keys.hit("back"):
            self.save_run()
            self.go("title" if self.store_from == "start" else "menu")
            return
        if index >= len(stock):
            if keys.hit("select"):
                self.leave_store()
            return
        key = stock[index]
        pack = tl.store_item(key)[2]
        if keys.hit("select") or keys.hit("right"):
            got = trail.buy(key, pack)
            if got:
                self.note = "Bought %s." % unit(key, got)
                self.warned = False
            elif trail.supplies[key] >= tl.carry_limit(key):
                self.note = "The wagon can't carry any more."
            else:
                self.note = "Not enough Copilot Credits."
        elif keys.hit("left"):
            back = trail.sell_back(key, pack)
            if back:
                self.note = "Returned %s." % unit(key, back)
            else:
                self.note = "Only this visit's purchases can go back."

    def leave_store(self):
        trail = self.trail
        if self.store_from != "start":
            self.save_run()
            self.go("menu")
            return
        if trail.supplies["brew"] <= 0 and not self.warned:
            self.warned = True
            self.note = "No cold brew packed! Leave again to go anyway."
            return
        trail.ticker = "The Ducky leans into the harness. Onward!"
        self.save_run()
        self.go("roam")

    def _view_store(self):
        trail = self.trail
        stock = trail.store_keys()
        stop = trail.current_stop()
        lines = [stop[0] if stop else "Fort Mason Center", trail.date_text()]
        markup = trail.markup()
        if markup > 100:
            lines.append("Venue markup: +%d%%" % (markup - 100))
        foot = []
        if self.cursor < len(stock):
            key = stock[self.cursor]
            _key, _price, pack, _carry, blurb = tl.store_item(key)
            foot.append("%s for %s credits." % (unit(key, pack), tl.commas(pack * trail.price(key))))
            foot.append(blurb)
        foot.append("Copilot Credits left: " + tl.commas(trail.supplies["credits"]))
        leave = "title" if self.store_from == "start" else "leave"
        view = View("store", self.store_name(), lines, self.store_options(), self.cursor,
                    "RIGHT buy  LEFT return  BACK " + leave)
        view.note = self.note
        view.foot = tuple(foot)
        return view

    # ----- free roam ----------------------------------------------------------------
    def sprint_state(self):
        trail = self.trail
        if trail.turbo_days > 0:
            return "Sprinting"
        if trail.turbo_cooldown > 0:
            return "Cooling %dd" % trail.turbo_cooldown
        if trail.supplies["brew"] <= 0:
            return "No brew"
        return "Ready"

    def sprint_block_note(self):
        state = self.sprint_state()
        if state == "Sprinting":
            return "Already sprinting."
        if state == "No brew":
            return "No cold brew to fuel a sprint."
        if state != "Ready":
            return "Sprint cooling down: %s left." % tl.plural(self.trail.turbo_cooldown, "day")
        return "Cross the river first."

    def sprint(self, by_shake=False):
        trail = self.trail
        if trail is None or self.over:
            return False
        if trail.start_sprint():
            self.toast("Shake detected: turbo sprint!" if by_shake else "Turbo sprint!")
            return True
        self.toast(self.sprint_block_note())
        return False

    def auto_camp_due(self):
        return self.want_camp and self.save["auto_camp"]

    def direction(self, keys):
        """The direction to walk: a fresh press wins, then the key held
        longest, then any held key."""
        for name, _dx, _dy in DIRS:
            if keys.hit(name):
                return name
        if self.last_dir is not None and keys.down(self.last_dir):
            return self.last_dir
        for name, _dx, _dy in DIRS:
            if keys.down(name):
                return name
        return None

    def try_step(self, name, keys, extra=0):
        trail = self.trail
        dx = 0
        dy = 0
        for entry in DIRS:
            if entry[0] == name:
                dx = entry[1]
                dy = entry[2]
        from_x = trail.x
        from_y = trail.y
        ms = trail.step(dx, dy)
        self.last_dir = name
        if ms <= 0:
            reason = trail.blocked_reason(dx, dy)
            if reason and (keys.hit(name) or reason != self.bump):
                self.toast(reason)
            self.bump = reason
            self.stride = 0
            return False
        self.bump = ""
        self.walk = [from_x, from_y, ms, min(extra, ms)]
        return True

    def _roam(self, dt, keys):
        trail = self.trail
        # Presses fire for one frame only, so take them mid-step too: BACK
        # sprints at once and SELECT waits for the step to land.
        if keys.hit("select"):
            self.want_menu = True
        elif keys.hit("back"):
            self.sprint()
        walk = self.walk
        extra = 0
        if walk is not None:
            walk[3] += dt
            self.stride += dt
            if walk[3] < walk[2]:
                return
            extra = walk[3] - walk[2]
            self.walk = None
            lines, outcome = trail.after_step()
            self.outcome(lines, outcome)
            if self.screen != "roam" or self.over:
                self.stride = 0
                return
        if self.want_menu:
            self.stride = 0
            if trail.at_kind("river"):
                self.go("river")
            else:
                self.open_menu("roam")
            return
        if self.auto_camp_due():
            self.start_camp(True, "roam")
            return
        name = self.direction(keys)
        if name is None:
            self.stride = 0
            self.bump = ""
            return
        self.try_step(name, keys, extra)

    def outcome(self, lines, outcome):
        """React to the end of a step (see Trail.after_step)."""
        trail = self.trail
        if outcome == "game_over":
            self.game_over()
            self.show_card(trail.date_text(), lines + ["Nobody is left to finish the trail."], "tombstone", "roam")
        elif outcome == "victory":
            self.win()
            if lines:
                self.show_card(trail.date_text(), lines, "victory", "roam")
            else:
                self.go("victory")
        elif outcome == "river":
            self.save_run()
            if lines:
                self.show_card(trail.date_text(), lines, "river", "roam")
            else:
                self.go("river")
        elif outcome == "stop":
            self.save_run()
            self.open_stop(lines)
        else:
            if trail.day - self.saved_day >= SAVE_EVERY_DAYS:
                self.save_run()
            if lines:
                self.show_card(trail.date_text(), lines, "roam", "roam")

    def party_px(self):
        """World pixel position of the party, sliding between tiles."""
        trail = self.trail
        x = trail.x * tm.TILE
        y = trail.y * tm.TILE
        walk = self.walk
        if walk is not None and walk[3] < walk[2]:
            left = walk[2] - walk[3]
            x -= (trail.x - walk[0]) * tm.TILE * left // walk[2]
            y -= (trail.y - walk[1]) * tm.TILE * left // walk[2]
        return x, y

    def walk_frame(self):
        if self.walk is None:
            return 0
        return (self.stride // WALK_FRAME_MS) & 1

    def next_text(self):
        trail = self.trail
        short = tm.STOPS[trail.next_stop()][1]
        away = trail.steps_to_next()
        if away < 0:
            return short
        if away == 0:
            return short + ", here"
        return "%s, %s steps" % (short, tl.commas(away))

    def status_rows(self):
        trail = self.trail
        return (
            ("Date", trail.date_text()),
            ("Weather", trail.weather()),
            ("Health", trail.party_health()),
            ("Cold brew", tl.plural(int(trail.supplies["brew"]), "keg")),
            ("Next stop", self.next_text()),
            ("Steps walked", tl.commas(trail.steps)),
        )

    def _view_roam(self):
        trail = self.trail
        view = View("roam", "", (), (), -1, "D-pad walk  SELECT menu  BACK sprint")
        view.rows = self.status_rows()
        if trail.turbo_days > 0:
            view.note = "Turbo sprint: %s left" % tl.plural(trail.turbo_days, "day")
        else:
            view.note = trail.ticker
        view.data = trail
        return view

    # ----- arriving at a stop -------------------------------------------------------
    def open_stop(self, lines):
        self.stop_lines = [tl.STOP_BLURBS[self.trail.at]] + list(lines)
        self.stop_page = 0
        self.go("stop")

    def stop_pages(self):
        return max(1, (len(self.stop_lines) + STOP_PAGE - 1) // STOP_PAGE)

    def _stop(self, dt, keys):
        if keys.hit("back"):
            self.go("roam")
        elif keys.hit("select") or keys.hit("right"):
            self.stop_page += 1
            if self.stop_page >= self.stop_pages():
                self.open_menu("roam")
        elif keys.hit("left") and self.stop_page > 0:
            self.stop_page -= 1

    def _view_stop(self):
        trail = self.trail
        pages = self.stop_pages()
        start = self.stop_page * STOP_PAGE
        more = self.stop_page + 1 < pages
        view = View("stop", tm.STOPS[trail.at][0], self.stop_lines[start:start + STOP_PAGE], (), -1,
                    "SELECT more  BACK walk on" if more else "SELECT look around  BACK walk on")
        view.foot = (trail.date_text(),)
        view.data = trail.at
        return view

    # ----- the size-up menu -----------------------------------------------------------
    def open_menu(self, origin):
        self.origin = origin
        self.menu_cursor = 0
        self.go("menu", 0)

    def menu_options(self):
        trail = self.trail
        river = self.origin == "river"
        options = [("Back to the river" if river else "Keep shipping", "", True, "leave"),
                   ("Check the wagon", "", True, "supplies"),
                   ("Look at the venue map", "", True, "map"),
                   ("Set the pace", tl.PACES[trail.pace][0], True, "pace"),
                   ("Set the rations", tl.RATIONS[trail.rations][0], True, "rations"),
                   ("Make camp and rest", "", True, "camp"),
                   ("Talk to attendees", "", True, "talk")]
        if trail.at_store():
            options.append(("Visit the store", "", True, "store"))
        stamps = int(trail.supplies["lgtm"])
        options.append(("Bug & AI Slop Hunt", tl.plural(stamps, "LGTM"), stamps > 0, "hunt"))
        options.append(("Turbo sprint", self.sprint_state(), trail.can_sprint() and not river, "sprint"))
        options.append(("Save and quit", "", True, "quit"))
        return options

    def leave_menu(self):
        if self.origin == "river" and self.trail.at_kind("river"):
            self.go("river")
        else:
            self.go("roam")

    def _menu(self, dt, keys):
        trail = self.trail
        option = self.menu_input(keys, self.menu_options())
        self.menu_cursor = self.cursor
        if keys.hit("back"):
            self.leave_menu()
            return
        if self.auto_camp_due():
            self.start_camp(True, "menu")
            return
        if not keys.hit("select"):
            return
        action = option[3]
        if not option[2]:
            if action == "hunt":
                self.note = "You need LGTM Stamps to hunt."
            else:
                self.note = self.sprint_block_note()
            return
        if action == "leave":
            self.leave_menu()
        elif action == "supplies":
            self.go("supplies")
        elif action == "map":
            self.go("map")
        elif action == "pace":
            self.go("pace", trail.pace)
        elif action == "rations":
            self.go("rations", trail.rations)
        elif action == "camp":
            self.start_camp(False, "menu")
        elif action == "talk":
            self.show_card("Talk to attendees", (self.rng.choice(SPEAKERS) + " says:", '"' + trail.tip() + '"'), "menu")
        elif action == "store":
            self.open_store("menu")
        elif action == "hunt":
            self.start_hunt()
        elif action == "sprint":
            self.go("roam")
            self.sprint()
        elif action == "quit":
            self.save_run()
            self.go("title")

    def _view_menu(self):
        trail = self.trail
        stop = trail.current_stop()
        lines = (trail.date_text(), "Weather: " + trail.weather(), "Health: " + trail.party_health(), "You can:")
        options = []
        for label, value, enabled, _action in self.menu_options():
            options.append((label, value, enabled))
        view = View("menu", stop[0] if stop else "Fort Mason Center", lines, options, self.cursor,
                    "UP/DOWN choose  SELECT go  BACK walk on")
        view.note = self.note
        return view

    # ----- the wagon and the map ----------------------------------------------------------
    def _supplies(self, dt, keys):
        if keys.hit("select") or keys.hit("back"):
            self.go("menu")

    def _view_supplies(self):
        trail = self.trail
        rows = []
        for key, label in tl.SUPPLIES:
            rows.append((label, tl.commas(int(trail.supplies[key]))))
        party = []
        for member in trail.members:
            party.append((member.name, member.status(), member.alive))
        view = View("supplies", "Your wagon", (), (), -1, "SELECT or BACK return")
        view.rows = tuple(rows)
        view.data = tuple(party)
        view.foot = ("The party drinks %s kegs a day." % kegs(trail.brew_per_day()),)
        return view

    def _map(self, dt, keys):
        if keys.hit("select") or keys.hit("back"):
            self.go("menu")

    def _view_map(self):
        trail = self.trail
        away = trail.steps_to_next()
        if away < 0:
            where = "Find a way across"
        elif away == 0:
            where = "You are here"
        else:
            where = tl.commas(away) + " steps away"
        lines = ("Next stop: " + tm.STOPS[trail.next_stop()][1], where, "Walked: %s steps" % tl.commas(trail.steps))
        view = View("map", "Fort Mason Center", lines, (), -1, "SELECT or BACK return")
        view.data = trail
        return view

    # ----- pace and rations -------------------------------------------------------------
    def choose(self, keys, table, field, label):
        self.menu_input(keys, table)
        if keys.hit("back"):
            self.go("menu")
        elif keys.hit("select"):
            setattr(self.trail, field, self.cursor)
            self.toast("%s: %s" % (label, table[self.cursor][0]))
            self.save_run()
            self.go("menu")

    def _pace(self, dt, keys):
        self.choose(keys, tl.PACES, "pace", "Pace")

    def _view_pace(self):
        options = []
        for name, steps, _health in tl.PACES:
            options.append((name, "%d steps/day" % steps, True))
        view = View("menu", "Set the pace", ("The pace is %s." % tl.PACES[self.trail.pace][0], "You can pick:"),
                    options, self.cursor, "UP/DOWN choose  SELECT set  BACK cancel")
        view.foot = (PACE_NOTES[self.cursor],)
        return view

    def _rations(self, dt, keys):
        self.choose(keys, tl.RATIONS, "rations", "Rations")

    def _view_rations(self):
        options = []
        for name, amount, _health in tl.RATIONS:
            options.append((name, kegs(amount) + " kegs each", True))
        view = View("menu", "Set the rations", ("The rations are %s." % tl.RATIONS[self.trail.rations][0],
                                                "You can pick:"),
                    options, self.cursor, "UP/DOWN choose  SELECT set  BACK cancel")
        view.foot = (RATION_NOTES[self.cursor],)
        return view

    # ----- Production Deployment rivers ---------------------------------------------------
    def river_value(self, option):
        trail = self.trail
        if option == tl.WAIT:
            return "1 day"
        risk = "%d%%" % int(trail.crossing_risk(option) * 100 + 0.5)
        if option == tl.CAULK:
            return "2 LGTMs, " + risk
        if option == tl.FERRY:
            return "%d cr, %s" % (trail.ferry_cost(), risk)
        return risk

    def river_options(self):
        trail = self.trail
        options = []
        for index in range(len(tl.RIVER_OPTIONS)):
            options.append((tl.RIVER_OPTIONS[index], self.river_value(index), trail.river_option_ok(index)))
        options.append(("Plan it out", "", True))
        return options

    def _river(self, dt, keys):
        trail = self.trail
        self.menu_input(keys, self.river_options())
        if keys.hit("back"):
            self.go("roam")
            return
        if self.auto_camp_due():
            self.start_camp(True, "river")
            return
        if not keys.hit("select"):
            return
        option = self.cursor
        if option >= len(tl.RIVER_OPTIONS):
            self.open_menu("river")
            return
        if not trail.river_option_ok(option):
            if option == tl.CAULK:
                self.note = "You need 2 LGTM Stamps to ship it."
            else:
                self.note = "Not enough Copilot Credits for the ferry."
            return
        stop = trail.at
        name = tm.STOPS[stop][0]
        lines, crossed = trail.cross(option)
        if trail.all_dead():
            self.game_over()
            self.show_card(name, lines + ["Nobody is left to finish the trail."], "tombstone")
        elif not crossed:
            self.save_run()
            self.show_card(name, lines, "river")
        else:
            failed = False
            for line in lines:
                if line.startswith("The deploy failed"):
                    failed = True
            self.cross_stop = stop
            self.cross_option = option
            self.cross_lines = lines
            self.cross_failed = failed
            self.cross_ms = 0
            self.cross_name = name
            self.go("crossing")

    def _view_river(self):
        trail = self.trail
        river = trail.river or (0, 0)
        lines = (trail.date_text(), "Weather: " + trail.weather(),
                 "Diff: %s ft wide, %s ft deep" % (tl.commas(river[1]), tl.tenths(river[0])), "You can:")
        view = View("river", tm.STOPS[trail.at][0], lines, self.river_options(), self.cursor,
                    "UP/DOWN choose  SELECT go  BACK walk on")
        view.note = self.note
        view.data = trail.at
        return view

    def _crossing(self, dt, keys):
        self.cross_ms += dt
        if self.cross_ms >= CROSS_MS or keys.hit("select") or keys.hit("back"):
            self.save_run()
            self.show_card(self.cross_name, self.cross_lines, "roam", "roam")

    def _view_crossing(self):
        view = View("crossing", self.cross_name, (tl.RIVER_OPTIONS[self.cross_option],), (), -1, "SELECT skip",
                    min(1.0, self.cross_ms / float(CROSS_MS)))
        view.data = (self.cross_stop, self.cross_option, self.cross_failed)
        return view

    # ----- Bug & AI Slop Hunt ------------------------------------------------------------
    def start_hunt(self):
        self.hunt = self.trail.start_hunt()
        self.go("hunt")

    def _hunt(self, dt, keys):
        hunt = self.hunt
        if keys.hit("back"):
            hunt.finish()
        if not hunt.done:
            right = keys.down("right") or keys.hit("right")
            left = keys.down("left") or keys.hit("left")
            down = keys.down("down") or keys.hit("down")
            up = keys.down("up") or keys.hit("up")
            dx = (1 if right else 0) - (1 if left else 0)
            dy = (1 if down else 0) - (1 if up else 0)
            hunt.update(dt, dx, dy, keys.hit("select"))
        if hunt.done:
            self.end_hunt()

    def end_hunt(self):
        trail = self.trail
        lines = trail.finish_hunt(self.hunt)
        self.hunt = None
        if trail.all_dead():
            self.game_over()
            self.show_card("Bug & AI Slop Hunt", lines + ["Nobody is left to finish the trail."], "tombstone")
        else:
            self.save_run()
            self.show_card("Bug & AI Slop Hunt", lines, "menu")

    def _view_hunt(self):
        hunt = self.hunt
        view = View("hunt", "Bug & AI Slop Hunt", (), (), -1, "D-pad walk  SELECT stamp  BACK stop",
                    hunt.remaining_ms() / float(tl.HUNT_MS))
        view.data = hunt
        return view

    # ----- Dark Mode Camp ----------------------------------------------------------------
    def start_camp(self, auto, origin):
        self.camp_auto = auto
        self.camp_days = 0
        self.camp_timer = 0
        self.camp_origin = origin
        self.walk = None
        self.stride = 0
        if auto:
            self.want_camp = False
        self.go("camp")

    def break_camp(self, by_hand):
        if self.camp_auto and by_hand:
            self.darkness.suppress()
        self.camp_auto = False
        self.want_camp = False
        self.save_run()
        self.go(self.camp_origin)

    def _camp(self, dt, keys):
        trail = self.trail
        if keys.hit("select") or keys.hit("back"):
            self.break_camp(True)
            return
        if self.want_camp and not self.camp_auto:
            self.camp_auto = True
            self.want_camp = False
        if self.camp_auto and not self.dark_room:
            self.toast("The lights are back on. Break camp!")
            self.break_camp(False)
            return
        if not self.camp_auto and self.camp_days >= MAX_CAMP_DAYS:
            self.break_camp(False)
            return
        self.camp_timer += dt
        if self.camp_timer < CAMP_DAY_MS:
            return
        self.camp_timer = 0
        self.camp_days += 1
        lines = trail.rest_day()
        if trail.all_dead():
            self.game_over()
            self.show_card("Dark Mode Camp", lines + ["Nobody is left to finish the trail."], "tombstone", "camp")
        elif lines:
            self.show_card("Dark Mode Camp", lines, "camp", "camp")

    def _view_camp(self):
        trail = self.trail
        if self.camp_auto:
            lines = ["Lights out. The party rests until the room is bright again."]
        else:
            lines = ["Resting: day %d of %d." % (min(self.camp_days + 1, MAX_CAMP_DAYS), MAX_CAMP_DAYS)]
        if self.camp_days:
            lines.append("Health: %s. Rested %s." % (trail.party_health(), tl.plural(self.camp_days, "day")))
        else:
            lines.append("Health: %s." % trail.party_health())
        view = View("camp", "Dark Mode Camp", lines, (), -1, "SELECT break camp",
                    min(1.0, self.camp_timer / float(CAMP_DAY_MS)))
        view.data = self.camp_auto
        return view

    # ----- event cards ---------------------------------------------------------------------
    def _event(self, dt, keys):
        if keys.hit("back"):
            self.go(self.card_after)
        elif keys.hit("select") or keys.hit("right"):
            self.card_page += 1
            if self.card_page >= self.card_pages():
                self.go(self.card_after)
        elif keys.hit("left") and self.card_page > 0:
            self.card_page -= 1

    def _view_event(self):
        pages = self.card_pages()
        start = self.card_page * EVENT_PAGE
        hint = "SELECT more" if self.card_page + 1 < pages else "SELECT continue"
        if pages > 1:
            hint = "%d/%d  %s" % (self.card_page + 1, pages, hint)
        view = View("card", self.card_title, self.card_lines[start:start + EVENT_PAGE], (), -1, hint)
        view.data = self.card_back
        return view

    # ----- tombstones, victories and IR ------------------------------------------------------
    def nonce(self):
        return self.link.nonce if self.link is not None else 0

    def beam(self, packet, what):
        link = self.link
        if link is None:
            self.toast("IR is not available on this badge.")
            return False
        if link.sending():
            self.toast("Still beaming. Hold steady.")
            return False
        link.beam(packet)
        self.save["beamed"] += 1
        self.persist()
        if link.can_send():
            self.toast("Beaming your %s over IR." % what)
        else:
            self.toast("No IR: %s beam simulated." % what)
        return True

    def beam_progress(self):
        link = self.link
        if link is None or not link.sending():
            return None
        return link.progress()

    def receive(self, packets):
        changed = False
        for packet in packets:
            record = tl.tombstone_from_packet(packet)
            if record is not None:
                tl.add_tombstone(self.save, record)
                self.toast("Tombstone beamed in: step %s." % tl.commas(record[0]))
                changed = True
                continue
            victory = tl.victory_from_packet(packet)
            if victory is not None:
                score = victory[0]
                self.toast("Victory beamed in: %s points!" % tl.commas(score))
                changed = True
        if changed:
            self.save["met"] += 1
            self.persist()
        return changed

    def _tombstone(self, dt, keys):
        record = self.record
        if keys.hit("left") or keys.hit("right"):
            step = 1 if keys.hit("right") else -1
            record[2] = (record[2] + step) % len(tl.EPITAPHS)
        elif keys.hit("select"):
            self.persist()
            self.beam(tl.tombstone_packet(self.nonce(), record), "tombstone")
        elif keys.hit("back"):
            self.persist()
            self.go("title")

    def _view_tombstone(self):
        return View("tombstone", "Game over", tl.tombstone_lines(self.record), (), -1,
                    "L/R epitaph  SELECT beam  BACK title", self.beam_progress())

    def _victory(self, dt, keys):
        score, survivors, days, role, _best = self.result
        if keys.hit("select"):
            self.beam(tl.victory_packet(self.nonce(), score, survivors, days, role), "victory")
        elif keys.hit("back"):
            self.go("title")

    def _view_victory(self):
        score, survivors, days, role, best = self.result
        lines = ("Final score: %s%s" % (tl.commas(score), "  New best!" if best else ""),
                 "%d of %d made it in %s." % (survivors, len(tl.PARTY), tl.plural(days, "day")),
                 "%s, score x%d" % (tl.role_label(role), tl.ROLES[role][3]))
        return View("victory", "You made it to the Mainstage!", lines, (), -1,
                    "SELECT beam victory  BACK title", self.beam_progress())

    def _graveyard(self, dt, keys):
        stones = self.save["tombstones"]
        if not stones or keys.hit("back"):
            self.go("title")
            return
        count = len(stones)
        if keys.hit("left"):
            self.stone -= 1
        elif keys.hit("right"):
            self.stone += 1
        self.stone %= count
        if keys.hit("select"):
            self.beam(tl.tombstone_packet(self.nonce(), stones[self.stone]), "tombstone")

    def _view_graveyard(self):
        stones = self.save["tombstones"]
        if not stones:
            return View("tombstone", "Graveyard", ("No tombstones yet.",), (), -1, "BACK title")
        index = self.stone % len(stones)
        return View("tombstone", "Graveyard %d/%d" % (index + 1, len(stones)), tl.tombstone_lines(stones[index]),
                    (), -1, "L/R browse  SELECT beam  BACK title", self.beam_progress())

    # ----- help ------------------------------------------------------------------------------
    def _help(self, dt, keys):
        if keys.hit("back"):
            self.go("title", len(self.title_options()) - 1)
        elif keys.hit("select") or keys.hit("right"):
            self.help_page += 1
            if self.help_page >= len(HELP):
                self.go("title", len(self.title_options()) - 1)
        elif keys.hit("left") and self.help_page > 0:
            self.help_page -= 1

    def _view_help(self):
        title, lines = HELP[self.help_page]
        return View("help", "%s  (%d/%d)" % (title, self.help_page + 1, len(HELP)), lines, (), -1,
                    "SELECT next  LEFT back  BACK title")

    # ----- outputs for the renderer and the hardware ------------------------------------------
    def view(self):
        return getattr(self, "_view_" + self.screen)()

    def lights(self):
        """Case light levels (0-1) for the four corners."""
        now = self.now
        link = self.link
        if link is not None and link.sending():
            lit = (now // 120) % 4
            levels = [0.05, 0.05, 0.05, 0.05]
            levels[lit] = 0.5
            return tuple(levels)
        if self.screen == "camp":
            flicker = 0.08 + ((now // 90) * 37 % 9) / 100.0
            return (flicker, flicker * 0.6, flicker * 0.6, flicker)
        if self.screen == "victory":
            lit = (now // 250) % 4
            levels = [0.1, 0.1, 0.1, 0.1]
            levels[lit] = 0.4
            return tuple(levels)
        trail = self.trail
        if self.screen == "roam" and trail is not None and trail.turbo_days > 0:
            level = 0.3 if (now // 250) & 1 else 0.1
            return (level, level, level, level)
        return (0, 0, 0, 0)
