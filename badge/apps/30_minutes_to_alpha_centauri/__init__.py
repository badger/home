import sys
import os

sys.path.insert(0, "/system/apps/30_minutes_to_alpha_centauri")
os.chdir("/system/apps/30_minutes_to_alpha_centauri")

import math
import random
import cutscene
import time

hud = image.load("assets/hud.png")
win = image.load("assets/win.png")
game_over = image.load("assets/game_over.png").spritesheet(5, 1)

ark_font = font.ark
screen.font = ark_font
screen.antialias = image.OFF


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3
    WIN_SCREEN = 4


BLACK = color.rgb(0, 0, 0)
WHITE = color.rgb(255, 255, 255)
TEXTURE_SIZE = 64

# Here we're setting up texture packs that will be filled in when the game selects a level.
background = None
wall_tex = None
obst_tex = None
wall_variation = 0
player_sprites = image.load("assets/player.png").spritesheet(9, 1)

# Setting up lots of variables that persist frame to frame.
movement_offset = 0
start_side_length = 2
z_offset = 0
screen_centre = vec2(screen.width / 2, screen.height / 2)
segment_multiplier = 2
num_segs = 6
default_z_increment = 0.10
z_increment = 0.10
# Everything that used to move a fixed amount per frame is now scaled by
# frame_scale, the real time elapsed relative to the ~15fps the game ran at on
# the old badge. At 15fps frame_scale is 1.0 and the maths matches the original
# exactly; at higher framerates it keeps the same real-world pace. z_step is the
# per-frame forward travel (z_increment scaled for the current frame).
frame_scale = 1.0
z_step = default_z_increment
target_fps = 60
pixel_doubling = False
collision_debug = False
include_obstacle = False
game_state = GameState.INTRO
level_start_time = 0
level_segments_total = 0
level_segments_passed = 0
congrat_choice = ""
final_time = 0
start_screen = 0
fade_counter = 255


# The level just stores the name and how much we want the walls to vary.
class Level:
    def __init__(self, texture_pack, wall_variation):
        self.texture_pack = texture_pack
        self.wall_variation = wall_variation


# Just one level defined at the moment, more to come
levels = [
    Level("hyperion", 0)
]


# This resets everythiong back to its starting conditions, including loading in level textures and picking the random values for the cargo, level and distance.
def init_game():
    global z_increment, z_offset, player, background, wall_tex, obst_tex, wall_variation, intro_cutscene, level_segments_passed, level_segments_total, congrat_choice, start_screen, fade_counter
    level_seed = random.randint(0, len(levels) - 1)
    current_level = levels[level_seed]
    background = image.load(f"assets/{current_level.texture_pack}_bg.png")
    wall_tex = image.load(f"assets/{current_level.texture_pack}_wall.png").spritesheet(8, 1)
    obst_tex = image.load(f"assets/{current_level.texture_pack}_obst.png").spritesheet(5, 7)
    start_screen = True
    fade_counter = 255
    wall_variation = current_level.wall_variation
    level_segments_passed = 0
    level_segments_total = random.randint(100, 200)
    intro_cutscene = cutscene.Cutscene(build_intro_cutscene())
    congrat_text = ["Ya got guts, kid.", "Nice goin', hotshot.", "Good goin', kid, ya did it!", "Nice clean run, kid."]
    congrat_choice = congrat_text[random.randint(0, len(congrat_text) - 1)]

    create_centre_points()
    z_increment = default_z_increment
    z_offset = 0
    player = Player()


