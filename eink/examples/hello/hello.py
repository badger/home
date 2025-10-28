import badger2040
from badger2040 import WIDTH

# Create a new Badger and set it to update at normal speed.
display = badger2040.Badger2040()
display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)

# Reset display and show message
display.clear()
display.set_font("sans")
display.set_thickness(3)
display.set_pen(0)
display.rectangle(0, 0, WIDTH, 16)
display.set_pen(15)
display.text("Hello, Universe!", 20, 20, WIDTH, 1)
display.update()

# Call halt in a loop, on battery this switches off power.
# On USB, the app will exit when A+C is pressed because the launcher picks that up.
while True:
    display.keepalive()
    display.halt()