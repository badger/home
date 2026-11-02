# 12 o'clocks

Twelve selectable interpretations of John Maeda's clock artworks, adapted from CodingTrain for the Universe 2026 badge.

Left/Right switches faces. Menu opens the twelve-item list; Up/Down selects,
Select runs, and Back cancels. Menu also closes the list. Home remains owned
by the badge launcher. The last selected face is saved after 800 ms without
another selection, or on exit. Only the selected face runs; opening the list
pauses it. There are no live thumbnails.

## Time and requirements

Requires Universe 2026 firmware with the native graphics and `badgeware.State`
APIs. No Wi-Fi, credentials, extra hardware, browser libraries, audio, or
network access is used. The internal RTC is read with `time.localtime()` as-is:
this app does not change its timezone or synchronize it. Set the badge's time
with the existing Clock app first. An unset RTC shows a warning. If another
app left the RTC in UTC, this app also shows UTC.

## The twelve faces

| # | Face | Preserved behavior and small-screen adaptation |
| --- | --- | --- |
| 01 | Pendulum | White time and grey AM/PM swing oppositely in a two-second cycle; fixed dot coordinates fitted to 320x240. |
| 02 | Overlaid circles | Red hour, yellow minute, blue second outlined dot matrices. |
| 03 | Double circle | Two edge-centred radial time matrices; cached native ring sectors replace pies and masking circles. The source's effective six-second rotation is preserved. |
| 04 | Colour history | 25 overlapping, skewed time traces; newest white, older hues five degrees apart. Original edge clipping is retained. Time jumps reconstruct at most 25 entries, never hours of catch-up. |
| 05 | Rotated numbers | Black hours, white minutes and red seconds on grey, with the original rotations and relative sizes. |
| 06 | Game of Life | Original 63x30 finite board, 50 ms target steps, time continually seeded, grey life and yellow clock dots. No wrapping. As in the pinned source, grey cells come from the pre-step buffer. |
| 07 | Time as a hand | Stacked time turns with seconds, grey AM/PM at the pivot, red colon blinks every 500 ms. |
| 08 | Zoom and fade | Opposing hour/minute size and brightness waves; the frame-based increment is converted to 1.5 radians/second (the original at 60 fps). |
| 09 | Clocks as pixels | Every lit dot is a tiny clock; one tile is rendered each second and stamped. Subpixel triangular hands become one-pixel lines on the 9px tile. |
| 10 | Rotated grid | Grey 00-59 grid rotated ten degrees, white hour/minute and extruded red seconds. Static grid cached only while this face is active. |
| 11 | Rotating pixels | Five-second faux-3D cylindrical time, original depth ordering and brightness, grey background. |
| 12 | Cube | Six affine, translucent digit faces, original painter's order, red top and grey/white sides. |

HIRES (320x240) preserves Life's nonzero cell widths and the fine grid.
Animated faces target 15 redraws/second except Life (20 simulation steps/second);
static faces redraw on second changes, and face 07 also on blink changes.
Animation phases use elapsed time, not callback counts. Work never queues
unbounded catch-up steps after a pause. Glyph contours replace the source's
overlapping rectangles and one-pixel seam patches.

## Resource boundaries

The deployable app is three Python modules, this README, the MIT license, and
a 24x24 PNG icon. The shared bitmapped alphabet has 105 payload bytes, including
space; shared contours retain the original vertex data. There are no animation
image sequences or twelve separate engines.

Life allocates two 1,890-byte buffers (3,780 payload bytes total) only on face 06.
History stores a timestamp, hue, and count; it generates at most 25 entries.
Face 09 caches a 9x9 tile at HIRES. Face 10 alone caches a 320x240 image
(up to 307,200 bytes for RGBA pixels, excluding native image overhead).
Native glyph/arc caches are bounded by the alphabet/current time and released
on face switches. Temporary native transforms and geometry still allocate;
these bounds are not measurements of total MicroPython heap use.

Retaining unchanged frames avoids repeated Python drawing work; it does **not**
put the CPU or LCD to sleep. No battery-life or physical frame-rate claim is
made. Host tests and browser emulation cannot measure badge heap headroom,
viper execution speed, power, or display latency.

## Validation and hardware checklist

Validated with 17 host regression tests, the app/README checks, and an ARM
MicroPython cross-compile of the viper Life function. The repository's Universe
2026 MicroPython WASM simulator rendered all twelve faces; recordings confirmed
motion on 01/03/06/08/11. Simulator controls covered wraparound selection,
Menu/Back, Home/reopening with persisted selection, and logical Right with
the badge inverted. The simulator adapts viper to Python; these are not
physical-badge performance measurements.

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_twelve_clocks.py'
python3 .github/skills/hyb26-skill/scripts/validate_app.py badge/apps/twelve_clocks
python3 .github/scripts/validate_app_readmes.py badge/apps
python3 tools/build_twelve_clocks_icon.py
```

Before physical release, check all twelve faces at 12:59:59 and midnight,
both badge orientations, Menu/Back/Home, and saved selection after reopening.
Measure face 06's step duration against 50 ms, frame timing on 03/04/11,
and free heap before/after repeated switching (especially 10 and 12). Check
alpha compositing and grid legibility on the LCD. No physical deployment is
performed by these checks.

## Attribution

Original artworks: **John Maeda, 12 o'clocks**.
This MicroPython adaptation follows the p5.js interpretations by
**Daniel Shiffman and the CodingTrain contributors**, not a redesign or a claim
to reproduce the original executable.

Source: <https://codingtrain.github.io/12oclocks/> and
<https://github.com/CodingTrain/12oclocks/tree/170fb6ff31ed93fe07c82974a918eb790be24b9e>.
All twelve `clocks/clock-01.js` through `clock-12.js`, `resources/font.js`,
and `resources/font_shapes.js` were consulted at that pinned revision.
The font rows and polygon vertices are preserved in `clockwork.py`.
Copyright (c) 2017 Daniel Shiffman. The upstream MIT license is included in
`LICENSE`.
