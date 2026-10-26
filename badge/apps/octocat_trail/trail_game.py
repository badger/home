"""Screen flow for The Octocat Trail.

A pure controller: update() takes the clock, a Keys snapshot and optional
sensor readings, drives the rules in trail_logic across the venue map in
trail_map, and describes each screen as a View for trail_draw to render. It
never touches the badge runtime, so CPython tests can play the whole game
with fake keys.
"""

import trail_logic as tl

TOAST_MS = 3500
MAX_DT = 250
EVENT_PAGE = 3
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
        self.menu_cursor = 0
        self.card_title = ""
        self.card_lines = [""]
        self.card_page = 0
        self.card_after = "title"
        self.card_back = None
        self.walk = None
        self.stride = 0
        self.last_dir = None
        self.bump = ""
        self.saved_day = 0
        self.hunt = None
        self.toasts = []
        self.camp_auto = False
        self.darkness = tl.DarkDetector()
        self.dark_room = False
        self.want_camp = False
        self.light = None
        self.store_from = "start"
        self.warned = False
        self.record = None
        self.result = None
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
        if trail.supplies["brew"] <= 0 and not self.warned:
            self.warned = True
            self.note = "No cold brew packed! Leave again to go anyway."
            return
        trail.ticker = "The Ducky leans into the harness. Onward!"
        self.save_run()

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
