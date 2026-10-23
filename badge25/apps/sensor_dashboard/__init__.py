from badgeware import screen, io, brushes, shapes, PixelFont
import machine
import time

from sensor_core import SensorDashboard, dew_point, fahrenheit
from gas_indexes import GasIndexes, index_caption


background = brushes.color(13, 17, 23)
card_background = brushes.color(26, 33, 43)
foreground = brushes.color(235, 245, 255)
accent = brushes.color(80, 220, 150)
muted = brushes.color(170, 180, 190)
warning = brushes.color(255, 180, 90)
blue = brushes.color(100, 190, 255)
dashboard = None
imperial = False
startup_error = None
index_error = None
small_font = None
value_font = None
tiny_font = None
cards = None
caption_windows = None
caption_states = None


def init():
    global dashboard, imperial, startup_error, index_error, small_font, value_font, cards
    global caption_windows, caption_states, tiny_font
    imperial = False
    startup_error = None
    index_error = None
    small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
    value_font = PixelFont.load("/system/assets/fonts/nope.ppf")
    tiny_font = PixelFont.load("/system/apps/sensor_dashboard/tiny.ppf")
    cards = (
        shapes.rounded_rectangle(4, 16, 74, 31, 4),
        shapes.rounded_rectangle(82, 16, 74, 31, 4),
        shapes.rounded_rectangle(4, 50, 152, 19, 4),
        shapes.rounded_rectangle(4, 72, 74, 36, 4),
        shapes.rounded_rectangle(82, 72, 74, 36, 4),
    )
    caption_windows = {x: screen.window(x + 5, 98, 64, 8) for x in (4, 82)}
    caption_states = {}
    indexes = None
    try:
        import _gas_index
        indexes = GasIndexes(_gas_index, time.ticks_diff)
    except (ImportError, ValueError) as error:
        index_error = "Index error"
        print("Sensor dashboard: native gas module unavailable:", error)
    try:
        bus = machine.I2C(
            0, sda=machine.Pin.board.I2C_SDA,
            scl=machine.Pin.board.I2C_SCL, freq=100000
        )
        dashboard = SensorDashboard(
            bus, time.ticks_ms(), time.ticks_diff, time.ticks_add, indexes
        )
    except (OSError, AttributeError, ValueError) as error:
        dashboard = None
        startup_error = "I2C init failed"
        print("Sensor dashboard: initialization failed:", error)


def text_fit(text, x, y, width, brush):
    screen.brush = brush
    if screen.measure_text(text)[0] > width:
        while text and screen.measure_text(text + "..")[0] > width:
            text = text[:-1]
        text += ".."
    screen.text(text, x, y)


def card(label, value, x, y, width, brush=foreground):
    screen.font = small_font
    text_fit(label, x + 5, y + 4, width - 10, muted)
    screen.font = value_font
    text_fit(value, x + 5, y + 14, width - 10, brush)


def caption_offset(text_width, elapsed):
    overflow = max(0, int(text_width) - 64)
    if not overflow:
        return 0
    travel = max(1, (overflow * 1000 + 11) // 12)
    phase = max(0, elapsed) % (2 * (1000 + travel))
    if phase < 1000:
        return 0
    if phase < 1000 + travel:
        return min(overflow, (phase - 1000) * 12 // 1000)
    if phase < 2000 + travel:
        return overflow
    return max(0, overflow - (phase - 2000 - travel) * 12 // 1000)


def scrolling_caption(text, x, brush):
    screen.font = tiny_font
    now = time.ticks_ms()
    state = caption_states.get(x)
    if state is None or state[0] != text:
        state = (text, now)
        caption_states[x] = state
    offset = caption_offset(screen.measure_text(text)[0], time.ticks_diff(now, state[1]))
    window = caption_windows[x]
    window.font = tiny_font
    window.brush = brush
    window.text(text, -offset, 0)


def gas_card(label, value, baseline, x):
    card(label, "--" if value is None else str(value), x, 72, 74, blue)
    screen.font = small_font
    caption = index_caption(value, baseline)
    if index_error:
        caption = index_error
    elif dashboard is not None and dashboard.sgp_status not in (
        "OK", "Measuring", "Conditioning", "Starting"
    ):
        caption = dashboard.sgp_status
    scrolling_caption(caption, x, warning if value is None else muted)


def temperature_text(value):
    if value is None:
        return "--"
    return "%.1f %s" % (fahrenheit(value) if imperial else value, "F" if imperial else "C")


def update():
    global imperial
    if io.BUTTON_A in io.pressed:
        imperial = False
    if io.BUTTON_C in io.pressed:
        imperial = True
    if dashboard is not None:
        dashboard.update(time.ticks_ms())
    screen.brush = background
    screen.clear()
    screen.font = small_font
    hint = "A=Met C=Imp"
    hint_x = screen.width - 5 - screen.measure_text(hint)[0]
    text_fit("SENSORS", 5, 4, hint_x - 11, accent)
    screen.brush = blue
    screen.text(hint, hint_x, 4)
    screen.brush = card_background
    for shape in cards:
        screen.draw(shape)
    if dashboard is None:
        text_fit(startup_error or "Starting...", 9, 25, screen.width - 18, warning)
        text_fit("Check Qw/ST cable", 9, 55, screen.width - 18, muted)
    else:
        card("Temp", temperature_text(dashboard.temperature), 4, 16, 74)
        card("HUMIDITY", "--" if dashboard.humidity is None else "%.1f %%" % dashboard.humidity, 82, 16, 74)
        if dashboard.temperature is None:
            screen.font = small_font
            text_fit(dashboard.sht_status, 9, 38, 64, warning)
        dew = None if dashboard.temperature is None else dew_point(
            dashboard.temperature, dashboard.humidity
        )
        screen.font = small_font
        text_fit("DEW POINT", 9, 56, 70, muted)
        screen.font = value_font
        value = temperature_text(dew)
        screen.brush = foreground
        screen.text(value, 151 - screen.measure_text(value)[0], 54)
        indexes = dashboard.indexes
        gas_card("VOC INDEX", indexes.voc if indexes else None, 100, 4)
        gas_card("NOx INDEX", indexes.nox if indexes else None, 1, 82)
    screen.font = tiny_font
    footer = "BASELINE LEARNS OVER TIME" if (time.ticks_ms() // 4000) % 2 else "RELATIVE INDEX, NOT PPM"
    text_fit(footer, 5, 113, screen.width - 10, muted)


def on_exit():
    if dashboard is not None:
        dashboard.close()
