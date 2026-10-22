# Reusable U26 patterns

These are design patterns, not copy-and-paste guarantees. Keep the pattern
small, then adapt names, layout, and state to the requested app.

## App loop and screen states

- Keep mutable app state in module or small class fields.
- Make `update()` perform one short frame of work.
- Use a state enum or simple named states for intro, active, paused, and game
  over screens.
- Call `run(update)` at module level.

## Button input

- Use `badge.pressed(BUTTON_*)` for one action per press.
- Use `badge.held(BUTTON_*)` for continuous behavior.
- Use `badge.released(BUTTON_*)` when an action must happen on release.
- Keep HOME reserved for the launcher. Never use it as an app control.
- For custom hold or repeat behavior, store the press time and next repeat time.

## Motion and tilt

- Read `badge.imu()` in the frame loop, not in a blocking loop.
- Convert raw accelerometer values using the verified gravity scale.
- Smooth noisy values and compare against a recent rest baseline.
- For gestures, require a strong impulse followed by a return toward rest.
- Add a cooldown and ignore duplicate gestures while an animation is active.
- Test gentle movement, a deliberate gesture, and repeated gestures on hardware.

## Saved state

- Use a small dictionary with stable keys.
- Load defaults before calling `State.load`.
- Save only when a value changes or a run completes.
- Handle missing or malformed values without crashing the app.
- Test both first run and reopen after HOME or reset.

## Assets and drawing

- Keep assets inside the app directory, usually under `assets/`.
- Prefer small PNG files and load them once.
- Use `screen.width` and `screen.height` instead of fixed assumptions when the
  display mode can change.
- Use a real image asset for emoji or detailed art. Do not assume the firmware
  font contains Unicode emoji glyphs.

## Network and cache

- Start asynchronous work from the state transition that needs it.
- Keep `update()` responsive while a request is pending.
- Write to a temporary file and rename only after a complete response.
- Show cached or offline content when possible.
- Bound response sizes and provide timeout, error, and retry behavior.