# This provides the different data to the opening cutscene.
def build_intro_cutscene():
    cargo_options = ["enviro units", "vole vents", "stem bolts", "fresh towels", "flange stumps"]
    cargo_seed = random.randint(0, len(cargo_options) - 1)
    cargo_txt = cargo_options[cargo_seed]

    scene_list = []
    scene_list.append(cutscene.CutsceneScreen("title", "", cutscene.CutsceneLayout.img_full, ark_font))
    scene_list.append(cutscene.CutsceneScreen("intercom", "Hey, hotshot! Hope they weren't yankin' my chain when they said you was the best drone jockey this side of Arcturus.", cutscene.CutsceneLayout.img_btm, ark_font))
    scene_list.append(cutscene.CutsceneScreen("cargo", f"Gotta urgent delivery of {cargo_txt}, and the faster you get it there, the bigger the bonus.", cutscene.CutsceneLayout.img_left, ark_font))
    scene_list.append(cutscene.CutsceneScreen("level_hyperion", "Yer takin' it to New Hyperion Base, the rough end. Shouldn't have trouble but it's tight in there.", cutscene.CutsceneLayout.img_right, ark_font))
    scene_list.append(cutscene.CutsceneScreen("package_load", "Yer drone's being loaded. You know the controls, right? A, C, Up and Down to move, B to boost? Yeah, course you do. Good luck.", cutscene.CutsceneLayout.img_top, ark_font))
    return scene_list


# Just a little utility method to get the xy coordinates given a singlew index (reading l-r then t-b)
def get_sprite(spritesheet, w, index):
    x = index % w
    y = math.floor(index / w)
    return spritesheet.sprite(x, y)


# Defining the tunnel segment class, which stores the coordinates of its centre, corners, side length and
# its texture (randomly decided when the segment is created), as well as what obstacle(s) it has in it and their textures.
class Segment:
    def __init__(self, side, centre, offset_x, offset_y, obst, collision=True):
        self.ul = vec2(0, 0)
        self.ur = vec2(0, 0)
        self.ll = vec2(0, 0)
        self.lr = vec2(0, 0)
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.centre = centre
        self.radius = side
        self.texture_l = random.randint(0, 7)
        self.texture_r = random.randint(0, 7)
        self.obst = obst
        self.collision = collision
        self.obst_texture_1, self.obst_texture_2 = pick_textures(obst)

    # Refreshing doesn't actually take any external parameters, they all do the
    # same thing, slowly get bigger over time.
    def refresh(self):
        self.radius += (self.radius * segment_multiplier * z_step) / 2
        x_focus = screen.width - player.x
        y_focus = screen.height - player.y

        x_dist = x_focus - screen_centre.x
        y_dist = y_focus - screen_centre.y

        x_dist *= (self.radius) / 140
        y_dist *= (self.radius) / 140

        x_dist += self.radius * self.offset_x / 200
        y_dist += self.radius * self.offset_y / 200

        x = screen_centre.x + x_dist
        y = screen_centre.y + y_dist

        self.centre = vec2(x, y)
        self.ul = vec2(self.centre.x - self.radius, self.centre.y - self.radius)
        self.ur = vec2(self.centre.x + self.radius, self.centre.y - self.radius)
        self.ll = vec2(self.centre.x - self.radius, self.centre.y + self.radius)
        self.lr = vec2(self.centre.x + self.radius, self.centre.y + self.radius)

    # Draw just draws lines around the tunnel segment. We don't use it except for the floor.
    def draw(self):
        screen.pen = color.rgb(255, 255, 255, 50)
        # screen.line(self.ul, self.ur)
        # screen.line(self.ur, self.lr)
        screen.line(self.lr, self.ll)
        # screen.line(self.ll, self.ul)


