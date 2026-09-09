import json
import math
import os
import secrets
import sys
from datetime import datetime, timezone

import requests
import wifi

# Standalone bootstrap for finding app assets
os.chdir("/system/apps/iss_tracker")

# Standalone bootstrap for module imports
sys.path.insert(0, "/system/apps/iss_tracker")

badge.mode(HIRES)
screen.antialias = image.X4
screen.font = font.sins

CX, CY = screen.width / 2, screen.height / 2

ONE_MINUTE = 60

ISS_API_URL = "http://api.open-notify.org/iss-now.json"
CREW_API_URL = "http://api.open-notify.org/astros.json"

last_updated_loc = None
last_updated_crew = None

update_location = False
update_crew = False
time_set = False

MAP_HEIGHT = 180
MAP_WIDTH = 360
PATH_WIDTH = 2

STAR_PATTERN = brush.pattern(color.rgb(0, 0, 0), color.grey, 20)
BORDER_PATTERN = brush.pattern(color.white, color.rgb(0, 0, 0), 25)
SEA_PATTERN = brush.pattern(color.navy, color.rgb(255, 255, 255, 140), 32)
NIGHT_COLOR = color.rgb(0, 0, 0, 64)

coastlines = []
coastline_bounds = []
coastline_lats = []
iss_crew = []
iss_path = []

# variables used for the crew member window
cr = rect(10, 10, screen.width - 20, screen.height - 20)
crew_window = shape.rectangle(cr.x, cr.y, cr.w, cr.h)
crew_outline = shape.rectangle(cr.x, cr.y, cr.w, cr.h).stroke(2)
show_info = False

iss_sprite = image.load("icon.png")


def load_coastlines():

    global path_count, point_count

    with open("/system/assets/world.geo.json", "r") as f:
        data = json.loads(f.read())
        for country in data:
            for polygon in country["polygons"]:
                mn = 180
                mx = -180
                lat_mn = 90
                lat_mx = -90
                path = []
                for p in polygon:
                    path.append(vec2(p[0], -p[1]))
                    mn = min(mn, p[0])
                    mx = max(mx, p[0])
                    lat_mn = min(lat_mn, -p[1])
                    lat_mx = max(lat_mx, -p[1])

                coastline_lats.append((lat_mx + lat_mx) / 2)
                coastlines.append(shape.custom(path))
                coastline_bounds.append((mn, mx))


def get_tau_and_dec():
    global time_set

    # sync time with ntp at start up. We don't need to do this again
    if not time_set:
        try:
            rtc.time_from_ntp()
            rtc.rtc_to_localtime()
            time_set = True
        except OSError:
            pass

    dt = datetime.now(timezone.utc)
    year = dt.year
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    days_into_year = (dt - start).total_seconds() / 86400

    seconds_since_midnight = dt.hour * 3600 + dt.minute * 60 + dt.second
    degrees = (seconds_since_midnight / 86400) * 360  # 86400 seconds in a day

    declination = -23.45 * math.cos(math.radians((360 / 365) * (days_into_year + 10)))
    return degrees - 180, declination


load_coastlines()

# starting points for the x and y
x, y = 0, 0

# scale value
s = 2.0


def calc_day_night_latitude(longitude, dec):
    latitude = 0
    cos_lat = math.cos(math.radians(longitude))
    try:
        tan_lat = -cos_lat / math.tan(math.radians(dec))
        latitude = math.degrees(math.atan(tan_lat))
    except ZeroDivisionError:
        latitude = 90.0 if cos_lat > 0 else -90.0 if cos_lat < 0 else 0
    return latitude


def get_location():
    global last_updated_loc

    last_updated_loc = badge.ticks

    # try and get the latest position
    # return the last if error raised
    try:
        r = requests.get(ISS_API_URL)
        j = r.json()
        return float(j["iss_position"]["longitude"]), float(j["iss_position"]["latitude"])
    except (OSError, ValueError):
        return None, None


def get_crew():
    global iss_crew, last_updated_crew

    last_updated_crew = badge.ticks

    crew = []
    # try and get the latest position
    # return the last if error raised
    try:
        # get the d data
        r = requests.get(CREW_API_URL)
        j = r.json()

        # grab the list of people in space right now
        people_in_space = j["people"]

        # if that person is on the ISS, save their name to a list
        for person in people_in_space:
            if person["craft"] == "ISS":
                crew.append(person["name"])

        iss_crew = crew

    except (OSError, ValueError):
        pass


def draw_notification(t):
    w, _ = screen.measure_text(t)
    screen.pen = color.rgb(0, 0, 0, 100)
    screen.rectangle(8, 10, w + 30, 15)
    screen.pen = color.white
    screen.text(t, 10, 11)


