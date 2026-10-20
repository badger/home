"""
Follow the space station across a live world map, tracing its orbit through day
and night.

Positions come from wheretheiss.at, which needs no key or account, and the
coastlines from world.geo.json beside this file. The network details come from
secrets.py.

Controls:
* Left = The whole world
* Right = Closed in and travelling with the station
* Up and down = Close in further, or back out to the whole world
* Select = Fetch again now
"""

import json
import math

import requests

import missing_details

MISSING = missing_details.missing("WIFI_SSID")
if not MISSING:
  import wifi

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

WIDTH, HEIGHT = 320, 240

# The map fills the screen, but latitude is not spread evenly down it. Around
# the equator a degree is worth what a degree of longitude is, so the middle of
# the map holds a true aspect; the slack needed to reach the top and bottom is
# pushed out towards the poles, where it shows least. The readouts sit over the
# foot of it.
MAP_W, MAP_H = WIDTH, HEIGHT
MAP_TOP = 0
BAND_H = 47
BAND_TOP = HEIGHT - BAND_H

# Closed in, a degree is worth this much more. The station never leaves 51.6
# degrees of latitude, so following it never reaches a pole.
FOLLOW_ZOOM = 2.5
ZOOM_MIN, ZOOM_MAX = 1.0, 6.0
ZOOM_RATE = 1.6             # what a second on the button multiplies the zoom by
CENTRE_BY = 2.0             # the zoom by which the view has taken hold of it

TRACK_STEP_S = 300          # seconds between the points the feed returns
TRACK_BACK, TRACK_AHEAD = 9, 10
# A fetch blocks the frame for about a second, so they are spaced out and the
# marker carries on between them from the last two fixes.
POSITION_EVERY = 30_000
TRACK_EVERY = 600_000
RETRY_AFTER = 15_000
REQUEST_TIMEOUT = 10

WHERE = "https://api.wheretheiss.at/v1/satellites/25544"
COASTLINES = "world.geo.json"

# Coastlines are thinned as they are read: a point closer than this to the one
# before adds nothing at either zoom, and a ring smaller than this in both
# directions is under a pixel across.
SIMPLIFY = 0.45             # degrees
SMALLEST = 1.4              # degrees

white = color.rgb(242, 245, 243)
text = color.rgb(228, 235, 230)
muted = color.rgb(144, 150, 146)
green = color.rgb(95, 237, 131)
green_bright = color.rgb(140, 242, 166)
green_deep = color.rgb(15, 191, 62)
warning = color.rgb(255, 125, 120)

night = color.rgb(0, 0, 0, 140)
sea = color.rgb(16, 20, 17)
land = color.rgb(30, 64, 40)
track_ahead = color.rgb(95, 237, 131, 90)
track_flown = color.rgb(95, 237, 131, 230)
highlight = color.rgb(95, 237, 131, 90)

# the strip above the readouts naming the country the station is over or
# near, absent in open ocean
NAME_H = 20

label_font = font.sins
value_font = font.bacteria
heading_font = font.futile

BAND_PAD = 12

WAITING = "fetching iss position..."

# a short timeout so failures report quickly; retries set high enough that
# wifi's own error card never appears and connecting() keeps reporting instead
WIFI_TIMEOUT = 10           # seconds an attempt is given
WIFI_RETRIES = 100000       # a failed round takes about a second, so this is a day of them

MARKER = 4.5                # radius of the station's dot, in pixels
HALO = 9.0

# The bar along the bottom edge fills as the next reading comes due.
BAR_H = 3

zoom = 1.0                  # 1.0 is the whole world, above it holds the station
where = None                # the last position, as the feed gave it
previous = None             # the one before, to carry the marker between fetches
track = []                  # (lon, lat) around one orbit
track_from = 0              # the timestamp the first track point belongs to
fetched_at = None           # ticks when the position last arrived
next_position = 0
next_track = 0
fault = None                # what went wrong with the last attempt

outlines = []               # every coastline as shapes, built once at startup
lands = []                  # per country: name, ringed bounds, and its shapes
over_name = None            # the country under the station, or None at sea
near_name = None            # failing that, one within NEAR_DEGREES of it
place_shapes = ()           # the named country's shapes, for the highlight