# The Player class stores your position, and methods to draw the player in 3D
# and determine whether you're about to hit something.
class Player:
    def __init__(self):
        self.x = screen_centre.x
        self.y = screen_centre.y + 40
        self.x_speed = 0
        self.y_speed = 0
        self.x_accel = 0
        self.y_accel = 0
        self.ul = False
        self.ur = False
        self.ll = False
        self.lr = False
        self.x_window = 24
        self.y_window = 13
        self.boost = False

    # Each bit of the player's image is made up of different sprites, shifted slightly with respect to each other
    # depending on where you are on the screen to give a 3D effect. It also switches between the yellow
    # and blue rocket exhaust depending on whether you're boosting or not.
    def draw(self):
        x_offset = self.x - screen_centre.x
        y_offset = self.y - screen_centre.y
        player_img = image(72, 72)

        rocket_offset = x_offset * 0.1

        player_img.blit(player_sprites.sprite(5, 0), vec2(15 - (x_offset * 0.2), 8 - (y_offset * 0.1)))

        if x_offset >= -10 and x_offset <= 10:
            player_img.blit(player_sprites.sprite(1, 0), vec2(-5 - rocket_offset, 18))
            player_img.blit(player_sprites.sprite(1, 0), vec2(37 + rocket_offset, 18))
            player_img.blit(player_sprites.sprite(0, 0), vec2(15, 18))
        elif x_offset < -10:
            player_img.blit(player_sprites.sprite(1, 0), vec2(-5 - rocket_offset, 18))
            player_img.blit(player_sprites.sprite(0, 0), vec2(17, 18))
            player_img.blit(player_sprites.sprite(1, 0), vec2(37 + rocket_offset, 18))
        else:
            player_img.blit(player_sprites.sprite(1, 0), vec2(37 - rocket_offset, 18))
            player_img.blit(player_sprites.sprite(0, 0), vec2(15, 18))
            player_img.blit(player_sprites.sprite(1, 0), vec2(-5 + rocket_offset, 18))

        rocket1 = 6 if self.boost else 2
        rocket2 = 7 if self.boost else 3
        rocket3 = 8 if self.boost else 4

        player_img.blit(player_sprites.sprite(rocket1, 0), vec2(15 + (x_offset * 0.1), 18 + (y_offset * 0.1)))
        player_img.blit(player_sprites.sprite(rocket2, 0), vec2(15 + (x_offset * 0.15), 18 + (y_offset * 0.15)))
        player_img.blit(player_sprites.sprite(rocket2, 0), vec2(15 + (x_offset * 0.2), 18 + (y_offset * 0.2)))
        player_img.blit(player_sprites.sprite(rocket3, 0), vec2(15 + (x_offset * 0.3), 18 + (y_offset * 0.3)))

        screen.blit(player_img, vec2(self.x - 32, self.y - 32))

    # Refresh moves the player on the screen according to the controls.
    def refresh(self):
        self.x_speed += self.x_accel * frame_scale
        self.y_speed += self.y_accel * frame_scale

        self.x += self.x_speed * frame_scale
        self.y += self.y_speed * frame_scale

        if self.x > screen.width - 20 or self.x < 20:
            self.x_speed *= -1
            self.x_accel = 0

        if self.y > screen.height - 20 or self.y < 20:
            self.y_speed *= -1
            self.y_accel = 0

        # the original halved speed and accel every frame; express that as a
        # time-based decay so the damping feels the same at any framerate
        damping = 0.5 ** frame_scale
        self.x_speed *= damping
        self.y_speed *= damping
        self.x_accel *= damping
        self.y_accel *= damping

        rocket_offset = (self.x - screen_centre.x) * 0.1
        self.x_window = 30 - abs(rocket_offset)

    # This method just sets four flags to say whether you're overlapping each of the four
    # quadrants relative to the supplied segment.
    def calc_collision_boxes(self, segment):
        self.ul = self.x < segment.centre.x + self.x_window and self.y < segment.centre.y + self.y_window
        self.ur = self.x > segment.centre.x - self.x_window and self.y < segment.centre.y + self.y_window
        self.ll = self.x < segment.centre.x + self.x_window and self.y > segment.centre.y - self.y_window
        self.lr = self.x > segment.centre.x - self.x_window and self.y > segment.centre.y - self.y_window


# This checks the collision of the segment the player is flying through with their collision boxes.
def check_collision():
    segment = segments[-3]
    player.calc_collision_boxes(segment)

    if not segment.collision:
        return False
    if player.ul and segment.obst in (8, 9, 10, 11, 12, 13, 14):
        return True
    if player.ur and segment.obst in (4, 5, 6, 7, 12, 13, 14):
        return True
    if player.ll and segment.obst in (2, 3, 6, 7, 10, 11, 14):
        return True
    if player.lr and segment.obst in (1, 3, 5, 7, 9, 11, 13):
        return True
    return False


