# Gitris

Gitris is a GitHub-themed falling-block puzzle game adapted for the Universe 2026 badge.

## Controls

- Select starts a game and drops the current piece immediately.
- Left and Right move the piece; hold either to keep moving.
- Up rotates clockwise.
- Down drops the piece faster.
- Menu or Back pauses; Select resumes.
- Back from the pause screen returns to the title.
- Home returns to the badge launcher.

Clear full rows to score commits and advance release levels. Every twelve
pieces, a merge-conflict row appears with one gap. Your best score is saved
through Badgeware state storage. No network connection or credentials are
required.

## Installation

On a Universe 2026 badge in USB disk mode, copy this complete directory to
`BADGER/apps/gitris`, then safely eject and reset the badge. Do not copy it to
the firmware bootloader drive. No firmware, launcher, or existing apps need
to be replaced. Stock launchers may show a generic app icon.

## Source

Adapted from `badge25/apps/gitris` in
[badger/home](https://github.com/badger/home/tree/c095061d3483a2504a67a1f37ed4d7ee71edad5a/badge25/apps/gitris).
The port uses the 2026 runtime, orientation-aware controls, and a high-resolution
layout. The original source is MIT licensed; see `LICENSE`.
