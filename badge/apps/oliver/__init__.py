"""
Follow Oliver Widger's nonstop circumnavigation aboard Phoenix on a world map.

Positions come from the end of his public PredictWind tracker page, which is
2.6 MB whole but holds the voyage in its last bytes, so only those are asked
for. The last good reading is kept in /state, so the map still shows where he
was when there is no network.

Controls:
* Left = The whole world
* Right = Closed in on the boat
* Up and down = Close in further, or back out to the whole world
* Select = Fetch again now
"""

import json
import machine
import math
import time

import requests

import missing_details

MISSING = missing_details.missing("WIFI_SSID")
if not MISSING:
  import wifi

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

WIDTH, HEIGHT = 320, 240
MAP_W, MAP_H = WIDTH, HEIGHT
BAND_H = 47
BAND_TOP = HEIGHT - BAND_H
NAME_H = 20
BAND_PAD = 12

FOLLOW_ZOOM = 2.5
ZOOM_MIN, ZOOM_MAX = 1.0, 6.0
ZOOM_RATE = 1.6
CENTER_BY = 2.0

TRACKER = "https://www.predictwind.com/tracking/SY_Phoenix"
TAIL_BYTES = 60000          # about 100 bytes a fix: two weeks of them
VOYAGE_START = 1790899200   # 2026-10-02T00:00Z, the day he left Port Townsend
SAVED = "/state/oliver.json"
COASTLINES = "/system/assets/world.geo.json"

FETCH_EVERY = 900_000       # the tracker reports about hourly
RETRY_AFTER = 60_000
REQUEST_TIMEOUT = 30
TRACK_STEP = 0.25           # degrees between the wake's points
TRACK_POINTS = 1500         # about 90,000 nm of them

SIMPLIFY = 0.45
SMALLEST = 1.4

WIFI_TIMEOUT = 10
WIFI_RETRIES = 100000

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

text = color.rgb(228, 235, 230)
muted = color.rgb(144, 150, 146)
amber = color.rgb(255, 196, 92)
warning = color.rgb(255, 125, 120)
white = color.rgb(242, 245, 243)
sea = color.rgb(13, 24, 38)
land = color.rgb(44, 66, 58)
wake = color.rgb(255, 196, 92, 220)

label_font = font.sins
value_font = font.bacteria

zoom = FOLLOW_ZOOM
boat = None                 # the last reading, as saved
outlines = []
next_fetch = 0
fault = None
fresh = False               # the reading came from the tracker this run


def load_land():
  """Coastlines thinned as they are read; see the iss app."""
  with open(COASTLINES, "r") as handle:
    countries = json.load(handle)
  rings = []
  for country in countries:
    for polygon in country["polygons"]:
      piece = []
      last = None
      for lon, lat in polygon:
        if last is not None and abs(lon - last[0]) > 180.0:
          if len(piece) > 2:
            rings.append(piece)
          piece = []
          last = None
        if last is None or abs(lon - last[0]) + abs(lat - last[1]) > SIMPLIFY:
          piece.append((lon, lat))
          last = (lon, lat)
      if len(piece) > 2:
        rings.append(piece)
  kept = []
  for ring in rings:
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    if max(lons) - min(lons) > SMALLEST or max(lats) - min(lats) > SMALLEST:
      kept.append(ring)
  return kept


DEG_X = MAP_W / 360.0
LAT_CUBIC = (MAP_H / 2 - DEG_X * 90.0) / 90.0 ** 3


def base(lon, lat):
  return ((lon + 180.0) * DEG_X,
          MAP_H / 2 - (DEG_X * lat + LAT_CUBIC * lat * lat * lat))


def center_now():
  if boat is None or zoom <= 1.0:
    return None
  hold = min(1.0, (zoom - 1.0) / (CENTER_BY - 1.0))
  x, y = base(boat["lon"], boat["lat"])
  return (MAP_W / 2 + (x - MAP_W / 2) * hold,
          MAP_H / 2 + (y - MAP_H / 2) * hold)


def project(lon, lat, center):
  x, y = base(lon, lat)
  if center is None:
    return x, y
  return (MAP_W / 2 + (x - center[0]) * zoom,
          MAP_H / 2 + (y - center[1]) * zoom)


def viewing(center, lap=0.0):
  if center is None:
    return mat3()
  return (mat3().translate(MAP_W / 2, MAP_H / 2).scale(zoom, zoom)
          .translate(lap - center[0], -center[1]))


def draw_map(center):
  screen.antialias = image.OFF
  screen.pen = sea
  screen.rectangle(0, 0, MAP_W, MAP_H)
  laps = [0.0]
  if center is not None:
    half = (MAP_W / 2) / zoom
    if center[0] - half < 0:
      laps.append(-MAP_W)
    if center[0] + half > MAP_W:
      laps.append(MAP_W)
  screen.pen = land
  for lap in laps:
    carry = viewing(center, lap)
    for outline in outlines:
      outline.transform = carry
    screen.shapes(outlines)
  screen.antialias = image.X2