# Basically just a slightly long winded way of picking a texture depending on which of the sixteen combinations of filled in squares
# a given segment has. It returns an index or two to the obstacles spritesheet. It's deciding randomly which of the multiple sprites
# to use for each combination of squares, as well as to use a single merged image or separate ones filling each quadrant.
@micropython.native
def pick_textures(index):
    tex1 = 0
    tex2 = 0
    coin = random.randint(0, 1)

    if index > 14:
        pass
    elif index == 0:
        pass
    elif index == 1:
        tex1 = random.randint(13, 16)
    elif index == 2:
        tex1 = random.randint(9, 12)
    elif index == 3:
        if coin:
            tex1 = random.randint(9, 12)
            tex2 = random.randint(13, 16)
        else:
            tex1 = random.randint(19, 20)
    elif index == 4:
        tex1 = random.randint(5, 8)
    elif index == 5:
        if coin:
            tex1 = random.randint(5, 8)
            tex2 = random.randint(13, 16)
        else:
            tex1 = random.randint(23, 24)
    elif index == 6:
        tex1 = random.randint(5, 8)
        tex2 = random.randint(9, 12)
    elif index == 7:
        tex1 = random.randint(25, 26)
    elif index == 8:
        tex1 = random.randint(1, 4)
    elif index == 9:
        tex1 = random.randint(1, 4)
        tex2 = random.randint(13, 16)
    elif index == 10:
        if coin:
            tex1 = random.randint(1, 4)
            tex2 = random.randint(9, 12)
        else:
            tex1 = random.randint(21, 22)
    elif index == 11:
        tex1 = random.randint(27, 28)
    elif index == 12:
        if coin:
            tex1 = random.randint(1, 4)
            tex2 = random.randint(5, 8)
        else:
            tex1 = random.randint(17, 18)
    elif index == 13:
        tex1 = random.randint(29, 30)
    elif index == 14:
        tex1 = random.randint(31, 32)

    return tex1, tex2


# Sets up an initial array of segments for the start of the level.
@micropython.native
def create_centre_points():
    global segments
    segments = []
    side_length = start_side_length
    centre_point = screen_centre
    for i in range(num_segs):
        new_length = side_length * segment_multiplier * i
        segment = Segment(new_length, centre_point, 0, 0, 0, False)
        segments.append(segment)
        side_length = new_length

    return segments


# Takes four points and draws vertical strips between them, sampling the texture for each one.
# It then also draws a semitransparent black line over it to darken the texture more toward the centre of the screen.
@micropython.native
def draw_wall(image, topleft, bottomleft, topright, bottomright, tex):
    screen.pen = BLACK
    width = topright.x - topleft.x
    tile = wall_tex.sprite(tex, 0)
    for i in range(width):
        x_pos = math.floor(topleft.x + i)
        if x_pos > 0 and x_pos < screen.width:
            t = i / width
            toppoint = topleft.y + ((topright.y - topleft.y) * t)
            bottompoint = math.floor(bottomleft.y + ((bottomright.y - bottomleft.y) * t))
            # Scalar line coords avoid allocating a vec2 pair per column.
            image.blit_vspan(tile, x_pos, toppoint, bottompoint - toppoint, t, 0, t, 1)
            screen.alpha = min(x_pos, 160 - x_pos) * 255 // 80
            screen.line(x_pos, toppoint, x_pos, bottompoint)
    screen.alpha = 255


# Just calculates the time since the start of gameplay.
def calc_time():
    current_time = time.ticks_ms()
    elapsed = current_time - level_start_time
    ms = elapsed % 1000
    _, _, _, _, minute, sec, _, _ = time.gmtime(int(elapsed / 1000))
    return minute, sec, ms


# Simple routines to draw the HUD, time and progress along the course onto the screen.
def draw_hud():
    screen.blit(hud, vec2(0, 0))
    minute, sec, ms = calc_time()

    minute = str(minute)
    sec = str(sec)
    ms = str(ms)

    minute = ("0" * (2 - len(minute))) + minute
    sec = ("0" * (2 - len(sec))) + sec
    ms = ("0" * (3 - len(ms))) + ms

    text = f"Time:{minute}:{sec}:{ms}"
    w, _ = screen.measure_text(text)
    screen.pen = color.rgb(0, 255, 0)
    screen.text(text, 80 - (w / 2), 108)
    screen.pen = color.rgb(0, 128, 0)
    screen.rectangle(20, 118, 120, 2)
    course_progress = (level_segments_passed / level_segments_total) * 120
    screen.pen = color.rgb(0, 255, 0)
    screen.rectangle(20, 118, course_progress, 2)


