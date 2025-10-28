import time
from aye_arr.nec import NECSender
from pimoroni import RGBLED

"""
IR Beacon for Github Universe 2025.

Set COMMAND to a unique code for each device.
"""

# Beacon Constants
ADDRESS = 0x45      # Make sure this matches the address used for the event
COMMAND = 0x66      # Make sure this matches one of the quests codes for the event
BURST = 5
BURST_DELAY = 0.01
BURST_COLOUR = (255, 32, 255)
SILENCE_DELAY = 1

# Board Constants
IR_TX_PIN = 0
LED_PINS = (18, 19, 20)

# Variables
sender = NECSender(IR_TX_PIN, 0, 0)
led = RGBLED(*LED_PINS)

# Initiate the sender
sender.start()

# Loop forever
while True:
    # Send the intended address and command several times to help it be detected
    print(f"Sending Addr 0x{ADDRESS:02x}, Cmd 0x{COMMAND:02x}")
    for i in range(BURST):
        sender.send_addr_cmd(ADDRESS, COMMAND)
        led.set_rgb(*BURST_COLOUR)

        time.sleep(BURST_DELAY)
        led.set_rgb(0, 0, 0)

    # Have a period of silence between each burst
    time.sleep(SILENCE_DELAY)