def draw_wake(center):
  if boat is None:
    return
  last = None
  screen.pen = wake
  for lon, lat in boat["track"]:
    x, y = project(lon, lat, center)
    if last is not None and abs(x - last[0]) < MAP_W / 2 * zoom:
      screen.shape(shape.line(vec2(last[0], last[1]), vec2(x, y), 1.4))
    last = (x, y)


def draw_boat(center):
  if boat is None:
    return
  x, y = project(boat["lon"], boat["lat"], center)
  swell = 0.5 - 0.5 * math.cos(badge.ticks / 2200 * 2.0 * math.pi)
  screen.pen = color.rgb(255, 196, 92, 50)
  screen.shape(shape.circle(x, y, 7 + 4 * swell))
  screen.pen = white
  screen.shape(shape.circle(x, y, 4.5))
  screen.pen = amber
  screen.shape(shape.circle(x, y, 2.7))


def hemisphere(value, positive, negative):
  return "%.2f %s" % (abs(value), positive if value >= 0 else negative)


def stamp(when):
  moment = time.gmtime(when)
  return "%d %s %02d:%02dZ" % (moment[2], MONTHS[moment[1] - 1], moment[3], moment[4])


def age():
  """How long ago the fix was, or an empty string until the clock has been set.

  The clock comes up in 2025 after a reset, which puts every fix in the future.
  """
  minutes = (time.time() - boat["at"]) // 60
  if minutes < 0:
    return ""
  if minutes < 60:
    return "%dm ago" % minutes
  if minutes < 1440:
    return "%dh %dm ago" % (minutes // 60, minutes % 60)
  return "%dd %dh ago" % (minutes // 1440, minutes % 1440 // 60)


def set_clock(date):
  """Set the clock from a Date header: Sat, 31 Oct 2026 03:47:12 GMT."""
  parts = date.split()
  hour, minute, second = [int(part) for part in parts[4].split(":")]
  day, month, year = int(parts[1]), MONTHS.index(parts[2]) + 1, int(parts[3])
  weekday = time.gmtime(time.mktime((year, month, day, 0, 0, 0, 0, 0)))[6]
  machine.RTC().datetime((year, month, day, weekday, hour, minute, second, 0))


def readout(x, label, number, unit):
  screen.font = label_font
  screen.pen = muted
  screen.text(label, x, BAND_TOP + 6)
  screen.font = value_font
  screen.pen = text
  screen.text(number, x, BAND_TOP + 20)
  width = screen.measure_text(number)[0]
  screen.font = label_font
  screen.pen = muted
  screen.text(unit, x + width + 3, BAND_TOP + 27)


def status():
  """What the corner of the strip says about where the reading came from."""
  if fault:
    return "old: fetch failed", warning
  if not fresh:
    return "saved", amber
  return "live", muted


def draw_band():
  screen.pen = color.rgb(0, 0, 0, 190)
  screen.rectangle(0, BAND_TOP - NAME_H, WIDTH, BAND_H + NAME_H)
  screen.font = value_font
  if boat is None:
    screen.pen = warning if fault else muted
    screen.text(fault or "waiting for the tracker...",
                rect(BAND_PAD, BAND_TOP - 12, WIDTH - BAND_PAD * 2, BAND_H + 8),
                align=image.CENTER)
    return

  screen.pen = text
  place = "%s  %s" % (hemisphere(boat["lat"], "N", "S"),
                      hemisphere(boat["lon"], "E", "W"))
  screen.text(place, BAND_PAD, BAND_TOP - NAME_H + 3)
  saying, tone = status()
  screen.font = label_font
  screen.pen = tone
  screen.text(saying, WIDTH - BAND_PAD - screen.measure_text(saying)[0], BAND_TOP - NAME_H + 5)

  readout(BAND_PAD, "voyage", "Day %d" % boat["day"], "")
  readout(100, "speed", "%.1f" % boat["speed"], "kt")
  readout(170, "24h run", "%d" % round(boat["run"]), "nm")
  screen.font = label_font
  screen.pen = muted
  screen.text(stamp(boat["at"]) + "\n" + age(),
              rect(238, BAND_TOP + 6, WIDTH - 238 - BAND_PAD, 30), align=image.RIGHT)


def miles(a, b):
  lat_a, lat_b = math.radians(a["p"]["lat"]), math.radians(b["p"]["lat"])
  half_lat = (lat_b - lat_a) / 2
  half_lon = math.radians(b["p"]["lon"] - a["p"]["lon"]) / 2
  chord = (math.sin(half_lat) ** 2
           + math.cos(lat_a) * math.cos(lat_b) * math.sin(half_lon) ** 2)
  return 3440.065 * 2 * math.asin(min(1.0, math.sqrt(chord)))


def parse_tail(body):
  """The voyage's fixes from the end of the page, oldest first.

  The range starts somewhere inside a fix, so the list opens at the first
  object boundary and closes where the page moves on to "images".
  """
  opening = body.find("},{")
  closing = body.rfind('],"images"')
  if opening < 0 or closing < 0:
    raise ValueError("no route in tracker page")
  fixes = json.loads("[" + body[opening + 2:closing] + "]")
  voyage = [fix for fix in fixes if fix["t"] >= VOYAGE_START]
  if not voyage:
    raise ValueError("no fixes since departure")
  voyage.sort(key=lambda fix: fix["t"])
  return voyage


def reading_from(voyage, before):
  """The newest fix and run, with the wake extended from the last reading's."""
  newest = voyage[-1]
  recent = [fix for fix in voyage if fix["t"] >= newest["t"] - 86400]
  run = 0.0
  for index in range(1, len(recent)):
    run += miles(recent[index - 1], recent[index])
  track = list(before["track"]) if before else []
  since = before["at"] if before else 0
  for fix in voyage:
    point = (fix["p"]["lon"], fix["p"]["lat"])
    if fix["t"] > since and (not track or abs(point[0] - track[-1][0])
                             + abs(point[1] - track[-1][1]) >= TRACK_STEP):
      track.append(point)
  del track[:-TRACK_POINTS]
  return {"at": newest["t"], "lat": newest["p"]["lat"], "lon": newest["p"]["lon"],
          "speed": float(newest.get("bsp") or 0.0),
          "day": (newest["t"] - VOYAGE_START) // 86400 + 1,
          "run": run, "track": track}


def load_saved():
  try:
    with open(SAVED, "r") as handle:
      return json.load(handle)
  except (OSError, ValueError):
    return None


def save(reading):
  try:
    with open(SAVED, "w") as handle:
      json.dump(reading, handle)
  except OSError as reason:
    print("oliver: could not save:", reason)


def fetch():
  global boat, fault, fresh
  response = requests.get(TRACKER, timeout=REQUEST_TIMEOUT, headers={
      "Range": "bytes=-%d" % TAIL_BYTES,
      "Accept-Encoding": "identity",
      "User-Agent": "Mozilla/5.0 badger-oliver",
  })
  try:
    if response.status_code != 206:
      raise OSError("HTTP %d" % response.status_code)
    body = response.text
    try:
      set_clock(response.headers["Date"])
    except (KeyError, ValueError, IndexError) as reason:
      print("oliver: no clock from the tracker:", reason)
  finally:
    response.close()
  boat = reading_from(parse_tail(body), boat)
  fresh = True
  fault = None
  save(boat)


def fetch_due():
  global next_fetch, fault
  if badge.ticks < next_fetch or MISSING or not wifi.is_connected():
    return
  try:
    fetch()
    next_fetch = badge.ticks + FETCH_EVERY
  except (OSError, ValueError, KeyError, TypeError, MemoryError) as reason:
    fault = "%s: %s" % (type(reason).__name__, reason)
    print("oliver:", fault)
    next_fetch = badge.ticks + RETRY_AFTER


boat = load_saved()

screen.pen = sea
screen.rectangle(0, 0, WIDTH, HEIGHT)
screen.font = value_font
screen.pen = muted
screen.text("Reading the world map", rect(26, 110, WIDTH - 52, 40), align=image.CENTER)
badge.update()

if not MISSING:
  wifi.connect(timeout=WIFI_TIMEOUT, retries=WIFI_RETRIES)

outlines = [shape.custom([vec2(*base(lon, lat)) for lon, lat in ring])
            for ring in load_land()]


def update():
  global zoom, next_fetch

  if badge.pressed(BUTTON_LEFT):
    zoom = ZOOM_MIN
  if badge.pressed(BUTTON_RIGHT):
    zoom = FOLLOW_ZOOM

  step = ZOOM_RATE * badge.ticks_delta / 1000
  if badge.held(BUTTON_UP):
    zoom = min(ZOOM_MAX, zoom * (1 + step))
  if badge.held(BUTTON_DOWN):
    zoom = max(ZOOM_MIN, zoom / (1 + step))

  if badge.pressed(BUTTON_SELECT):
    next_fetch = 0

  if not MISSING and not wifi.is_connected():
    wifi.connect()
  fetch_due()

  center = center_now()
  draw_map(center)
  draw_wake(center)
  draw_boat(center)
  draw_band()


run(update)
