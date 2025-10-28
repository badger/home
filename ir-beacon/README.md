# IR Beacon
This project implements an IR beacon that transmits NEC protocol infrared signals. It was designed for Mona's Quest at GitHub Universe 2025 as a quest/scavenger hunt system where devices can send unique codes that can be detected by other devices.

## Hardware Pin Configuration

The project is based around the [Tiny2040 - a small RP2040-based board from Pimoroni](https://shop.pimoroni.com/products/tiny-2040?variant=39560012234835).  This board is mounted on a custom PCB to add connections for battery power and to power up to two IR LED's. The following pin configuration is used:

### Main Beacon (`main.py`)

| Component | Pin(s) | Description |
|-----------|--------|-------------|
| **IR TX** | GPIO 0 | Infrared transmitter LED pin |
| **RGB LED** | GPIO 18, 19, 20 | Red, Green, Blue channels for status indication |

### Pin Details

- **IR_TX_PIN = 0**: Connects to the IR LED transmitter for sending infrared pulses
- **LED_PINS = (18, 19, 20)**: On board RGB LED for visual feedback during transmission
  - Pin 18: Red channel
  - Pin 19: Green channel  
  - Pin 20: Blue channel

## Code Structure

### Main Components

```
ir-beacon/
├── main.py           # Main beacon application
├── send.py           # NEC protocol sender implementation
├── receive.py        # NEC protocol receiver implementation
├── common.py         # NEC protocol constants and utilities
├── pulse/            # Low-level pulse generation and reception
│   ├── send.py       # PIO-based pulse sender
│   ├── receive.py    # PIO-based pulse receiver
│   └── pio/          # PIO state machine programs
│       ├── tx.py     # Transmit PIO program
│       └── rx.py     # Receive PIO program
└── remotes/          # Remote control descriptors
    └── descriptor.py # Remote button mapping definitions
```

### Key Files

#### `main.py` - Beacon Application

The main beacon continuously transmits IR codes in bursts:

- **ADDRESS**: `0x45` - Event address (must match receiver)
- **COMMAND**: `0x66` - Unique quest code for each device. Two byes of hex (0x00 to 0xFF).  For Mona's Quest, each location should have a different ID, we are using `0x11`, `0x22` etc for each station.
- **BURST**: Sends 5 repetitions per burst
- **BURST_DELAY**: 0.01s between repetitions
- **SILENCE_DELAY**: 1s between bursts
- **BURST_COLOUR**: On board status LED flashes Purple (255, 32, 255) RGB color during transmission

#### `send.py` - NECSender Class

Handles NEC protocol transmission using PIO state machines:

- `send_addr_cmd(addr, cmd)`: Send address and command bytes
- `send_code(code)`: Send raw 32-bit NEC code
- Uses 38kHz carrier frequency
- Supports short (8-bit) and extended (16-bit) addresses

#### `common.py` - Protocol Constants

NEC protocol timing constants:
- **Frequency**: 38 kHz carrier
- **Start burst**: 9000 µs
- **Start data**: 4500 µs
- **Data burst**: 560 µs
- **Data "0"**: 560 µs
- **Data "1"**: 1680 µs (560 × 3)

### Pulse Generation (`pulse/`)

Low-level pulse transmission and reception using RP2040/RP2350 PIO as timing is critical for IR protocols:

- **PulseSender**: Generates modulated IR pulses at carrier frequency
- **PulseReceiver**: Receives and decodes pulse timing
- Uses hardware PIO state machines for precise timing
- Supports debug pins for oscilloscope analysis

## Usage

### Basic Beacon (Transmit Only)

```python
from aye_arr.nec import NECSender
from pimoroni import RGBLED

# Pin configuration
IR_TX_PIN = 0
LED_PINS = (18, 19, 20)

# Create sender and LED
sender = NECSender(IR_TX_PIN, 0, 0)  # pin, PIO, state machine
led = RGBLED(*LED_PINS)

# Start the sender
sender.start()

# Send codes
sender.send_addr_cmd(0x45, 0x66)
```

### Custom Address and Command

Edit `main.py` to customize your beacon:

```python
ADDRESS = 0x45      # Your event address
COMMAND = 0x66      # Your unique quest code
```

Each quest location should have a different `COMMAND` value while keeping the same `ADDRESS`.

## NEC Protocol Details

The NEC protocol uses a 32-bit data format:
- **Bits 0-7**: Address (or low byte of extended address)
- **Bits 8-15**: Inverted address (or high byte of extended address)
- **Bits 16-23**: Command
- **Bits 24-31**: Inverted command

Timing is critical and handled by PIO state machines for accuracy.

## PIO Resources

The code uses RP2040/RP2350 PIO (Programmable I/O) for precise timing:
- **PIO instance**: 0 (configurable)
- **State machine**: 0 (configurable)
- Can support multiple senders/receivers on different PIO/SM combinations

## Customization

### Change Transmission Pattern

```python
BURST = 10              # Increase repetitions
BURST_DELAY = 0.02      # Slower repetition rate
SILENCE_DELAY = 2       # Longer pause between bursts
BURST_COLOUR = (0, 255, 0)  # Green instead of purple
```

### Dependencies

- MicroPython
- Pimoroni libraries (`pimoroni.RGBLED`)
- RP2040/RP2350 hardware (for PIO)

## License

Copyright 2025 Christopher Parrott for Pimoroni Ltd  
Licensed under the MIT License.