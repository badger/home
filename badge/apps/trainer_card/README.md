# Trainer Card

Trainer Card shows your GitHub profile as a retro monster-trainer ID card, with a badge case for your Mona's Expedition awards.

Created by [@octobooth-17](https://github.com/octobooth-17).

## Download and install

Download the [Trainer Card ZIP](https://github.com/octobooth-17/home/releases/download/trainer-card-v1.0.0/trainer-card-v1.0.0.zip)
for the GitHub Universe 2026 badge.

1. Extract the ZIP and open **Mass Storage** on your badge.
2. Copy the complete `trainer_card` folder into `apps` on the **BADGER** USB
   drive, keeping its `assets` folder intact.
3. Safely eject the drive and let the badge restart, then open **Trainer Card**
   from the menu.

If the menu shows a generic icon, follow the
[menu icon patch instructions](https://github.com/badger/home/blob/main/hardware/USB_SERIAL.md#menu-icon-patch).
This app targets the 2026 firmware, not the Universe 2025 badge.

## Usage

Open **Trainer Card** from the badge menu.

- **SELECT** flips the card between the trainer card and the badge case.
- **UP/DOWN** on the front changes the card color. Your choice is remembered.
- **Arrows** on the back choose a badge and show where to earn it.
- **BACK** on the badge case flips back to the front.
- **HOME** returns to the menu.

The front shows your name, GitHub handle, contributions, followers, public
repositories, contacts collected with the Contacts app, a portrait, and one star
for every two badges earned. The back shows the eight Mona's Expedition awards,
with locked badges faded out, plus the CAB award once you've found it.

## Requirements

No network access is needed; the card only reads data other apps have saved.

- Set your contact name and GitHub username in the **Settings** app.
- Open the **Badge** app once on Wi-Fi to sync your GitHub stats and avatar.
  Without them, the card shows `---` and your badge's identicon.
- Badges unlock when the badge menu picks up the infrared beacon at each Mona's
  Expedition location.

## Credits and license

Trainer Card and its custom menu icon were created by
[@octobooth-17](https://github.com/octobooth-17).
The Mona's Expedition award artwork is reused from
[badger/home's menu assets](https://github.com/badger/home/tree/main/badge/apps/menu/awards).
The app is distributed under the
[repository's MIT license](https://github.com/badger/home/blob/main/LICENSE);
the download includes the license notice.
