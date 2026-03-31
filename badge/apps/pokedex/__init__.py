import sys
import os

sys.path.insert(0, "/system/apps/pokedex")
os.chdir("/system/apps/pokedex")

from badgeware import io, brushes, shapes, Image, run, PixelFont, screen, Matrix, file_exists
import random
import math
import network
from urllib.urequest import urlopen
import gc
import json


# Colours
white = brushes.color(235, 245, 255)
faded = brushes.color(235, 245, 255, 100)
red = brushes.color(220, 50, 50)
dark_red = brushes.color(150, 30, 30)
dark_bg = brushes.color(15, 15, 25)

# Type colours
TYPE_COLOURS = {
    "normal": (168, 168, 120),
    "fire": (240, 80, 48),
    "water": (104, 144, 240),
    "grass": (120, 200, 80),
    "electric": (248, 208, 48),
    "ice": (152, 216, 216),
    "fighting": (192, 48, 40),
    "poison": (160, 64, 160),
    "ground": (224, 192, 104),
    "flying": (168, 144, 240),
    "psychic": (248, 88, 136),
    "bug": (168, 184, 32),
    "rock": (184, 160, 56),
    "ghost": (112, 88, 152),
    "dragon": (112, 56, 248),
    "dark": (112, 88, 72),
    "steel": (184, 184, 208),
    "fairy": (238, 153, 172),
}

small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

SPRITE_URL = "https://wsrv.nl/?url=https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{path}{id}.png&w=80&h=80&output=png"
STAT_NAMES = ["hp", "atk", "def", "sp.a", "sp.d", "spd"]
MAX_POKEMON = 151

# Load pokemon database from local file (12KB, all Gen 1)
pokedex_db = None
DB_PATH = "/system/apps/pokedex/gen1.json"
try:
    f = open(DB_PATH, "r")
    pokedex_db = json.loads(f.read())
    f.close()
except Exception as e:
    print("Failed to load pokedex db: {}".format(e))

WIFI_PASSWORD = None
WIFI_SSID = None
wlan = None
connected = False
ticks_start = None
WIFI_TIMEOUT = 30

# State
current_id = 4  # Start with Charmander
pokemon_data = None
pokemon_sprite = None
sprite_task = None
sprite_fetching = False
shiny = False


def get_wifi_details():
    global WIFI_PASSWORD, WIFI_SSID
    if WIFI_SSID is not None:
        return True
    try:
        sys.path.insert(0, "/")
        import secrets
        sys.path.pop(0)
        WIFI_SSID = getattr(secrets, "WIFI_SSID", None)
        WIFI_PASSWORD = getattr(secrets, "WIFI_PASSWORD", None)
        del secrets
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None
    return WIFI_SSID is not None


def wlan_start():
    global wlan, ticks_start, connected
    if ticks_start is None:
        ticks_start = io.ticks
    if connected:
        return True
    try:
        if wlan is None:
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            if wlan.isconnected():
                connected = True
                return True
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        connected = wlan.isconnected()
    except Exception as e:
        print("WiFi error: {}".format(e))
        return False
    if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
        return connected
    return False


def sprite_path(pokemon_id, is_shiny=False):
    if is_shiny:
        return "/system/shiny/{}.png".format(pokemon_id)
    return "/system/sprites/{}.png".format(pokemon_id)


def fetch_sprite(pokemon_id, is_shiny=False):
    path = sprite_path(pokemon_id, is_shiny)
    if file_exists(path):
        return
    try:
        url_path = "shiny/" if is_shiny else ""
        response = urlopen(SPRITE_URL.format(id=pokemon_id, path=url_path), headers={"User-Agent": "Pokedex Badge"})
        data = bytearray(512)
        with open(path, "wb") as f:
            while True:
                length = response.readinto(data)
                if length == 0:
                    break
                f.write(data[:length])
                yield
        del data
        del response
    except Exception as e:
        try:
            os.remove(path)
        except:
            pass
        raise RuntimeError("Sprite fetch failed: {}".format(e))
    finally:
        gc.collect()