NEAR_DEGREES = 16.0         # about 1800km, most of what is in sight from orbit


def load_land():
  """Each country's coastline rings, thinned, as (name, [rings]).

  A ring that steps more than half the world sideways has crossed the date
  line, which would draw as a streak across a plate carree, so it is cut
  there and the pieces stand on their own.
  """
  with open(COASTLINES, "r") as handle:
    countries = json.load(handle)

  kept = []
  for country in countries:
    rings = []
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

    drawable = []
    for ring in rings:
      lons = [point[0] for point in ring]
      lats = [point[1] for point in ring]
      if max(lons) - min(lons) > SMALLEST or max(lats) - min(lats) > SMALLEST:
        drawable.append(ring)
    if drawable:
      kept.append((country["name"], drawable))
  return kept


def shortest(degrees):
  """The same angle, brought into -180 to 180."""
  return (degrees + 180.0) % 360.0 - 180.0


def landed(lon, lat):
  """The country under this point, as (name, its shapes), or (None, ()) at sea.

  A ray cast over each country's rings, behind a bounds test that rules
  nearly all of them out. Costs a few tens of ms, so it runs once per fetch.
  """
  for name, bounds, shapes_ in lands:
    inside = False
    for x0, y0, x1, y1, ring in bounds:
      if lon < x0 or lon > x1 or lat < y0 or lat > y1:
        continue
      j = len(ring) - 1
      for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and \
           lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
          inside = not inside
        j = i
    if inside:
      return name, shapes_
  return None, ()


def nearby(lon, lat):
  """The closest country within NEAR_DEGREES, or None in open ocean.

  Distance is taken to the ring points, which the thinning keeps within about
  half a degree of the true coast: near enough for a label. Longitude is
  squeezed by the latitude so a degree is worth the same both ways.
  """
  squeeze = math.cos(math.radians(lat))
  best, best_shapes, best_d = None, (), NEAR_DEGREES * NEAR_DEGREES
  for name, bounds, shapes_ in lands:
    for x0, y0, x1, y1, ring in bounds:
      # the bounds, grown by the reach, rule almost every ring out
      if (lat < y0 - NEAR_DEGREES or lat > y1 + NEAR_DEGREES
          or (lon < x0 - NEAR_DEGREES or lon > x1 + NEAR_DEGREES)
          and (lon + 360.0 < x0 - NEAR_DEGREES or lon - 360.0 > x1 + NEAR_DEGREES)):
        continue
      for px, py in ring:
        dx = shortest(px - lon) * squeeze
        dy = py - lat
        d = dx * dx + dy * dy
        if d < best_d:
          best_d, best, best_shapes = d, name, shapes_
  return best, best_shapes


# A degree of latitude is worth this at the equator, matching longitude, and
# the cubic term takes up the rest of the height by the poles.
DEG_X = MAP_W / 360.0
LAT_CUBIC = (MAP_H / 2 - DEG_X * 90.0) / 90.0 ** 3


def base(lon, lat):
  """Longitude and latitude on the whole world map, before any zoom."""
  return ((lon + 180.0) * DEG_X,
          MAP_H / 2 - (DEG_X * lat + LAT_CUBIC * lat * lat * lat))


def project(lon, lat, centre=None):
  """A point on the map as drawn, which is the whole world scaled about `centre`."""
  x, y = base(lon, lat)
  if centre is None:
    return x, y
  return (MAP_W / 2 + (x - centre[0]) * zoom,
          MAP_H / 2 + (y - centre[1]) * zoom)


def centre_now():
  """Where the view is held, in whole world coordinates, or None for all of it.

  Between zoom 1 and CENTRE_BY the centre eases from the middle of the map
  onto the station, so zooming in never jumps.
  """
  if where is None or zoom <= 1.0:
    return None

  hold = min(1.0, (zoom - 1.0) / (CENTRE_BY - 1.0))
  x, y = base(where["lon"], where["lat"])
  return (MAP_W / 2 + (x - MAP_W / 2) * hold,
          MAP_H / 2 + (y - MAP_H / 2) * hold)