# The loop to render the tunnel and obstacles.
# For each segment of the tunnel, we take the side walls of it and the segment behind it, draw_wall() between them with the texture,
# and blit that segment's obstacle, if any, to the screen.
@micropython.native
def render_gameplay():
    screen.blit(background, vec2(0, 0))

    for segment in segments:
        segment.refresh()

    for i in range(len(segments) - 2):
        inner = segments[i]
        outer = segments[i + 1]
        inner.draw()

        if inner.ul.x > 0:
            draw_wall(screen, outer.ul, outer.ll, inner.ul, inner.ll, inner.texture_l)
        if inner.ur.x < screen.width:
            draw_wall(screen, inner.ur, inner.lr, outer.ur, outer.lr, inner.texture_r)

        if i == 0:
            screen.pen = BLACK
            horizon = shape.custom([inner.ul, inner.ur, inner.lr, inner.ll])
            screen.shape(horizon)

        if inner.obst_texture_1 > 0:
            screen.blit(get_sprite(obst_tex, 5, inner.obst_texture_1), rect(inner.ul.x, inner.ul.y, inner.radius * 2, inner.radius * 2))
        if inner.obst_texture_2 > 0:
            screen.blit(get_sprite(obst_tex, 5, inner.obst_texture_2), rect(inner.ul.x, inner.ul.y, inner.radius * 2, inner.radius * 2))

    player.draw()

    draw_hud()


# Just checks whether we're in the black "good luck" screen or the fade from black.
def check_start():
    return fade_counter <= 0 and start_screen > num_segs


player = Player()
segments = create_centre_points()
init_game()


