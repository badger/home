# ASCII Mona

Turn any GitHub handle into a custom Mona made from real MyOctocat parts, show it as vector or ASCII art, and beam it to nearby badges over IR.

## Usage

ASCII Mona grows a Mona from a GitHub handle. The handle hashes to 19 values of Mona DNA:

- colours for the body, face, eyes, hair and facial hair
- one of GitHub's MyOctocat parts for each of the eyes, mouth, hair, hat, top, bottoms, shoes, prop, eyewear and facial hair
- two extras, a title and a backdrop

Handles aren't case-sensitive and the DNA uses only integer maths, so a handle makes the same Mona on every badge.

Your own Mona comes from `GITHUB_USERNAME` in Settings. The profile the Badge app saves in `/state/badge_user.json` tunes it, and supplies the handle when `GITHUB_USERNAME` is empty. A badge with neither gets a mystery Mona made from its ID. The app opens on your Mona the first time, then on the last Mona you looked at.

| Button | Main view |
| --- | --- |
| SELECT | Beam the Mona on screen over IR |
| LEFT / RIGHT | Switch between the Vector, Shapes, Dither and Edges styles |
| UP | Vector: open the DNA card. ASCII styles: cycle the Primer, ANSI, Phosphor and Amber palettes |
| DOWN | Choose whose Mona to show |
| MENU | Look the handle up on GitHub, or cancel a running lookup |
| BACK | Exit |

The DNA card shows:

- the Mona's parts and colours
- profile facts: name, followers and public repos
- up to two notes from a lookup
- the DNA as 38 hex digits

On the card, SELECT looks the handle up on GitHub, DOWN opens Tweak, and UP or BACK closes the card.

### Choosing a handle

DOWN opens "Who gets a Mona?". UP and DOWN choose a row, SELECT picks it, and BACK or LEFT closes the list.

- **Type a handle** opens an arcade letter wheel:
  - UP and DOWN spin the letter under the cursor; hold to spin fast.
  - LEFT and RIGHT move the cursor, and RIGHT past the last letter adds one.
  - MENU deletes the letter under the cursor.
  - SELECT makes the Mona and BACK cancels.

  A live preview shows the Mona as you type. The wheel only accepts a valid GitHub handle: 1 to 39 letters, digits or hyphens, with no hyphen at either end and no double hyphen. Typing your own handle brings back your own Mona.
- **You**: your own Mona.
- Up to eight recent Monas you made, caught or tweaked.
- Up to 24 cards saved by the Contacts app (`/state/contacts.json`).
- **Surprise me** rolls a mystery Mona with random DNA and no handle.

### Tweaking a Mona

DOWN on the DNA card opens Tweak, which lists all 19 DNA fields: body colour, face colour, eyes, eye colour, mouth, hair, hair colour, hat, top, bottoms, shoes, prop, eyewear, face hair, face hair colour, two extras, title and backdrop.

- UP and DOWN pick a field.
- LEFT and RIGHT change it, and the Mona updates as you go. Hold to repeat.
- SELECT saves.
- MENU puts back the handle's own Mona.
- BACK returns to the DNA card without saving.

When you tweak your own Mona, that becomes the Mona you beam and swap. When you tweak anyone else's, it's saved in your recent Monas. A later profile lookup keeps your tweaks.

### Getting a handle from another badge

- **Hold the badges back to back.** When both badges are on ASCII Mona's main view, the Bluetooth badge link (`badgeware.link`, the proximity swap Contacts uses) swaps the owners' cards both ways: GitHub handle, Mona DNA and name. Each badge then shows the other owner's Mona. For ten seconds afterwards, SELECT shares the Mona on screen over the link as well as IR.
- **Beam it.** SELECT sends the Mona on screen over IR. Any badge in range that is running ASCII Mona catches it and adds it to its recent Monas. It appears straight away, or when that badge's owner closes the letter wheel.

A badge only receives a Mona while it's running ASCII Mona.

### The quest code

After the Mona, a beam sends command `0x88` on address `0x45` three times. That's the Universe quest beacon code for quest 8. What it unlocks depends on what the other badge is running:

- The Quest app completes quest 8, "Octocat Generator".
- The menu's Mona's Expedition counts it as "Level Up Lounge".
- ASCII Mona records quest 8 in the Quest app's progress (`/state/quest.json`) and shows "Quest 8 complete: Octocat Generator".

ASCII Mona never sends the beacon's reset code.

### GitHub profile lookup

MENU, or SELECT on the DNA card, fetches the public profile from `https://api.github.com/users/<handle>`. It tunes the Mona only from what the profile states, and never infers anything personal such as gender, ethnicity or faith:

- **Title:** a bio keyword sets it, such as maintain, design, docs, mentor or research. Without one, 100 or more public repos makes a Maintainer and 20 or more public gists makes a Hacker.
- **Ship It Squirrel:** for GitHub staff and anyone who lists GitHub as their company.
- **Crown:** for 1,000 or more followers.
- **Classic Octocat body colour:** for accounts created in 2010 or earlier.
- **Bio interests** add items, for example:
  - music adds a guitar, games a controller and space an astronaut suit
  - tea or coffee adds a mug, Ruby a gem and photography a camera

The DNA card shows the first two notes about what changed. The badge keeps the last eight profiles, so tuned Monas stay tuned offline. Without a lookup, the Mona comes from the handle alone.

## Styles

**Vector** draws the real MyOctocat parts with a gentle bob over the backdrop from the Mona's DNA: plain, a contribution grid, stars or rings.

The three ASCII styles redraw the Mona as a 24 x 18 grid of 8 x 12 pixel characters that type themselves in like a terminal:

- **Shapes** picks the character whose shape best matches each cell, comparing six-zone shape vectors.
- **Dither** shades each cell from a character ramp with 4 x 4 Bayer ordered dithering.
- **Edges** traces the outlines with a Sobel filter and draws them as line art.

UP cycles the Primer, ANSI, Phosphor and Amber palettes. If the badge runs short of memory, the ASCII styles fall back to Vector.

## Hardware and network

- **IR:** NEC frames go out through GPIO16 (IR TX) and come in through GPIO17 (IR RX). A Mona travels on address `0x4C` as a packet of one-byte frames:
  - `A5 5A` and a length byte
  - a version byte, the 19 DNA bytes and the handle in ASCII
  - a CRC-8

  The beam sends the packet twice, then the quest code. Each frame takes about 80 ms, so a beam for an eight-letter handle takes about six seconds. The receiver ignores its own echo, and repeats of a Mona it caught in the last 15 seconds.
- **Bluetooth badge link (`badgeware.link`):** carries the back-to-back swap. Both badges must be running ASCII Mona.
- **Wi-Fi (optional):** used only for the GitHub profile lookup, on the network saved in Settings. To raise the GitHub API rate limit, set `GITHUB_TOKEN` in `secrets.py` on the badge. The app sends it only to `api.github.com`.
- **Case lights:** flash while beaming and follow the proximity swap the way Contacts does. They turn off when you leave the app.
- **Memory:** the app reads the MyOctocat art from `assets/octocat.bin` on demand and caches only the parts the Mona on screen wears. Retained heap is about 1 MB.

The app saves your style, palette, recent Monas, profiles, your tweaked Mona and the last handle you typed in `/state/ascii_mona.json`.

## Simulator

The Badge Simulator has no IR or badge link. There, a beam runs with the same timing, the badge shows "Simulated beam: no IR sender here", and no Mona arrives from another badge. Everything else works, including the letter wheel, Tweak, every style and the DNA card. The GitHub lookup uses your computer's network.

## Credits

- The ASCII styles are an independent MicroPython implementation of techniques from Cameron Foxly's [Ascii-Motion](https://github.com/CameronFoxly/Ascii-Motion): 6D shape-vector character matching, Bayer 4 x 4 ordered dithering, Sobel edge line art and terminal-style palettes. No Ascii-Motion code is copied.
- The Octocat art is © GitHub, from the [MyOctocat builder](https://myoctocat.com/build-your-octocat/). It's baked into `assets/octocat.bin`, and `mona_parts.py` is generated from the same parts.