def viewing(centre, lap=0.0):
  """The matrix that carries the whole world map into the view being drawn."""
  if centre is None:
    return mat3()
  return (mat3().translate(MAP_W / 2, MAP_H / 2).scale(zoom, zoom)
          .translate(lap - centre[0], -centre[1]))


def draw_land(centre):
  """The countries, filled flat.

  The outlines are built once and moved by a matrix: reprojecting every point
  in Python costs half a second, drawing the shapes as they stand 17ms, as
  one batch. Zoomed in they are drawn a world either side too, so the map
  wraps at the date line.
  """
  # which copies of the world are visible at this zoom
  laps = [0.0]
  if centre is not None:
    half = (MAP_W / 2) / zoom
    if centre[0] - half < 0:
      laps.append(-MAP_W)
    if centre[0] + half > MAP_W:
      laps.append(MAP_W)

  for lap in laps:
    carry = viewing(centre, lap)
    screen.pen = land
    for outline in outlines:
      outline.transform = carry
    screen.shapes(outlines)

    # the country the strip names, washed out of the others
    if place_shapes:
      screen.pen = highlight
      screen.shapes(place_shapes)


def draw_night(centre):
  """Shade the half of the world the sun is not on.

  The feed gives the point the sun is overhead. The terminator is the circle
  a quarter turn from it, which crosses each meridian at a latitude that
  falls out of the sun's declination.
  """
  if not where:
    return

  solar_lat = math.radians(where["solar_lat"])
  if abs(solar_lat) < 0.02:                # equinox: the line is a meridian
    solar_lat = 0.02 if solar_lat >= 0 else -0.02

  edge = []
  for step in range(37):
    lon = -180.0 + step * 10.0
    dlon = math.radians(lon - where["solar_lon"])
    lat = math.degrees(math.atan(-math.cos(dlon) / math.tan(solar_lat)))
    edge.append(project(lon, lat, centre))

  # the pole on the sun's side is lit, so night lies the other way
  away = -90.0 if where["solar_lat"] > 0 else 90.0
  _, far = project(0, away, centre)
  points = [vec2(x, y) for x, y in edge]
  points.append(vec2(edge[-1][0], far))
  points.append(vec2(edge[0][0], far))

  screen.pen = night
  screen.shape(shape.custom(points))


def draw_map():
  """The sea, the land, and the night side, drawn where the view is now.

  Antialiasing is off for the map: it halves the frame cost, and eased edges
  would show seams where countries share a border.
  """
  centre = centre_now()
  screen.antialias = image.OFF
  screen.pen = sea
  screen.rectangle(0, 0, MAP_W, MAP_H)
  draw_land(centre)
  draw_night(centre)
  screen.antialias = image.X2


def draw_track():
  """The ground track, brighter behind the station than ahead of it."""
  if len(track) < 2:
    return

  flown = 0.0
  if fetched_at is not None and track_from:
    flown = (where["at"] + (badge.ticks - fetched_at) / 1000
             - track_from) / TRACK_STEP_S

  centre = centre_now()
  last = None
  for index, (lon, lat) in enumerate(track):
    x, y = project(lon, lat, centre)
    if last is not None and abs(x - last[0]) < MAP_W / 2:
      screen.pen = track_flown if index <= flown else track_ahead
      screen.shape(shape.line(vec2(last[0], last[1] + MAP_TOP),
                              vec2(x, y + MAP_TOP), 1.6))
    last = (x, y)


EARTH_R = 6371.0            # km, for the footprint and the orbit
MU = 398600.4418            # km^3/s^2, Earth's gravitational parameter
FOOTPRINT_STEPS = 36
# the disc pulses between these; lighten() has no alpha, so the pulse is in
# how hard it lifts what it covers
FOOTPRINT_LIFT = (10, 44)
FOOTPRINT_MS = 2200


