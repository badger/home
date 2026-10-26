# Taste Stamp

Flip or karate-chop your badge to slam Creative Director verdicts, shake the Creative 8-Ball for a Studio creative direction, and beam either one to nearby badges over IR.

## Usage

Taste Stamp has two modes. Press LEFT or RIGHT to switch between them.

### Stamp mode

Flip the badge upside down (or back upright), karate-chop it, or press DOWN to slam a verdict onto the creative brief. Each slam shakes the screen, flings ink and strobes the four case lights. Older stamps fade as new ones land.

| Button | Action |
| --- | --- |
| DOWN | Slam a verdict |
| UP | Pick the next verdict, or go back to random |
| SELECT | Beam the last verdict to nearby badges |
| BACK | Clear the paper; press again to exit |

The seven verdicts are SHIP IT, CERTIFIED BANGER, NEEDS MORE TEETH, KILL THE FLUFF, TOO SAFE, WHERE IS THE TENSION? and MAKE THE DEV THE HERO. Random slams deal every verdict once before any repeats.

### Creative 8-Ball mode

Shake the badge, flip it, or press DOWN or UP to tumble a dithered 3D d20. It settles with one numbered face towards you and reveals one of 20 Studio creative directions, such as KILL YOUR DARLINGS or SHOW THE CODE.

| Button | Action |
| --- | --- |
| DOWN / UP | Spin the d20 |
| SELECT | Beam the prompt to nearby badges once the d20 lands |
| BACK | Reset the d20; press again to exit |

### Beaming

SELECT sends the current verdict or prompt as a short NEC infrared burst. A badge that receives it slams the same verdict, or spins its d20 onto the same prompt. Beams only arrive while the other badge is also running Taste Stamp, so open the app on both badges and point them at each other.

## Hardware

- **Motion:** flips use `badge.upside_down()`. Chops and shakes come from `badge.imu()` as relative changes in the size and direction of the acceleration, so they work in any orientation and at any frame rate. The thresholds are at the top of each detector in `motion.py`.
- **Case lights:** the four rear LEDs strobe on every slam and chase while a beam goes out or comes in. They switch off when you leave the app.
- **Infrared:** transmits on GPIO16 (IR TX, PIO0 state machine 1) and receives on GPIO17 through the firmware's `badgeware.ir` receiver, on NEC address `0x53`. It never transmits on `0x45`, the address of the menu's achievement beacons.
- No network access or extra hardware is required.

## Badge Simulator

The simulator has no IR hardware and its IMU never moves, so use the buttons instead of motion: DOWN slams a verdict or spins the d20, and the canvas rotate control flips the badge. SELECT shows a simulated beam.

## Files

- `__init__.py`: app loop, drawing and input.
- `verdicts.py`: verdicts, inks and 8-Ball prompts, plus a seeded xorshift random number generator and a shuffle bag.
- `stamp.py`: stroked block font, stamp artwork, and slam, shake, strobe and splatter timing.
- `eightball.py`: d20 geometry, tumbling and landing, projection and Bayer dithering.
- `motion.py`: flip, chop and shake detectors.
- `beam.py`: IR message format, send queue and receiver.