def load_pokemon(pokemon_id):
    global pokemon_data
    if pokedex_db is None:
        pokemon_data = None
        return
    entry = pokedex_db.get(str(pokemon_id))
    if entry is None:
        pokemon_data = None
        return
    # db format: n=name, t=types, s=[hp,atk,def,spatk,spdef,spd], h=height, w=weight
    pokemon_data = {
        "name": entry["n"].upper(),
        "id": pokemon_id,
        "types": entry["t"],
        "stats": entry["s"],
        "height": entry["h"],
        "weight": entry["w"],
    }


def type_brush(type_name):
    rgb = TYPE_COLOURS.get(type_name, (168, 168, 120))
    return brushes.color(*rgb)


def draw_type_badge(type_name, x, y):
    label = type_name.upper()
    screen.font = small_font
    w, h = screen.measure_text(label)
    screen.brush = type_brush(type_name)
    screen.draw(shapes.rounded_rectangle(x, y, w + 4, h + 1, 2))
    screen.brush = white
    screen.text(label, x + 2, y)


# Fixed bar layout
BAR_X = 97
BAR_W = 36

def draw_stat_bar(name, value, x, y, max_val=154):
    fill = min(int((value / max_val) * BAR_W), BAR_W)

    screen.font = small_font
    screen.brush = faded
    screen.text(name, x, y)

    # Bar background
    screen.brush = brushes.color(40, 40, 50)
    screen.draw(shapes.rounded_rectangle(BAR_X, y + 2, BAR_W, 5, 2))

    # Bar fill
    if value >= 100:
        screen.brush = brushes.color(100, 220, 100)
    elif value >= 60:
        screen.brush = brushes.color(220, 200, 60)
    else:
        screen.brush = brushes.color(220, 80, 60)
    if fill > 0:
        screen.draw(shapes.rounded_rectangle(BAR_X, y + 2, fill, 5, 2))

    # Value — right-aligned, leaving 2px margin from screen edge
    val_str = str(value)
    vw, _ = screen.measure_text(val_str)
    screen.brush = white
    screen.text(val_str, 155 - vw, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, 80 - (w / 2), y)