def draw_footprint(lon, lat):
  """The circle of ground the station can see, and be seen from.

  The feed gives its diameter, which is an angle at the centre of the Earth.
  Walking that angle round every bearing gives the ring, and longitudes are
  left unwrapped so the polygon holds together; drawing it a world either side
  covers the case where it laps the date line.
  """
  if not where:
    return

  reach = (where["footprint"] / 2.0) / EARTH_R      # radians
  lat0, lon0 = math.radians(lat), math.radians(lon)
  sin_lat0, cos_lat0 = math.sin(lat0), math.cos(lat0)
  sin_reach, cos_reach = math.sin(reach), math.cos(reach)

  ring = []
  for step in range(FOOTPRINT_STEPS):
    bearing = step * 2.0 * math.pi / FOOTPRINT_STEPS
    edge_lat = math.asin(sin_lat0 * cos_reach
                         + cos_lat0 * sin_reach * math.cos(bearing))
    edge_lon = lon0 + math.atan2(math.sin(bearing) * sin_reach * cos_lat0,
                                 cos_reach - sin_lat0 * math.sin(edge_lat))
    ring.append((math.degrees(edge_lon), math.degrees(edge_lat)))

  swell = 0.5 - 0.5 * math.cos(badge.ticks / FOOTPRINT_MS * 2.0 * math.pi)
  lift = FOOTPRINT_LIFT[0] + (FOOTPRINT_LIFT[1] - FOOTPRINT_LIFT[0]) * swell

  centre = centre_now()
  screen.pen = brush.lighten(int(lift))
  for lap in (-360.0, 0.0, 360.0):
    points = []
    for edge_lon, edge_lat in ring:
      x, y = project(edge_lon + lap, edge_lat, centre)
      points.append(vec2(x, y + MAP_TOP))
    screen.shape(shape.custom(points))


def draw_station():
  if not where:
    return

  lon, lat = where["lon"], where["lat"]
  if previous and fetched_at is not None:
    # extrapolate from the last two fixes between fetches, capped at twice
    # the measured gap
    span = where["at"] - previous["at"]
    if 0 < span < 120:
      ahead = min(2.0, (badge.ticks - fetched_at) / 1000 / span)
      lon += shortest(lon - previous["lon"]) * ahead
      lat += (lat - previous["lat"]) * ahead

  draw_footprint(shortest(lon), lat)

  # the marker: a faint halo, a white ring, and a core coloured by sunlight
  x, y = project(shortest(lon), lat, centre_now())
  y += MAP_TOP
  screen.pen = color.rgb(255, 255, 255, 60)
  screen.shape(shape.circle(x, y, HALO))
  screen.pen = white
  screen.shape(shape.circle(x, y, MARKER))
  screen.pen = green_bright if where["sunlit"] else muted
  screen.shape(shape.circle(x, y, MARKER - 1.8))


def thousands(value):
  """25000 as 25,000."""
  digits = str(value)
  groups = []
  while len(digits) > 3:
    groups.insert(0, digits[-3:])
    digits = digits[:-3]
  groups.insert(0, digits)
  return ",".join(groups)


# Altitude and speed, side by side over the foot of the map, with the bar along
# the bottom edge. The position is on the map, which says it better than a pair
# of numbers.
LABEL_Y, VALUE_Y = 6, 20
UNIT_GAP = 3
UNIT_DROP = 7
COLUMNS = ("left", "centre", "right")


def orbit_minutes(altitude):
  """How long a lap takes, from how high it is: Kepler's third law."""
  radius = EARTH_R + altitude
  return 2.0 * math.pi * math.sqrt(radius ** 3 / MU) / 60.0


def measure(text, typeface):
  screen.font = typeface
  return screen.measure_text(text)[0]


def aligned(width, column):
  if COLUMNS[column] == "left":
    return BAND_PAD
  if COLUMNS[column] == "centre":
    return (WIDTH - width) / 2
  return WIDTH - BAND_PAD - width


def readout(column, label, number, unit):
  number_w = measure(number, value_font)
  unit_w = measure(unit, label_font)
  width = number_w + UNIT_GAP + unit_w
  x = aligned(width, column)
  screen.font = label_font
  screen.pen = muted
  screen.text(label, aligned(measure(label, label_font), column), BAND_TOP + LABEL_Y)
  screen.font = value_font
  screen.pen = text
  screen.text(number, x, BAND_TOP + VALUE_Y)
  screen.font = label_font
  screen.pen = muted
  screen.text(unit, x + number_w + UNIT_GAP, BAND_TOP + VALUE_Y + UNIT_DROP)