def update():
    global game_state, z_offset, z_increment, include_obstacle, level_start_time, level_segments_passed, final_time, start_screen, fade_counter, frame_scale, z_step

    # If we're in the intro, just cycle through the intro cutscene with any button press until
    # there's no more pages of it left, then switch the game mode to gameplay.
    if game_state == GameState.INTRO:
        screen.pen = BLACK
        screen.clear()
        screen.pen = WHITE

        intro_cutscene.draw()

        if badge.pressed():
            if not intro_cutscene.advance():
                game_state = GameState.PLAYING
                level_start_time = time.ticks_ms()

    # If we're playing, advance time each tick and capture inputs.
    elif game_state == GameState.PLAYING:

        # How much real time has passed relative to a 15fps frame. Clamped so a
        # stutter (or the large first-frame delta) can't fling the player or
        # skip a whole tunnel segment in one step.
        frame_scale = min(badge.ticks_delta * 15 / 1000, 3)

        # This check disables controls while fading in.
        if check_start():

            if badge.held(BUTTON_LEFT) and player.x > 20:
                player.x_accel -= 2 * frame_scale
            elif badge.held(BUTTON_RIGHT) and player.x < screen.width - 20:
                player.x_accel += 2 * frame_scale
            if badge.held(BUTTON_DOWN) and player.y < screen.height - 20:
                player.y_accel += 2 * frame_scale
            if badge.held(BUTTON_UP) and player.y > 20:
                player.y_accel -= 2 * frame_scale
            if badge.pressed(BUTTON_SELECT):
                z_increment *= 2
                player.boost = True
            if badge.released(BUTTON_SELECT):
                z_increment /= 2
                player.boost = False

        # Forward travel for this frame, using the (possibly boosted) speed.
        z_step = z_increment * frame_scale

        # Refresh the pkayer, draw the main screen and advance time.
        player.refresh()
        render_gameplay()
        z_offset = z_offset + z_step

        # If check_collision() comes back true, we've hit something, so cancel our forward motion and go to the game over screen.
        if check_collision() and z_offset >= 0.9:
            z_increment = 0
            game_state = GameState.GAME_OVER

        # If we've hit the end of a segment, first of all delete the last segment (now off screen).
        if z_offset >= 1:
            z_offset = 0
            segments.pop()

            # If we're done with the fade in, increase the number of segments passed by 1.
            if check_start():
                level_segments_passed += 1

            # And if the number of segments we've passed has hit the randomly generated total for this run,
            # We store the final time and move to the win screen.
            if level_segments_passed >= level_segments_total:
                z_increment = 0
                final_time = calc_time()
                game_state = GameState.WIN_SCREEN
            else:
                # Otherwise, let's make up a new segment and add it to the list.
                # Every other segment has a chance for an obstacle, unless we're still in the intro.
                xo = random.randint(-wall_variation, wall_variation)
                yo = random.randint(-wall_variation, wall_variation)
                if check_start() and include_obstacle:
                    obst = random.randint(0, 16)
                else:
                    obst = 0
                include_obstacle = not include_obstacle
                segments.insert(0, Segment(start_side_length, screen_centre, xo, yo, obst))

            start_screen += 1

        # This just draws the "get ready" screen, until enough segments have passed that we're past any
        # graphical issues caused by startup.
        if start_screen <= num_segs:
            screen.pen = BLACK
            screen.clear()
            screen.blit(hud, vec2(0, 0))

            screen.pen = WHITE
            dist_text = f"{level_segments_total} klicks to"
            w, _ = screen.measure_text(dist_text)
            screen.text(dist_text, vec2((screen.width - w) / 2, 60))
            dist_text = "destination..."
            w, _ = screen.measure_text(dist_text)
            screen.text(dist_text, vec2((screen.width - w) / 2, 70))
            ready_text = "Get ready!"
            w, _ = screen.measure_text(ready_text)
            screen.text(ready_text, vec2((screen.width - w) / 2, 80))

        # And then if we're done with that, draw the gameplay, but with a semitransparent black over it that fades over time.
        # Only when the opacity of that has reached zero do we start the timer, enable the controls and start spawning obstacles.
        elif fade_counter > 0:
            screen.pen = color.rgb(0, 0, 0, fade_counter)
            screen.rectangle(0, 0, screen.width, screen.height)
            screen.blit(hud, vec2(0, 0))
            fade_counter -= 16 * frame_scale
            if fade_counter <= 0:
                level_start_time = time.ticks_ms()

    # If we're on game over, just randomly pick one of the five images with static to display, display it and loop until the user presses any button.
    elif game_state == GameState.GAME_OVER:
        static = random.randint(0, 4)
        screen.blit(game_over.sprite(static, 0), vec2(0, 0))

        if badge.pressed():
            init_game()
            game_state = GameState.INTRO

    # Win screen is very similar, except we're also calculating the score.
    # The score is basically the average time taken per segment, times an arbitrary big number,
    # so if you never use boost you should get about the same score every time.
    # The key to a high score is using boost as much as possible while still being able to avoid everything.
    elif game_state == GameState.WIN_SCREEN:
        screen.blit(win, vec2(0, 0))
        w, _ = screen.measure_text(congrat_choice)
        screen.text(congrat_choice, vec2((screen.width - w) / 2, 60))

        minute, sec, ms = final_time
        timetotal = (minute * 60 * 1000) + (sec * 1000) + ms
        scoretotal = int((level_segments_total / timetotal) * 751734)

        minute = str(minute)
        sec = str(sec)
        ms = str(ms)

        minute = ("0" * (2 - len(minute))) + minute
        sec = ("0" * (2 - len(sec))) + sec
        ms = ("0" * (3 - len(ms))) + ms

        time_text = f"Final time: {minute}:{sec}:{ms}"
        w, _ = screen.measure_text(time_text)
        screen.text(time_text, vec2((screen.width - w) / 2, 70))

        time_text = f"Over {level_segments_total} klicks"
        w, _ = screen.measure_text(time_text)
        screen.text(time_text, vec2((screen.width - w) / 2, 80))

        time_text = f"Gets you {scoretotal} creds!"
        w, _ = screen.measure_text(time_text)
        screen.text(time_text, vec2((screen.width - w) / 2, 90))

        if badge.pressed():
            init_game()
            game_state = GameState.INTRO


run(update)
