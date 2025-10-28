# Pimoroni Tiny FX - Library Reference <!-- omit in toc -->

This is the library reference for the [Pimoroni Tiny FX](https://shop.pimoroni.com/products/tinyfx), a LED effects controller, powered by the Raspberry Pi RP2040.


## Table of Content <!-- omit in toc -->
- [Getting Started](#getting-started)
- [](#)
- [Reading the User Button](#reading-the-user-button)
- [Setting the Mono LED Outputs](#setting-the-mono-led-outputs)
- [Setting the RGB LED Output](#setting-the-rgb-led-output)
- [Reading Voltage](#reading-voltage)
- [Effects System](#effects-system)
  - [Program Lifecycle](#program-lifecycle)
- [`TinyFX` Reference](#tinyfx-reference)
  - [Constants](#constants)
  - [Variables](#variables)
  - [Functions](#functions)
- [`WavPlayer` Reference](#wavplayer-reference)
  - [Constants](#constants-1)
  - [Functions](#functions-1)


## `PulseReceiver` Reference

### Functions

```python
# Initialisation
PulseReceiver(pin_num: int,
              pio: int,
              sm: int,
              decoder_func: callable)

# Interaction
start() -> None
stop() -> None
reset() -> None
decode(debug: bool=False) -> None
```


## `PulseSender` Reference

### Functions

```python
# Initialisation
PulseSender(pin_num: int,
            pio: int,
            sm: int,
            carrier_freq: int | float,
            debug_pin: int=None)

# Interaction
start() -> None
stop() -> None

send(high_us: int, low_us: int)
wait_for_send(high_us: int, low_us: int)
```