def draw_bar():
  """How far along we are towards the next reading."""
  if fetched_at is None:
    return
  left = max(0, next_position - badge.ticks)
  part = 1.0 - min(1.0, left / POSITION_EVERY)
  screen.pen = color.rgb(255, 255, 255, 30)
  screen.rectangle(0, HEIGHT - BAR_H, WIDTH, BAR_H)
  screen.pen = green_deep
  screen.rectangle(0, HEIGHT - BAR_H, int(WIDTH * part), BAR_H)


def draw_band():
  # the country under the station, or close by it, over the readouts
  place = None
  if over_name:
    place = "over %s" % over_name
  elif near_name:
    place = "near %s" % near_name
  if place:
    screen.pen = color.rgb(0, 0, 0, 150)
    screen.rectangle(0, BAND_TOP - NAME_H, WIDTH, NAME_H)
    screen.font = value_font
    screen.pen = text
    _, line = screen.measure_text(place)
    screen.text(place, BAND_PAD, BAND_TOP - NAME_H + (NAME_H - line) / 2)

  # a translucent scrim, so the map still shows under the type
  screen.pen = color.rgb(0, 0, 0, 190)
  screen.rectangle(0, BAND_TOP, WIDTH, BAND_H)

  if where is None:
    # no fix yet: show the wait or the fault instead, wrapped since faults
    # run longer than a line
    screen.font = value_font
    screen.pen = muted
    screen.text(fault or WAITING,
                rect(BAND_PAD, BAND_TOP + 6, WIDTH - BAND_PAD * 2, BAND_H - 10),
                align=image.CENTER)
    return

  readout(0, "altitude", "%d" % round(where["altitude"]), "km")
  readout(1, "speed", thousands(round(where["speed"])), "km/h")
  readout(2, "orbit", "%.1f" % orbit_minutes(where["altitude"]), "min")
  draw_bar()


def get_json(url):
  response = requests.get(url, timeout=REQUEST_TIMEOUT)
  try:
    if response.status_code != 200:
      raise OSError("HTTP %d" % response.status_code)
    return response.json()
  finally:
    response.close()


def fetch_position():
  """Where it is now, plus the point the sun is overhead."""
  global where, previous, fetched_at, fault, over_name, near_name, place_shapes
  payload = get_json(WHERE)
  reading = {
      "lat": float(payload["latitude"]),
      "lon": float(payload["longitude"]),
      "altitude": float(payload["altitude"]),
      "speed": float(payload["velocity"]),
      "sunlit": payload.get("visibility") != "eclipsed",
      "footprint": float(payload["footprint"]),
      "solar_lat": float(payload["solar_lat"]),
      "solar_lon": float(payload["solar_lon"]),
      "at": int(payload["timestamp"]),
  }
  previous = where
  where = reading
  fetched_at = badge.ticks
  fault = None
  over_name, place_shapes = landed(shortest(reading["lon"]), reading["lat"])
  near_name = None
  if over_name is None:
    near_name, place_shapes = nearby(shortest(reading["lon"]), reading["lat"])


def fetch_track():
  """One orbit of ground track, ten timestamps to a request."""
  global track, track_from
  if not where:
    return
  wanted = [where["at"] + step * TRACK_STEP_S
            for step in range(-TRACK_BACK, TRACK_AHEAD + 1)]
  points = []
  for start in range(0, len(wanted), 10):
    stamps = ",".join(str(when) for when in wanted[start:start + 10])
    for entry in get_json("%s/positions?timestamps=%s" % (WHERE, stamps)):
      points.append((float(entry["longitude"]), float(entry["latitude"])))
  if points:
    track = points
    track_from = wanted[0]