def draw_main_view():
    # Pokeball red header bar
    screen.brush = red
    screen.draw(shapes.rectangle(0, 0, 160, 14))
    screen.brush = brushes.color(180, 50, 50)
    screen.draw(shapes.rectangle(0, 14, 160, 1))

    # Title + number
    screen.font = large_font
    screen.brush = white
    if pokemon_data:
        screen.text("#{:03d}".format(pokemon_data["id"]), 2, -2)
        name = pokemon_data["name"]
        w, _ = screen.measure_text(name)
        screen.text(name, 157 - w, -2)
    else:
        center_text("POKEDEX", -2)

    # Sprite area (centred in left section)
    # Sprite centred in left column (0-65 x, 15-107 y)
    sprite_cx = 32
    sprite_cy = 65
    if pokemon_sprite:
        bob = math.sin(io.ticks / 400) * 2
        sx = 0
        sy = int(sprite_cy - 40 + bob)
        screen.blit(pokemon_sprite, sx, sy)

        # Shiny sparkles — alternating gold and white
        if shiny:
            sparkle = shapes.squircle(0, 0, 3, 2)
            for i in range(6):
                t = io.ticks / (500 + i * 130)
                phase = i * 1.047
                angle = t * 0.4 + phase
                r = 20 + i * 5
                cx = sprite_cx + math.cos(angle) * r
                cy = sprite_cy + bob + math.sin(angle) * (r * 0.65)
                pulse = math.sin(t * 2.5 + phase * 2)
                if pulse > 0.1:
                    alpha = int(pulse * 200) + 55
                    if i % 2 == 0:
                        screen.brush = brushes.color(248, 220, 48, alpha)
                    else:
                        screen.brush = brushes.color(255, 255, 255, alpha)
                    s = 0.3 + pulse * 0.7
                    sparkle.transform = Matrix().translate(cx, cy).rotate(t * 50 + i * 60).scale(s)
                    screen.draw(sparkle)
    else:
        screen.brush = faded
        squircle = shapes.squircle(0, 0, 8, 4)
        for i in range(3):
            squircle.transform = Matrix().translate(sprite_cx, sprite_cy).rotate(
                (io.ticks + i * 5000) / 40).scale(1 + i / 1.5)
            screen.draw(squircle)

    if pokemon_data:
        rx = 66
        types = pokemon_data["types"]

        # Type badges right-aligned from screen edge
        screen.font = small_font
        badge_x = 158
        for t in reversed(types):
            label = t.upper()
            tw, _ = screen.measure_text(label)
            badge_w = tw + 4
            badge_x -= badge_w
            draw_type_badge(t, badge_x, 17)
            badge_x -= 3  # gap between badges

        # Height / Weight — right-aligned
        screen.brush = faded
        h_m = pokemon_data["height"] / 10
        w_kg = pokemon_data["weight"] / 10
        hw_text = "{:.1f}m {:.1f}kg".format(h_m, w_kg)
        hw_w, _ = screen.measure_text(hw_text)
        screen.text(hw_text, 158 - hw_w, 30)

        # Stats
        y_start = 40
        for i, name in enumerate(STAT_NAMES):
            draw_stat_bar(name, pokemon_data["stats"][i], 69, y_start + i * 10)

    # Shiny indicator
    if shiny:
        screen.font = small_font
        screen.brush = brushes.color(248, 208, 48)
        screen.text("SHINY", 3, 16)

    # Button bar at bottom — matches header style
    screen.brush = dark_red
    screen.draw(shapes.rectangle(0, 107, 160, 1))
    screen.brush = red
    screen.draw(shapes.rectangle(0, 108, 160, 12))
    screen.font = small_font
    screen.brush = white
    screen.text("<prev", 5, 108)
    rw, _ = screen.measure_text("rand")
    screen.text("rand", 80 - rw // 2, 108)
    nw, _ = screen.measure_text("next>")
    screen.text("next>", 153 - nw, 108)


def load_sprite():
    global pokemon_sprite
    path = sprite_path(current_id, shiny)
    if file_exists(path):
        try:
            pokemon_sprite = Image.load(path)
        except:
            pokemon_sprite = None
    else:
        pokemon_sprite = None


def update():
    global current_id, sprite_task, sprite_fetching, pokemon_data, pokemon_sprite, connected, shiny

    # Clear screen
    screen.brush = dark_bg
    screen.draw(shapes.rectangle(0, 0, 160, 120))

    if pokedex_db is None:
        screen.font = large_font
        screen.brush = red
        center_text("POKEDEX", 20)
        screen.font = small_font
        screen.brush = white
        center_text("gen1.json missing!", 50)
        center_text("Re-flash badge files", 65)
        return

    # Input handling (0 = KEEFYMON, 1-151 = Gen 1)
    changed = False
    if io.BUTTON_C in io.pressed:
        current_id = (current_id + 1) % (MAX_POKEMON + 1)
        changed = True
    if io.BUTTON_A in io.pressed:
        current_id = (current_id - 1) % (MAX_POKEMON + 1)
        changed = True
    if io.BUTTON_B in io.pressed:
        current_id = random.randint(0, MAX_POKEMON)
        changed = True

    # Toggle shiny with UP button
    if io.BUTTON_UP in io.pressed:
        shiny = not shiny
        pokemon_sprite = None
        sprite_task = None
        sprite_fetching = False
        load_sprite()
        gc.collect()

    # Force sprite refresh on A+C hold
    if io.BUTTON_A in io.held and io.BUTTON_C in io.held:
        changed = True
        try:
            os.remove(sprite_path(current_id, shiny))
        except:
            pass

    if changed:
        pokemon_sprite = None
        sprite_task = None
        sprite_fetching = False
        load_pokemon(current_id)
        load_sprite()
        gc.collect()

    # Fetch sprite over WiFi if not cached
    if pokemon_sprite is None and not sprite_fetching:
        if get_wifi_details():
            if wlan_start():
                connected = True
                sprite_fetching = True
                gc.collect()
                sprite_task = fetch_sprite(current_id, shiny)

    if sprite_task:
        try:
            next(sprite_task)
        except StopIteration:
            sprite_task = None
            sprite_fetching = False
            load_sprite()
        except Exception as e:
            print("Sprite error: {}".format(e))
            sprite_task = None
            sprite_fetching = False

    draw_main_view()


# Load initial pokemon on startup
load_pokemon(current_id)
load_sprite()

if __name__ == "__main__":
    run(update)
