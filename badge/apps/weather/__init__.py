"""
Live weather and a three day forecast for where you are, or a few big cities.

Data comes from open-meteo.com and your location from ip-api.com; neither needs
a key. Wi-Fi details come from secrets.py (set them in Settings).

Controls:
* Left / Right = Previous / next place (the first is "here", found from your IP)
* Select = Refresh now
* Up / Down = Switch between Celsius and Fahrenheit
"""

import math
import os
import sys

import requests

import missing_details

APP_DIR = "/system/apps/weather"
try:
  os.chdir(APP_DIR)
  sys.path.insert(0, APP_DIR)
except OSError:
  pass

MISSING = missing_details.missing("WIFI_SSID")
if not MISSING:
  import wifi

WIDTH, HEIGHT = screen.width, screen.height
screen.antialias = image.X2

REFRESH_EVERY = 600_000
RETRY_AFTER = 20_000
REQUEST_TIMEOUT = 10

# name, latitude, longitude; the first slot is filled in from the IP address
PLACES = [
  ["Here", None, None],
  ["San Francisco", 37.77, -122.42],
  ["New York", 40.71, -74.01],
  ["London", 51.51, -0.13],
  ["Paris", 48.86, 2.35],
  ["Tokyo", 35.68, 139.69],
  ["Sydney", -33.87, 151.21],
]

bg = color.rgb(13, 17, 23)
panel = color.rgb(22, 27, 34)
white = color.rgb(240, 246, 252)
muted = color.rgb(139, 148, 158)
green = color.rgb(95, 237, 131)
sun_col = color.rgb(255, 200, 60)
cloud_col = color.rgb(190, 200, 212)
dark_cloud = color.rgb(120, 130, 145)
rain_col = color.rgb(80, 160, 255)
snow_col = color.rgb(235, 245, 255)
bolt_col = color.rgb(255, 225, 80)
warning = color.rgb(255, 125, 120)

place = 0
fahrenheit = False
data = None            # last good reading for the selected place
fault = None
loading = True
next_fetch = 0
icon_kind = None       # condition the menu icon in /state currently shows
frames_loading = 0     # one frame is drawn first so "updating" shows during a fetch
state = {"place": 0, "fahrenheit": False}

try:
  from badgeware import State
  State.load("weather", state)
  place = state["place"] % len(PLACES)
  fahrenheit = bool(state["fahrenheit"])
except Exception:
  pass


def save():
  try:
    from badgeware import State
    state["place"] = place
    state["fahrenheit"] = fahrenheit
    State.save("weather", state)
  except Exception:
    pass


def describe(code):
  """WMO weather code to (summary, icon kind)."""
  if code == 0:
    return "Clear", "sun"
  if code in (1, 2):
    return "Partly cloudy", "partly"
  if code == 3:
    return "Overcast", "cloud"
  if code in (45, 48):
    return "Fog", "fog"
  if code in (51, 53, 55, 56, 57):
    return "Drizzle", "rain"
  if code in (61, 63, 65, 66, 67, 80, 81, 82):
    return "Rain", "rain"
  if code in (71, 73, 75, 77, 85, 86):
    return "Snow", "snow"
  if code in (95, 96, 99):
    return "Thunderstorm", "storm"
  return "Unknown", "cloud"


def temp(celsius):
  if fahrenheit:
    return round(celsius * 9 / 5 + 32)
  return round(celsius)


def temp_text(celsius):
  return "%d%s" % (temp(celsius), "F" if fahrenheit else "C")


def draw_cloud(cx, cy, s, col):
  screen.pen = col
  screen.shape(shape.circle(cx - 0.45 * s, cy, 0.38 * s))
  screen.shape(shape.circle(cx + 0.05 * s, cy - 0.2 * s, 0.5 * s))
  screen.shape(shape.circle(cx + 0.5 * s, cy + 0.03 * s, 0.34 * s))
  screen.shape(shape.rectangle(cx - 0.45 * s, cy, 0.95 * s, 0.37 * s))


def draw_sun(cx, cy, s):
  screen.pen = sun_col
  screen.shape(shape.circle(cx, cy, 0.42 * s))
  for i in range(8):
    a = i * math.pi / 4
    screen.line(cx + math.cos(a) * 0.62 * s, cy + math.sin(a) * 0.62 * s,
                cx + math.cos(a) * 0.85 * s, cy + math.sin(a) * 0.85 * s)


