"""
Latest US news headlines and summaries from NPR, readable on the badge.

The feed is https://feeds.npr.org/1001/rss.xml, which needs no key. Wi-Fi
details come from secrets.py (set them in Settings).

Controls:
* Up / Down = Move between headlines, or scroll a story
* Select = Open the highlighted story's summary
* Back = Close the summary
* Right = Refresh now
"""

import os
import sys

import requests

import missing_details

APP_DIR = "/system/apps/headlines"
try:
  os.chdir(APP_DIR)
  sys.path.insert(0, APP_DIR)
except OSError:
  pass

MISSING = missing_details.missing("WIFI_SSID")
if not MISSING:
  import wifi

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
WIDTH, HEIGHT = screen.width, screen.height

FEED = "https://feeds.npr.org/1001/rss.xml"
MAX_ITEMS = 15
REFRESH_EVERY = 600_000
RETRY_AFTER = 20_000
REQUEST_TIMEOUT = 10

bg = color.rgb(13, 17, 23)
panel = color.rgb(22, 27, 34)
white = color.rgb(240, 246, 252)
muted = color.rgb(139, 148, 158)
green = color.rgb(95, 237, 131)
warning = color.rgb(255, 125, 120)

HEADER_H = 22
LINE_H = 12
PAD = 8

items = []          # (title, summary)
fault = None
loading = True
frames_loading = 0
next_fetch = 0
selected = 0
top = 0             # first headline shown in the list
reading = False
scroll = 0
lines_cache = {}    # wrapped lines per key and width


def unescape(s):
  for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
               ("&apos;", "'"), ("&#39;", "'"), ("&#8217;", "'"), ("&#8216;", "'"),
               ("&#8220;", '"'), ("&#8221;", '"'), ("&#8212;", "-"), ("&#8211;", "-")):
    s = s.replace(a, b)
  # the badge fonts are ASCII; swap the common typographic characters
  for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
               ("\u2014", "-"), ("\u2013", "-"), ("\u2026", "...")):
    s = s.replace(a, b)
  return "".join(c if ord(c) < 128 else "?" for c in s)


def tag(block, name):
  start = block.find("<" + name)
  while start >= 0 and block[start + len(name) + 1] not in " >":
    start = block.find("<" + name, start + 1)
  if start < 0:
    return ""
  start = block.find(">", start) + 1
  end = block.find("</" + name + ">", start)
  text = block[start:end].strip()
  if text.startswith("<![CDATA["):
    text = text[9:-3]
  return unescape(text.strip())


def strip_tags(s):
  out = []
  depth = 0
  for c in s:
    if c == "<":
      depth += 1
    elif c == ">" and depth:
      depth -= 1
    elif not depth:
      out.append(c)
  return "".join(out).strip()


def parse(xml):
  out = []
  pos = 0
  while len(out) < MAX_ITEMS:
    start = xml.find("<item>", pos)
    if start < 0:
      break
    end = xml.find("</item>", start)
    if end < 0:
      break
    block = xml[start:end]
    pos = end + 7
    title = tag(block, "title")
    published = tag(block, "pubDate")
    # "Wed, 28 Oct 2026 15:58:00 -0400" -> "28 Oct 2026 15:58"
    when = published[5:22] if len(published) >= 22 else ""
    summary = strip_tags(tag(block, "description"))
    if title:
      out.append((title, summary, when))
  return out


def fetch():
  global items, fault, next_fetch, selected, top
  try:
    r = requests.get(FEED, timeout=REQUEST_TIMEOUT)
    try:
      xml = r.text
    finally:
      r.close()
    parsed = parse(xml)
    if not parsed:
      raise ValueError("no headlines found")
    items = parsed
    selected = min(selected, len(items) - 1)
    top = min(top, selected)
    lines_cache.clear()
    fault = None
    next_fetch = badge.ticks + REFRESH_EVERY
  except Exception as e:
    fault = str(e)[:36] or "request failed"
    next_fetch = badge.ticks + RETRY_AFTER


def wrap(text, width, key):
  """Break text into lines no wider than width pixels."""
  cached = lines_cache.get(key)
  if cached:
    return cached
  lines = []
  line = ""
  for word in text.split():
    trial = word if not line else line + " " + word
    if screen.measure_text(trial)[0] <= width:
      line = trial
    else:
      if line:
        lines.append(line)
      line = word
  if line:
    lines.append(line)
  lines_cache[key] = lines
  return lines


