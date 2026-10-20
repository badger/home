"""Tufty's own day, which runs faster than ours and needs no clock to be set.

His day is moved on a frame at a time by whoever is drawing him, so it only
runs while he is on screen, and it is kept between sessions by saving where it
got to. At SPEED 120 a whole day of his passes in twelve of our minutes.
"""

SPEED = 120         # how much faster his day runs than ours
OPENS_AT = 9        # the hour a badge with no Tufty saved opens on

# the hours the scene turns over on, and the minutes either side of each one
# that the two backgrounds are blended across
DAWN, MORNING, EVENING, NIGHT = 5, 7, 19, 21
BLEND = 60

_minutes = OPENS_AT * 60


def advance(seconds):
  """Move his day on by this many seconds of ours, and say how far it went."""
  global _minutes
  passed = seconds * SPEED / 60
  _minutes += passed
  return passed


def now():
  """His time of day, as (hour, minute)."""
  at = int(_minutes)
  return (at // 60) % 24, at % 60


def resume(at):
  """Set his day to the minute a saved one was left at."""
  global _minutes
  _minutes = at


def reading():
  """His time of day as minutes, for keeping between sessions."""
  return int(_minutes)


def look(hour, minute):
  """The two backgrounds on show and how far between them the day is.

  Each change is mixed across BLEND minutes either side of the hour it falls
  on, so dusk arrives and leaves gradually. Away from a change the pair are
  the same and nothing is blended.
  """
  at = hour * 60 + minute
  for change in (DAWN, MORNING, EVENING, NIGHT):
    opens = change * 60 - BLEND
    if opens <= at < change * 60 + BLEND:
      return phase(change - 1), phase(change), (at - opens) / (BLEND * 2)
  return phase(hour), phase(hour), 0.0


def phase(hour):
  """Which of the three scenes belongs to this hour."""
  if hour < DAWN or hour >= NIGHT:
    return "night"
  if hour < MORNING or hour >= EVENING:
    return "dusk"
  return "day"
