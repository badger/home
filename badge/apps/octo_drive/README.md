# Octo Drive

Race a bright pseudo-3D highway with Mona at the wheel in this original arcade road game for the GitHub Universe 2026 badge.

## How to play

Reach all four checkpoints before time expires. Checkpoints add time, passing
traffic adds points, and leaving the road scrubs speed. Traffic density rises
after every checkpoint, while cones, oil patches and barriers become more
frequent in later sections. Finish quickly for a larger time bonus and a saved
best time.

| Pad | Action |
| --- | --- |
| Left / Right | Steer |
| Select (A) or Up | Accelerate |
| Back (B) or Down | Brake |
| Menu | Pause or resume |
| Home | Quit to the badge menu |

The game runs in LORES (160x120), renders the road and cars with vector
primitives, and stores its high score and best finish time with
`badgeware.State`.

The Mona driver sprite is copied from Super Mona. It is derived from the
MIT-licensed Flappy Mona artwork in `badger/home`; attribution is included in
`assets/LICENSE.txt`.