def draw_icon(kind, cx, cy, s):
  """Weather glyph centred on cx, cy; s is roughly its half width."""
  if kind == "sun":
    draw_sun(cx, cy, s)
  elif kind == "partly":
    draw_sun(cx + 0.35 * s, cy - 0.3 * s, s * 0.8)
    draw_cloud(cx - 0.1 * s, cy + 0.2 * s, s * 0.8, cloud_col)
  elif kind == "cloud":
    draw_cloud(cx, cy, s, cloud_col)
  elif kind == "fog":
    draw_cloud(cx, cy - 0.2 * s, s * 0.8, dark_cloud)
    screen.pen = muted
    for i in range(2):
      y = cy + 0.5 * s + i * 0.3 * s
      screen.line(cx - 0.8 * s, y, cx + 0.8 * s, y)
  elif kind == "rain":
    draw_cloud(cx, cy - 0.25 * s, s * 0.85, dark_cloud)
    screen.pen = rain_col
    for i in range(3):
      x = cx - 0.5 * s + i * 0.5 * s
      screen.line(x, cy + 0.45 * s, x - 0.15 * s, cy + 0.85 * s)
  elif kind == "snow":
    draw_cloud(cx, cy - 0.25 * s, s * 0.85, dark_cloud)
    screen.pen = snow_col
    for i in range(3):
      x = cx - 0.5 * s + i * 0.5 * s
      screen.shape(shape.circle(x, cy + 0.6 * s + (i % 2) * 0.2 * s, max(1, 0.1 * s)))
  elif kind == "storm":
    draw_cloud(cx, cy - 0.25 * s, s * 0.85, dark_cloud)
    screen.pen = bolt_col
    screen.line(cx + 0.1 * s, cy + 0.35 * s, cx - 0.15 * s, cy + 0.65 * s)
    screen.line(cx - 0.15 * s, cy + 0.65 * s, cx + 0.15 * s, cy + 0.65 * s)
    screen.line(cx + 0.15 * s, cy + 0.65 * s, cx - 0.1 * s, cy + 0.95 * s)


def text_at(txt, x, y, col, fnt=None):
  if fnt:
    screen.font = fnt
  screen.pen = col
  screen.text(txt, x, y)


def centre(txt, cx, y, col, fnt=None):
  if fnt:
    screen.font = fnt
  w, _ = screen.measure_text(txt)
  screen.pen = col
  screen.text(txt, cx - w / 2, y)