def fetch_due():
  """Fetch whatever is due, one thing a frame so a stall is never doubled."""
  global next_position, next_track, fault

  if not wifi.is_connected():
    return

  try:
    if badge.ticks >= next_position:
      fetch_position()
      next_position = badge.ticks + POSITION_EVERY
    elif badge.ticks >= next_track:
      fetch_track()
      next_track = badge.ticks + TRACK_EVERY
  except (OSError, ValueError, KeyError, TypeError) as reason:
    fault = "%s: %s" % (type(reason).__name__, reason)
    next_position = badge.ticks + RETRY_AFTER
    next_track = badge.ticks + RETRY_AFTER


def wait_page(heading, saying, spinning, tone=None):
  """A dimmed full-screen page: heading, message and an optional spinner.

  The first of these goes up before the coastlines have been read; until
  there is a map it draws on open sea.
  """
  if outlines:
    draw_map()
  else:
    screen.pen = sea
    screen.rectangle(0, 0, WIDTH, HEIGHT)
  screen.pen = color.rgb(0, 0, 0, 170)
  screen.rectangle(0, 0, WIDTH, HEIGHT)

  screen.font = heading_font
  screen.pen = green
  width, _ = screen.measure_text(heading)
  screen.text(heading, (WIDTH - width) / 2, 78)

  screen.font = value_font
  screen.pen = tone or muted
  screen.text(saying, rect(26, 112, WIDTH - 52, 100), align=image.CENTER)

  if spinning:
    # spinner: a faint full ring with a bright 90 degree sweep going round
    screen.pen = color.rgb(255, 255, 255, 40)
    screen.shape(shape.arc(WIDTH / 2, 206, 15, 19, 0, 360))
    turned = badge.ticks / 1200 * 360
    screen.pen = green
    screen.shape(shape.arc(WIDTH / 2, 206, 15, 19, turned, turned + 90))


def connecting():
  """Hold the map until the network is up, saying how that is going.

  `wifi.connect()` moves its own state machine on each time it is called, so
  the loop both drives the attempt and reports what it says about it. With no
  details to connect with there is nothing to drive, and the missing details
  page stands until someone goes back to the launcher or into disk mode.
  """
  while MISSING:
    missing_details.show(MISSING, draw_map)
    badge.update()

  reason = None
  while True:
    # read status before connect() retries and clears it, and hold any
    # failure for the page
    code, saying = wifi.status()
    if code < 0:
      reason = saying

    if wifi.connect():
      return

    # failures get their own heading and colour
    if reason:
      wait_page("cannot connect", reason + "\n\nStill trying...", True, warning)
    else:
      wait_page("connecting to wifi...", saying, True)

    badge.update()


# the coastline read takes over a second and holds the frame, so a page goes
# up first. The radio starts before the read so the association runs during
# it, landing the first fix about two seconds sooner.
wait_page("starting up...", "Reading the world map", False)
badge.update()

if not MISSING:
  wifi.connect(timeout=WIFI_TIMEOUT, retries=WIFI_RETRIES)

# the rings become shapes once (from here on the map is moved by a matrix),
# and each country keeps its rings and their bounds for the landed() test
for name, rings in load_land():
  shaped = [shape.custom([vec2(*base(lon, lat)) for lon, lat in ring])
            for ring in rings]
  outlines.extend(shaped)
  bounds = []
  for ring in rings:
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    bounds.append((min(lons), min(lats), max(lons), max(lats), ring))
  lands.append((name, bounds, shaped))

connecting()


while True:
  if badge.pressed(BUTTON_LEFT):
    zoom = ZOOM_MIN
  if badge.pressed(BUTTON_RIGHT):
    zoom = FOLLOW_ZOOM

  # holding up closes in on the station and down backs out to the whole world
  step = ZOOM_RATE * badge.ticks_delta / 1000
  if badge.held(BUTTON_UP):
    zoom = min(ZOOM_MAX, zoom * (1 + step))
  if badge.held(BUTTON_DOWN):
    zoom = max(ZOOM_MIN, zoom / (1 + step))

  if badge.pressed(BUTTON_SELECT):
    next_position = 0
    next_track = 0

  fetch_due()

  draw_map()
  draw_track()
  draw_station()
  draw_band()
  badge.update()