def draw_map():

    matricies = []
    cx_scaled = CX / s
    y_scaled = y * s

    tau, dec = get_tau_and_dec()

    for o in [-360, 0, 360]:
        matricies.append(mat3().translate(((x + o) * s) + CX, y_scaled + CY).scale(s, s))

    daynight = []
    daynight.append(vec2(-180, 90))
    for i in range(-180, 180 + 1, 1):
        lat = calc_day_night_latitude(i + tau, dec)
        daynight.append(vec2(i, -lat))
    daynight.append(vec2(180, 90))
    daynight_shape = shape.custom(daynight)

    screen.pen = SEA_PATTERN
    screen.rectangle(0, y_scaled + CY - (90 * s), screen.width, 180 * s)

    for i, coastline in enumerate(coastlines):
        mn, mx = coastline_bounds[i]
        if abs(coastline_lats[i]) > 60:
            screen.pen = color.white
        elif coastline_lats[i] >= -22 and coastline_lats[i] <= 10:
            screen.pen = color.yellow
        else:
            screen.pen = color.lime
        for j, o in enumerate([-360, 0, 360]):
            if mn + o < -x + cx_scaled or mx + o > -x - cx_scaled:
                coastline.transform = matricies[j]
                screen.shape(coastline)

    screen.pen = NIGHT_COLOR
    for j, o in enumerate([-360, 0, 360]):
        if -180 + o < -x + cx_scaled or 180 + o > -x - cx_scaled:
            daynight_shape.transform = matricies[j]
            screen.shape(daynight_shape)

    if not show_info:
        screen.pen = color.white
        if len(iss_path) > 0:
            x1, y1 = iss_path[0]
            for i in range(1, len(iss_path)):
                x2, y2 = iss_path[i]
                if x2 < x1:
                    x1 -= 360
                line_seg = shape.line(x1, y1, x2, y2, PATH_WIDTH / s)
                for j, o in enumerate([-360, 0, 360]):
                    if x1 + o < -x + cx_scaled or x2 + o > -x - cx_scaled:
                        line_seg.transform = matricies[j]
                        screen.shape(line_seg)
                x1, y1 = x2, y2

        w, h = iss_sprite.width, iss_sprite.height
        i = (math.sin(badge.ticks / 120) * 64) + (255 - 64)
        screen.alpha = int(i)
        screen.blit(iss_sprite, vec2(CX - (w / 2), CY - (h / 2)))
        screen.alpha = 255


def draw_info():
    screen.pen = color.rgb(0, 0, 0, 150)
    screen.shape(crew_window)
    screen.pen = BORDER_PATTERN
    screen.shape(crew_outline)
    screen.pen = color.white

    ty = cr.y + 10
    tx = cr.x + 10
    screen.text(f"There are currently {len(iss_crew)} members of crew aboard the ISS", tx, ty)
    ty += 15
    for name in iss_crew:
        _, h = screen.measure_text(name)
        screen.text(f"- {name}", tx, ty)
        ty += (h + 1)

    ty += 15
    screen.text("ISS Info:", tx, ty)

    long, lat = -x, y
    ty += 11
    screen.text(f"- Long: {long}", tx, ty)
    ty += 11
    screen.text(f"- Lat: {lat}", tx, ty)


def update():
    global show_info, update_location, update_crew, s, x, y, iss_path

    screen.pen = STAR_PATTERN
    screen.clear()

    if badge.pressed(BUTTON_SELECT):
        show_info = not show_info

    # adjust the scale
    if badge.held(BUTTON_UP):
        s += 0.2
    if badge.held(BUTTON_DOWN):
        s -= 0.2
    # and clamp
    s = min(max(s, 1.0), 4.0)

    if wifi.connect():

        if update_location:
            long, lat = get_location()
            if long and lat:
                x, y = -long, lat

                # add location to list and clamp it to max length of 90
                iss_path.append((-x, -y))
                if len(iss_path) > 90:
                    iss_path.pop(0)
                update_location = False

        if update_crew:
            get_crew()
            update_crew = False

        if last_updated_crew is None:
            update_crew = True

        # get the ISS location once every minute
        if last_updated_loc is None or (badge.ticks - last_updated_loc) / 1000 > ONE_MINUTE:
            update_location = True

        draw_map()

        if update_location or update_crew:
            draw_notification("Updating...")

        if show_info:
            draw_info()

    else:
        screen.pen = brush.pattern(color.blue, color.grey, 32)
        screen.clear()
        draw_notification(f"Connecting to {secrets.WIFI_SSID}...")


run(update)