def day_name(iso):
  """Weekday abbreviation for a YYYY-MM-DD string (Sakamoto's method)."""
  y, m, d = int(iso[0:4]), int(iso[5:7]), int(iso[8:10])
  t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
  if m < 3:
    y -= 1
  w = (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7
  return ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")[w]


def locate():
  """Fill in the 'Here' slot from the IP address."""
  r = requests.get("http://ip-api.com/json/?fields=status,city,lat,lon", timeout=REQUEST_TIMEOUT)
  try:
    j = r.json()
  finally:
    r.close()
  if j.get("status") != "success":
    raise ValueError("location unavailable")
  PLACES[0][0] = j.get("city") or "Here"
  PLACES[0][1] = j["lat"]
  PLACES[0][2] = j["lon"]


def fetch():
  global data, fault, next_fetch
  try:
    if PLACES[place][1] is None:
      locate()
    name, lat, lon = PLACES[place]
    url = (
      "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
      "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
      "weather_code,wind_speed_10m"
      "&daily=weather_code,temperature_2m_max,temperature_2m_min"
      "&forecast_days=4&timezone=auto" % (lat, lon)
    )
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    try:
      j = r.json()
    finally:
      r.close()
    cur, daily = j["current"], j["daily"]
    data = {
      "name": name,
      "temp": cur["temperature_2m"],
      "feels": cur["apparent_temperature"],
      "humidity": cur["relative_humidity_2m"],
      "wind": cur["wind_speed_10m"],
      "code": cur["weather_code"],
      "days": [
        (daily["time"][i], daily["weather_code"][i],
         daily["temperature_2m_max"][i], daily["temperature_2m_min"][i])
        for i in range(1, 4)
      ],
      "high": daily["temperature_2m_max"][0],
      "low": daily["temperature_2m_min"][0],
    }
    fault = None
    next_fetch = badge.ticks + REFRESH_EVERY
    if place == 0:
      set_menu_icon(describe(cur["weather_code"])[1])
  except Exception as e:
    fault = str(e)[:30] or "request failed"
    next_fetch = badge.ticks + RETRY_AFTER


def set_menu_icon(kind):
  """Copy the matching icon to /state so the menu shows the current weather."""
  global icon_kind
  if kind == icon_kind:
    return
  try:
    with open("assets/icons/%s.png" % kind, "rb") as src, open("/state/weather_icon.png", "wb") as dst:
      dst.write(src.read())
    icon_kind = kind
  except OSError:
    pass


def draw_background():
  screen.pen = bg
  screen.rectangle(screen.clip)


def draw_status(msg, col=muted):
  draw_background()
  centre(msg, WIDTH / 2, HEIGHT / 2 - 5, col, font.sins)


def draw_weather():
  draw_background()
  d = data
  summary, kind = describe(d["code"])

  text_at(d["name"][:18], 6, 4, white, font.sins)
  for i in range(len(PLACES)):
    screen.pen = green if i == place else muted
    screen.shape(shape.circle(WIDTH - 8 - (len(PLACES) - 1 - i) * 7, 8, 2 if i == place else 1.2))

  draw_icon(kind, 32, 42, 22)
  text_at(temp_text(d["temp"]), 66, 20, white, font.futile)
  text_at(summary, 66, 44, green, font.sins)
  unit = "mph" if fahrenheit else "km/h"
  wind = d["wind"] * 0.621371 if fahrenheit else d["wind"]
  text_at("Feels %s  H %s L %s" % (temp_text(d["feels"]), temp_text(d["high"]), temp_text(d["low"])),
          6, 66, muted, font.sins)
  text_at("Hum %d%%  Wind %d%s" % (d["humidity"], round(wind), unit), 6, 77, muted, font.sins)

  top = 87
  card_w = (WIDTH - 8 * 2 - 4 * 2) / 3
  for i, (day, code, hi, lo) in enumerate(d["days"]):
    x = 8 + i * (card_w + 4)
    screen.pen = panel
    screen.shape(shape.rounded_rectangle(x, top, card_w, HEIGHT - top - 2, 3))
    cx = x + card_w / 2
    centre(day_name(day), cx, top + 1, white, font.sins)
    draw_icon(describe(code)[1], cx, top + 14, 6)
    centre("%d/%d" % (temp(hi), temp(lo)), cx, top + 21, muted, font.sins)

  if fault:
    screen.pen = warning
    screen.shape(shape.circle(WIDTH - 6, HEIGHT - 6, 2))
  if loading:
    centre("updating...", WIDTH / 2, 76, green, font.sins)


def connect_step():
  """Drive wifi one step; returns True once connected."""
  if wifi.is_connected():
    return True
  code, saying = wifi.status()
  if wifi.connect():
    return True
  draw_status("wifi: " + str(saying)[:22], warning if code < 0 else muted)
  return False


def request_refresh():
  global loading, frames_loading
  loading = True
  frames_loading = 0


def update():
  global place, fahrenheit, loading, data, fault, frames_loading

  if MISSING:
    missing_details.show(MISSING, draw_background)
    return

  if badge.pressed(BUTTON_RIGHT) or badge.pressed(BUTTON_LEFT):
    place = (place + (1 if badge.pressed(BUTTON_RIGHT) else -1)) % len(PLACES)
    data = None
    fault = None
    request_refresh()
    save()
  if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
    fahrenheit = not fahrenheit
    save()
  if badge.pressed(BUTTON_SELECT):
    request_refresh()

  if not connect_step():
    return

  if not loading and badge.ticks >= next_fetch:
    request_refresh()

  if data:
    draw_weather()
  elif fault and not loading:
    draw_status(fault, warning)
  else:
    draw_status("fetching weather...")

  if loading:
    frames_loading += 1
    if frames_loading >= 2:
      fetch()
      loading = False


run(update)