def clear():
  screen.pen = bg
  screen.rectangle(screen.clip)


def centre(txt, y, col):
  w, _ = screen.measure_text(txt)
  screen.pen = col
  screen.text(txt, (WIDTH - w) / 2, y)


def status(msg, col=muted):
  clear()
  screen.font = font.sins
  centre(msg, HEIGHT / 2 - 6, col)


def header(label):
  screen.pen = panel
  screen.rectangle(rect(0, 0, WIDTH, HEADER_H))
  screen.font = font.sins
  screen.pen = green
  screen.text(label, PAD, 5)
  if loading:
    screen.pen = muted
    w, _ = screen.measure_text("updating...")
    screen.text("updating...", WIDTH - PAD - w, 5)
  elif fault:
    screen.pen = warning
    screen.text("!", WIDTH - PAD - 4, 5)


def draw_list():
  global top
  clear()
  header("NPR News")
  screen.font = font.sins
  rows = (HEIGHT - HEADER_H - 4) // (LINE_H * 3 + 6)
  if selected < top:
    top = selected
  elif selected >= top + rows:
    top = selected - rows + 1
  y = HEADER_H + 4
  for i in range(top, min(len(items), top + rows)):
    lines = wrap(items[i][0], WIDTH - PAD * 2 - 6, ("t", i))[:3]
    block = LINE_H * 3 + 6
    if i == selected:
      screen.pen = panel
      screen.shape(shape.rounded_rectangle(2, y - 2, WIDTH - 4, block - 2, 3))
      screen.pen = green
      screen.rectangle(rect(2, y - 2, 2, block - 2))
    screen.pen = white if i == selected else muted
    for j, line in enumerate(lines):
      screen.text(line, PAD, y + j * LINE_H)
    y += block


def draw_story():
  clear()
  title, summary, meta = items[selected]
  header("%d / %d" % (selected + 1, len(items)))
  screen.font = font.sins
  width = WIDTH - PAD * 2
  lines = [(l, white) for l in wrap(title, width, ("st", selected))]
  if summary:
    lines += [("", white)] + [(l, muted) for l in wrap(summary, width, ("ss", selected))]
  if meta:
    lines += [("", white)] + [(l, green) for l in wrap(meta, width, ("sm", selected))]
  visible = (HEIGHT - HEADER_H - 6) // LINE_H
  global scroll
  scroll = max(0, min(scroll, max(0, len(lines) - visible)))
  y = HEADER_H + 4
  for line, col in lines[scroll:scroll + visible]:
    screen.pen = col
    screen.text(line, PAD, y)
    y += LINE_H
  if scroll + visible < len(lines):
    screen.pen = green
    screen.text("v", WIDTH - PAD - 4, HEIGHT - LINE_H - 2)


def connect_step():
  if wifi.is_connected():
    return True
  code, saying = wifi.status()
  if wifi.connect():
    return True
  status("wifi: " + str(saying)[:30], warning if code < 0 else muted)
  return False


def request_refresh():
  global loading, frames_loading
  loading = True
  frames_loading = 0


def update():
  global selected, reading, scroll, loading, frames_loading

  if MISSING:
    missing_details.show(MISSING, clear)
    return

  if items:
    if reading:
      if badge.pressed(BUTTON_DOWN):
        scroll += 2
      if badge.pressed(BUTTON_UP):
        scroll -= 2
      if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_SELECT):
        reading = False
    else:
      if badge.pressed(BUTTON_DOWN):
        selected = (selected + 1) % len(items)
      if badge.pressed(BUTTON_UP):
        selected = (selected - 1) % len(items)
      if badge.pressed(BUTTON_SELECT):
        reading = True
        scroll = 0
  if badge.pressed(BUTTON_RIGHT):
    request_refresh()

  if not connect_step():
    return

  if not loading and badge.ticks >= next_fetch:
    request_refresh()

  if items:
    if reading:
      draw_story()
    else:
      draw_list()
  elif fault and not loading:
    status(fault, warning)
  else:
    status("fetching headlines...")

  if loading:
    frames_loading += 1
    if frames_loading >= 2:
      fetch()
      loading = False


run(update)
