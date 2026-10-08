import random
import struct

import hints
from badgeware import State
from badgeware import link as badgelink

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

GAME = "pong"
STATE_KEY = "pong"

WIDTH = 320
HEIGHT = 240
COURT_TOP = 34
COURT_BOTTOM = 236
CENTRE_X = WIDTH / 2

PADDLE_WIDTH = 6
PADDLE_HEIGHT = 44
PADDLE_INSET = 10
PADDLE_SPEED = 230
MY_PADDLE_X = PADDLE_INSET
THEIR_PADDLE_X = WIDTH - PADDLE_INSET - PADDLE_WIDTH
BALL_SIZE = 6

SERVE_SPEED = 150
SPEED_STEP = 1.06
MAX_SPEED = 330
MAX_ANGLE = 0.8
SERVE_DELAY_MS = 900
POINT_PAUSE_MS = 1000
COUNTDOWN_MS = 2400
WINNING_SCORE = 5

PADDLE_SEND_MS = 60
PING_MS = 700
MAX_AGE_MS = 200
OFFER_MS = 15000
MAX_FRAME_MS = 100
CORRECTION_EASE = 25
FIXED = 16

MSG_ACCEPT = b"A"
MSG_DECLINE = b"D"
MSG_REMATCH = b"R"
MSG_SERVE = b"S"
MSG_HIT = b"H"
MSG_CROSS = b"X"
MSG_POINT = b"M"
MSG_PADDLE = b"Y"
MSG_PING = b"P"
MSG_PONG = b"Q"

BALL_FORMAT = "<hhhI"
BALL_BYTES = 10

black = color.rgb(0, 0, 0)
white = color.rgb(255, 255, 255)
dim_white = color.rgb(255, 255, 255, 140)
faint_white = color.rgb(255, 255, 255, 60)
court_line = color.rgb(255, 255, 255, 50)
accent = color.rgb(15, 191, 62)

title_font = font.ignore
name_font = font.ziplock
body_font = font.corset
score_font = font.more

TITLE_X = 8
TITLE_Y = 202
HINT_STYLE = hints.Style(white, dim_white, black)
HINT_RADIUS = 4


def clamp(value, low, high):
    return max(low, min(high, value))


def fit(text, width):
    while text and screen.measure_text(text)[0] > width:
        text = text[:-1]
    return text


def centred(text, y, typeface, pen):
    screen.font = typeface
    screen.pen = pen
    text = fit(text, WIDTH - 16)
    width, _ = screen.measure_text(text)
    screen.text(text, (WIDTH - width) / 2, y)


def draw_ribbon(title):
    screen.font = title_font
    screen.pen = white
    screen.text(title, TITLE_X, TITLE_Y)


def draw_hint(label, shape, right):
    screen.font = body_font
    label_width, _ = screen.measure_text(label)
    dots_width = hints.hint_width(shape, HINT_RADIUS)
    left = right - label_width - 6 - dots_width
    hints.draw_hint(HINT_STYLE, shape, shape, left + dots_width / 2, 219, HINT_RADIUS)
    screen.pen = dim_white
    screen.text(label, left + dots_width + 6, 213)
    return left - 12


def draw_hints(*pairs):
    right = WIDTH - TITLE_X
    for label, shape in pairs:
        right = draw_hint(label, shape, right)


def pack_ball(kind, y, vx, vy, now):
    return kind + struct.pack(BALL_FORMAT, round(y * FIXED), round(vx * FIXED), round(vy * FIXED), now & 0xFFFFFFFF)


def mirror_x(x):
    return WIDTH - x - BALL_SIZE


def unpack_ball(body):
    y, vx, vy, sent = struct.unpack(BALL_FORMAT, body)
    return y / FIXED, vx / FIXED, vy / FIXED, sent


