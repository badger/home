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
