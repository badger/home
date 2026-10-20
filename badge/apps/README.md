# Universe 2026 badge firmware examples

This directory includes all 15 launchable apps and the menu pulled from a
connected badge running the 2026-10-08 firmware build. Matching app files were
overwritten with the pulled versions; other repository apps and additional
assets were retained. The menu includes its vector icons, opening animation,
and Mona assets.

| App | What it does |
| --- | --- |
| `badge` | Shows a GitHub profile and contribution activity |
| `brattal` | A two-lane arcade shooter |
| `contacts` | Exchanges contact cards between badges |
| `flappy_mona` | Flappy-style game starring Mona |
| `iss` | Tracks the ISS on a live world map |
| `life` | Conway's Game of Life |
| `mass_storage` | Reboots the badge into USB mass-storage mode |
| `merge_conflict` | A collection of short games, including badge-link play |
| `mona_paint` | A tilt-aware paint program with drawing tools and undo |
| `mona_pet` | A virtual pet with feeding, cleaning, and matching games |
| `pong` | Badge-link multiplayer Pong |
| `rogue` | A turn-based dungeon game |
| `settings` | Edits network/profile details and backlight settings |
| `show` | Starts the firmware's local Sparkle show |
| `snake` | A continuously moving snake game |

The pulled apps use APIs and frozen modules provided
by that badge's firmware (including `badgeware.link`, `hints`, `missing_details`,
`fetch`, `sparkle`, and `pico3d`); it may not run on older builds or in a
simulator. Some apps need Wi-Fi, badge-link peers, configured profile details,
or hardware-specific firmware services.

The menu generates vector icons from `menu/icons.py` for known apps and loads
optional animations from `menu/anim/`. Any other app is shown with its own
`icon.png`, drawn scaled into the menu tile. Add one to every app. These files
are part of the deployable `badge/` tree, but pulling
them into the repository did not write anything to the physical badge.
