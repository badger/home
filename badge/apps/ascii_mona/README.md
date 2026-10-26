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