class Ball:
    def __init__(self):
        self.x = CENTRE_X
        self.y = (COURT_TOP + COURT_BOTTOM) / 2
        self.vx = 0.0
        self.vy = 0.0

    def set(self, x, y, vx, vy):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy

    def step(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y < COURT_TOP:
            self.y = COURT_TOP + (COURT_TOP - self.y)
            self.vy = abs(self.vy)
        elif self.y > COURT_BOTTOM - BALL_SIZE:
            self.y = (COURT_BOTTOM - BALL_SIZE) * 2 - self.y
            self.vy = -abs(self.vy)


class Record:
    def __init__(self):
        self.data = {"wins": 0, "losses": 0}
        State.load(STATE_KEY, self.data)

    def add(self, won):
        self.data["wins" if won else "losses"] += 1
        State.save(STATE_KEY, self.data)


class Pong:
    LOBBY = 0
    OFFER = 1
    COUNTDOWN = 2
    PLAY = 3
    OVER = 4

    def __init__(self):
        self.link = badgelink.Link(GAME)
        self.proximity = badgelink.Proximity(self.link)
        self.record = Record()
        self.mode = self.LOBBY
        self.mode_at = 0
        self.was_linked = False
        self.message = ""
        self.my_accept = False
        self.their_accept = False
        self.ball = Ball()
        self.my_paddle = (COURT_TOP + COURT_BOTTOM - PADDLE_HEIGHT) / 2
        self.their_paddle = self.my_paddle
        self.their_paddle_target = self.my_paddle
        self.my_score = 0
        self.their_score = 0
        self.owner_is_me = False
        self.serving = False
        self.serve_at = 0
        self.point_until = 0
        self.first_server_is_me = False
        self.last_paddle_sent = None
        self.paddle_sent_at = 0
        self.ping_at = 0
        self.rtt = None
        self.clock_offset = 0
        self.correction_x = 0.0
        self.correction_y = 0.0
        self.glow = 0.0

    def set_mode(self, mode, now):
        self.mode = mode
        self.mode_at = now

    def send(self, message):
        self.link.send(message)

    def leave(self, now, message=""):
        partner = self.link.partner
        self.proximity.rest(partner.id if partner else None, now)
        self.link.leave()
        self.message = message
        self.set_mode(self.LOBBY, now)

    def age_ms(self, sent, now):
        return clamp(now - (sent - self.clock_offset), 0, MAX_AGE_MS)

    def update(self, now, dt):
        self.link.pump()
        linked = self.link.linked
        if linked and not self.was_linked:
            if self.mode == self.LOBBY:
                self.my_accept = False
                self.their_accept = False
                self.message = ""
                self.rtt = None
                self.set_mode(self.OFFER, now)
            else:
                self.link.leave()
        if self.was_linked and not linked and self.mode != self.LOBBY:
            self.proximity.clear()
            self.message = "they walked away"
            self.set_mode(self.LOBBY, now)
        self.was_linked = linked

        if linked:
            for message in self.link.receive():
                self.handle(message, now)

        if self.mode == self.LOBBY:
            self.proximity.update(now)
            if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
                reset()
        elif self.mode == self.OFFER:
            self.offer_frame(now)
        elif self.mode == self.COUNTDOWN:
            self.move_paddle(dt)
            if now - self.mode_at >= COUNTDOWN_MS:
                self.start_play(now, self.first_server_is_me)
        elif self.mode == self.PLAY:
            self.play_frame(now, dt)
        elif self.mode == self.OVER:
            self.over_frame(now)

        if self.mode in (self.COUNTDOWN, self.PLAY):
            self.their_paddle += (self.their_paddle_target - self.their_paddle) * min(1.0, dt * 20)
            self.stream_paddle(now)
            if now - self.ping_at >= PING_MS:
                self.ping_at = now
                self.send(MSG_PING + struct.pack("<I", now & 0xFFFFFFFF))
        self.link.update()

        self.glow *= 0.93
        lights = self.proximity.lights(now) if self.mode == self.LOBBY else None
        if lights is None:
            badge.caselights(min(0.5, self.glow))
        else:
            badge.caselights(*lights)

    def handle(self, message, now):
        kind = message[:1]
        body = message[1:]
        if kind == MSG_ACCEPT:
            self.their_accept = True
        elif kind == MSG_DECLINE:
            self.leave(now, "they said no thanks")
        elif kind == MSG_REMATCH:
            self.their_accept = True
        elif kind == MSG_PADDLE and len(body) == 2:
            self.their_paddle_target = struct.unpack("<h", body)[0] / FIXED
        elif kind == MSG_PING and len(body) == 4:
            self.send(MSG_PONG + body + struct.pack("<I", now & 0xFFFFFFFF))
        elif kind == MSG_PONG and len(body) == 8:
            sent, replied = struct.unpack("<II", body)
            sample = now - sent
            if self.rtt is None or sample <= self.rtt:
                self.rtt = sample
                self.clock_offset = replied - (sent + now) / 2
        elif self.mode == self.PLAY:
            self.handle_play(kind, body, now)

    def handle_play(self, kind, body, now):
        if kind in (MSG_SERVE, MSG_HIT, MSG_CROSS) and len(body) == BALL_BYTES:
            y, vx, vy, sent = unpack_ball(body)
            x = CENTRE_X if kind == MSG_CROSS else MY_PADDLE_X + PADDLE_WIDTH
            shown_x = self.ball.x + self.correction_x
            shown_y = self.ball.y + self.correction_y
            self.ball.set(mirror_x(x), y, -vx, vy)
            self.ball.step(self.age_ms(sent, now) / 1000)
            if not self.serving:
                self.correction_x = shown_x - self.ball.x
                self.correction_y = shown_y - self.ball.y
            self.serving = False
            self.owner_is_me = kind == MSG_CROSS
        elif kind == MSG_POINT:
            self.my_score += 1
            self.glow = 0.5
            self.point(now, server_is_me=False)

    def offer_frame(self, now):
        if badge.pressed(BUTTON_SELECT) and not self.my_accept:
            self.my_accept = True
            self.send(MSG_ACCEPT)
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
            self.send(MSG_DECLINE)
            self.leave(now)
            return
        if self.my_accept and self.their_accept:
            self.start_match(now, self.link.central)
        elif now - self.mode_at > OFFER_MS:
            self.send(MSG_DECLINE)
            self.leave(now, "nobody pressed play")

    def start_match(self, now, server_is_me):
        self.first_server_is_me = server_is_me
        self.my_score = 0
        self.their_score = 0
        self.my_accept = False
        self.their_accept = False
        self.set_mode(self.COUNTDOWN, now)

    def start_play(self, now, server_is_me):
        self.set_mode(self.PLAY, now)
        self.point(now, server_is_me, pause=False)

    def point(self, now, server_is_me, pause=True):
        self.correction_x = 0.0
        self.correction_y = 0.0
        if self.my_score >= WINNING_SCORE or self.their_score >= WINNING_SCORE:
            self.record.add(self.my_score > self.their_score)
            self.set_mode(self.OVER, now)
            return
        self.owner_is_me = server_is_me
        self.serving = True
        self.point_until = now + POINT_PAUSE_MS if pause else now
        self.serve_at = self.point_until + SERVE_DELAY_MS

    def move_paddle(self, dt):
        step = 0
        if badge.held(BUTTON_UP):
            step -= 1
        if badge.held(BUTTON_DOWN):
            step += 1
        self.my_paddle = clamp(self.my_paddle + step * PADDLE_SPEED * dt, COURT_TOP, COURT_BOTTOM - PADDLE_HEIGHT)

    def stream_paddle(self, now):
        if now - self.paddle_sent_at < PADDLE_SEND_MS:
            return
        position = round(self.my_paddle * FIXED)
        if position == self.last_paddle_sent:
            return
        self.send(MSG_PADDLE + struct.pack("<h", position))
        self.last_paddle_sent = position
        self.paddle_sent_at = now

    def play_frame(self, now, dt):
        self.move_paddle(dt)
        ease = max(0.0, 1 - dt * CORRECTION_EASE)
        self.correction_x *= ease
        self.correction_y *= ease
        if now < self.point_until:
            return
        ball = self.ball
        if self.serving:
            if self.owner_is_me:
                ball.set(MY_PADDLE_X + PADDLE_WIDTH, self.my_paddle + (PADDLE_HEIGHT - BALL_SIZE) / 2, 0, 0)
                if now >= self.serve_at:
                    self.serve()
            else:
                ball.set(THEIR_PADDLE_X - BALL_SIZE, self.their_paddle + (PADDLE_HEIGHT - BALL_SIZE) / 2, 0, 0)
            return
        previous_x = ball.x
        ball.step(dt)
        if self.owner_is_me:
            self.owned_frame(now, previous_x)
        elif ball.x + BALL_SIZE >= THEIR_PADDLE_X:
            ball.x = THEIR_PADDLE_X - BALL_SIZE

    def serve(self):
        angle = random.uniform(-0.5, 0.5)
        self.ball.vx = SERVE_SPEED
        self.ball.vy = SERVE_SPEED * angle
        self.serving = False
        self.send(pack_ball(MSG_SERVE, self.ball.y, self.ball.vx, self.ball.vy, badge.ticks))

    def owned_frame(self, now, previous_x):
        ball = self.ball
        paddle_face = MY_PADDLE_X + PADDLE_WIDTH
        if ball.vx < 0 and ball.x <= paddle_face <= previous_x:
            centre = ball.y + BALL_SIZE / 2
            if self.my_paddle - BALL_SIZE <= centre - BALL_SIZE / 2 <= self.my_paddle + PADDLE_HEIGHT:
                offset = clamp((centre - (self.my_paddle + PADDLE_HEIGHT / 2)) / (PADDLE_HEIGHT / 2), -1, 1)
                speed = min(MAX_SPEED, abs(ball.vx) * SPEED_STEP)
                ball.x = paddle_face
                ball.vx = speed
                ball.vy = speed * offset * MAX_ANGLE
                self.glow = 0.25
                self.send(pack_ball(MSG_HIT, ball.y, ball.vx, ball.vy, now))
                return
        if ball.x + BALL_SIZE < 0:
            self.their_score += 1
            self.send(MSG_POINT)
            self.point(now, server_is_me=True)
            return
        if ball.vx > 0 and ball.x >= CENTRE_X > previous_x:
            ball.x = CENTRE_X
            self.owner_is_me = False
            self.send(pack_ball(MSG_CROSS, ball.y, ball.vx, ball.vy, now))

    def over_frame(self, now):
        if badge.pressed(BUTTON_SELECT) and not self.my_accept:
            self.my_accept = True
            self.send(MSG_REMATCH)
        elif badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_BACK):
            self.leave(now)
            return
        if self.my_accept and self.their_accept:
            self.start_match(now, self.my_score < self.their_score)

    def draw(self, now):
        screen.pen = black
        screen.clear()
        if self.mode == self.LOBBY:
            self.draw_lobby(now)
        elif self.mode == self.OFFER:
            self.draw_offer(now)
        elif self.mode == self.OVER:
            self.draw_over()
        else:
            self.draw_court(now)

    def draw_lobby(self, now):
        badgelink.draw_identicon(screen, self.link.id, (WIDTH - 56) // 2, 14, 56)
        centred(self.link.name, 78, name_font, white)
        peer = self.proximity.syncing()
        remaining = self.proximity.cooling(now)
        if peer is not None:
            progress = self.proximity.progress(now)
            centred("connecting..." if progress >= 1.0 else "syncing with " + peer.name, 118, name_font, white)
            screen.pen = faint_white
            screen.rectangle(TITLE_X, 148, WIDTH - TITLE_X * 2, 8)
            screen.pen = accent
            screen.rectangle(TITLE_X, 148, int((WIDTH - TITLE_X * 2) * progress), 8)
        elif remaining is not None:
            centred("pull apart to play again", 124, name_font, dim_white)
        else:
            centred("hold badges back to back", 118, name_font, white)
            centred("to play pong", 146, body_font, dim_white)
        if self.message:
            centred(self.message, 166, body_font, dim_white)
        record = self.record.data
        centred("won %d  lost %d" % (record["wins"], record["losses"]), 182, body_font, dim_white)
        draw_ribbon("pong")
        draw_hints(("menu", (BUTTON_LEFT,)))

    def draw_partner(self, status, pen):
        partner = self.link.partner
        if partner is None:
            return
        badgelink.draw_identicon(screen, partner.id, (WIDTH - 70) // 2, 14, 70)
        centred(partner.name, 94, name_font, white)
        centred(status, 122, body_font, pen)

    def draw_offer(self, now):
        if self.my_accept:
            status = "waiting for them..."
        elif self.their_accept:
            status = "they want to play"
        else:
            status = "play pong?"
        self.draw_partner(status, accent if self.their_accept else dim_white)
        remaining = max(0, OFFER_MS - (now - self.mode_at))
        screen.pen = faint_white
        screen.rectangle(TITLE_X, 156, int((WIDTH - TITLE_X * 2) * remaining / OFFER_MS), 4)
        draw_ribbon("pong")
        if self.my_accept:
            draw_hints(("cancel", (BUTTON_LEFT,)))
        else:
            draw_hints(("play", (BUTTON_SELECT,)), ("no thanks", (BUTTON_LEFT,)))

    def draw_over(self):
        won = self.my_score > self.their_score
        centred("you win!" if won else "they win", 40, name_font, accent if won else white)
        centred("%d - %d" % (self.my_score, self.their_score), 70, score_font, white)
        if self.their_accept and not self.my_accept:
            centred("they want a rematch", 150, body_font, accent)
        elif self.my_accept:
            centred("waiting for them...", 150, body_font, dim_white)
        draw_ribbon("pong")
        if self.my_accept:
            draw_hints(("leave", (BUTTON_LEFT,)))
        else:
            draw_hints(("rematch", (BUTTON_SELECT,)), ("leave", (BUTTON_LEFT,)))

    def draw_court(self, now):
        screen.pen = court_line
        for y in range(COURT_TOP, COURT_BOTTOM, 12):
            screen.rectangle(CENTRE_X - 1, y, 2, 6)
        screen.rectangle(0, COURT_TOP - 2, WIDTH, 1)
        screen.font = score_font
        screen.pen = dim_white
        mine = str(self.my_score)
        width, _ = screen.measure_text(mine)
        screen.text(mine, CENTRE_X - 16 - width, 0)
        screen.text(str(self.their_score), CENTRE_X + 16, 0)

        my_ink, _ = badgelink.identicon(self.link.id)[1:]
        partner = self.link.partner
        their_ink = badgelink.identicon(partner.id)[1] if partner else white
        screen.pen = my_ink
        screen.rectangle(MY_PADDLE_X, self.my_paddle, PADDLE_WIDTH, PADDLE_HEIGHT)
        screen.pen = their_ink
        screen.rectangle(THEIR_PADDLE_X, self.their_paddle, PADDLE_WIDTH, PADDLE_HEIGHT)

        if self.mode == self.COUNTDOWN:
            remaining = COUNTDOWN_MS - (now - self.mode_at)
            centred(str(max(1, int(remaining / (COUNTDOWN_MS / 3)) + 1)), 100, score_font, white)
            return
        if now < self.point_until:
            return
        screen.pen = white
        screen.rectangle(self.ball.x + self.correction_x, self.ball.y + self.correction_y, BALL_SIZE, BALL_SIZE)


game = Pong()


def update():
    now = badge.ticks
    dt = min(badge.ticks_delta, MAX_FRAME_MS) / 1000
    game.update(now, dt)
    game.draw(now)


def on_exit():
    badge.caselights(0)
    game.link.close()


run(update)
