# Pig vs Goose

Pig vs Goose is a turn-based water-balloon duel with destructible terrain, splashy craters, and a mischievous computer opponent.

## Play

Open **Pig Vs Goose** from the badge menu. Choose **VS COMPUTER** (you are
Pig) or **PASS & PLAY** (two people share the badge) using Left/Right, then
press Select. Pig throws first. The marker above a character indicates whose
turn it is.

## Badge vs Badge

Install the same version of Pig vs Goose on **two Universe 2026 badges**.
Choose **BADGE VS BADGE** on each, bring the badges close together, and press
**Select on both** when the opponent is found. This reuses Pong's
`badgeware.link.Link` and `Proximity` discovery/pairing helpers; it does not
need Wi-Fi credentials or an external server.

The link's central badge plays **Pig** and the other plays **Goose**. The
lobby tells you your character, and an asterisk marks your soak meter. Both
screens show the same board. Each player drives, aims, and throws using their
own badge **only on their character's turn**; the other screen says it is
waiting for the opponent.

One badge runs the authoritative game and sends acknowledged, fragmented
snapshots; the other displays those snapshots rather than running a second
independent simulation. This keeps craters (including overhangs), rolling
carts, wind, balloons, soak, butterflies, and hairdryer bonuses consistent.
The viewing badge updates at the link's delivered snapshot rate, not its own
physics rate. Missing packets are retried; held controls expire if updates stop.

- **Menu on either badge:** pause both. Select on either resumes.
- **Back while paused or at a result:** leave the link and return to the title.
- **Rematch:** Select on **both** badges starts a fresh shared landscape.
- **Home:** exit and close the link.
- If a badge leaves or stops responding, the other shows a connection error.
  Return to the title and enter Badge vs Badge again to pair for a new match.
  A disconnected match is not resumed.

Badge vs Badge requires firmware supplying `badgeware.link`, just like Pong.
The browser simulator cannot verify the real badge radio or pair two physical
badges. Its link stub stays on the searching screen and logs that badge
communication is unavailable; if the API is absent entirely, the title shows
a firmware requirement. Computer and pass-and-play modes do not load or
require the link.

## Turn controls

Each turn has two stages:

1. **Drive:** Left/Right drives your little red cart up to 12 terrain pixels,
   including small steps. Select enters aiming once both carts have stopped.
   You can stay put.
2. **Aim:** Left/Right decreases/increases elevation relative to your character's
   forward direction; 90 degrees is straight up. Up/Down raises/lowers power.
   Select throws once the carts are still. Back returns to driving without
   replenishing your allowance.

The board is a larger 200x150 terrain map, with smaller riders, rolling hills,
and a randomized sheer cliff near the middle. Both carts tilt to match their
wheel contacts, their wheels spin as they move, and gravity rolls them downhill
until they settle. Driving and a splash removing a ledge can start a roll;
gravity does not consume your driving allowance. A cart can carry momentum
across the bottom of a dip. Wait for rolling to finish before aiming or throwing.

The dotted guide previews only the beginning of a throw, not its landing.
Wind changes each turn; the HUD shows its direction and strength. Balloons
can fly above the screen, but leaving the left or right edge counts as a miss.
The computer searches possible throws incrementally and adds a small aiming
error. It does not deliberately drive during its own turns, but its cart still
rolls with gravity.

Splashes carve genuine circular holes, including overhangs, into the terrain.
Nearby characters gain soak, including the thrower if caught in their own
splash. Characters fall when the ground beneath their feet is removed; long
falls add soak. Falling into the water immediately soaks a character completely.
The first character to reach **100% soaked** loses. Simultaneous soak-outs draw.
The result panel explains who reached 100% and whether the finishing damage
came from a balloon splash, a hard landing, or falling into the water.
You can lose from accumulated splash or fall damage without touching the water.
The soak bars blend from blue through yellow and orange to critical red.

## Butterfly bonus

Occasionally a small butterfly flies across the sky in a sine wave, with a
random starting height, direction, amplitude, speed, and frequency. Hit it
**directly with your balloon** (not a splash) to summon the gigantic TURBO
hairdryer. It descends, shakes, blows animated gusts, and flaps your rider about
before retreating. It removes **25 percentage points** from the thrower's soak:
70% becomes 45%, and anything below 25% becomes 0%. It works for Pig or Goose
and never dries the opponent instead.

The balloon is spent on the bonus, without making a crater. Carts and butterfly
spawning pause during the dryer animation, then gravity settles and the turn
passes normally. Menu pauses the entire bonus, including the drying timer.

- **Menu:** pause and show controls; Select resumes, Back returns to the title.
- **Select after a round:** rematch with a fresh landscape.
- **Back after a round:** return to the title and choose a mode.
- **Home:** return to the badge launcher.

## Requirements

GitHub Universe 2026 firmware with the runtime-provided graphics and logical
button APIs. No network, external hardware, credentials, or saved state are
needed. Uses HIRES mode with a cached 200x150 terrain map. Input is
orientation-aware and physics uses elapsed time with fixed substeps.

## Development checks

From the repository root:

```sh
python3 .github/skills/hyb26-skill/scripts/validate_app.py badge/apps/pig_vs_goose
python3 .github/scripts/validate_app_readmes.py badge/apps
```

There are currently no app-specific automated tests in this checkout.

In the Badge Simulator, check both modes, driving and aiming, rolling and
tilting carts, splash craters, falls, butterfly hits, the complete dryer
animation, soak-bar colors, pause/resume, rematches, and upside-down controls.
The simulator is an
approximation: after deployment, confirm the menu icon, readability, input,
animation speed, Home/reopen, and both orientations on a physical badge.

**Two-badge hardware verification remains required:** pair two updated badges, play
several turns from each, verify matching craters and soak, hit a butterfly,
pause/resume from both sides, rematch with both votes, and exit/re-pair from
each side. Confirm link range and update smoothness on the actual firmware.

## Author

[Morten Rand-Hendriksen (@mor10)](https://github.com/mor10)
