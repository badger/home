# Tufty Badge

For GitHub Universe 2025 we have partnered with our friends at Pimoroni to create the 
Tufty Edition of our hackable conference badge.  This is a custom version of the 
[Pimoroni Tufty 2350](https://shop.pimoroni.com/) badge, with a custom PCB, added IR
sensors and pre-loaded with some fun apps.  The source code for the custom apps is 
available here.

These apps are designed to be run on the base MonaOS MicroPython firmware pre-installed on your badge with our custom badgeware library.

## Repository Structure

```
/badge/                 # Badge firmware and applications
  ├── main.py           # Boot loader and app launcher entry point
  ├── secrets.py        # WiFi configuration (SSID, password, GitHub username)
  ├── apps/             # Application directory
  │   ├── badge/        # GitHub profile stats viewer
  │   ├── flappy/       # Flappy Bird style game
  │   ├── gallery/      # Image gallery viewer
  │   ├── menu/         # App launcher/menu system
  │   ├── monapet/      # Virtual pet simulator
  │   ├── quest/        # IR beacon scavenger hunt
  │   ├── sketch/       # Drawing application
  │   └── startup/      # Boot animation
  └── assets/           # Shared resources
      ├── fonts/        # Pixel Perfect Fonts (.ppf) and bitmap fonts (.af)
      └── mona-sprites/ # Mona character sprite sheets
```

The `badge/` folder contents are pre-loaded in a hidden `/system/` partition on the device.

> [!NOTE]
> Looking for the e-ink badge firmware and setup guides? Head over to the `eink/` directory for the dedicated code and documentation.

## Flashing your Badge
When your badge arrives, it will be pre-loaded with a factory default Micropython image that will have a custom image of Micropython with our apps pre-installed and a 'MonaOS' app launcher.

To get started building apps for the badge, you will need to flash the latest Micropython
firmware that we have. You can find the latest firmware image in the
[Releases](https://github.com/badger/tufty/releases)

1. Download the latest `.uf2` firmware file from the [releases page](https://github.com/badger/tufty/releases).
2. Connect your badge to your computer via USB.
3. On the back of the badge, press and hold the `Home` button. While holding down `Home`, press and release the `Reset` button. Then release the `Home` button.
4. Your badge should then appear as a USB drive named `RP2350`.
5. Drag and drop the `.uf2` file onto the `RP2350` drive.
6. The badge will automatically reboot and run the new firmware.

## Copying Files to the Badge

### Understanding the File System

The badge has two partitions:
- **Hidden `/system/` partition** - Contains pre-loaded apps, assets, and default files (only visible via serial connection)
- **Visible user partition** - Accessible when in USB Mass Storage mode (the `BADGER` drive)

When the badge runs, it looks for files in the visible partition first. If a file exists there, it uses that version instead of the one in `/system/`. This allows you to override or customize any pre-installed app without modifying the hidden partition.

### Entering USB Mass Storage Mode

To copy files to the badge, double-press the Reset button on the back. The badge will appear as a USB drive named `BADGER`.

### Customizing or Replacing Apps

To override a pre-installed app or add a new one:

1. Enter USB Mass Storage mode (double-press Reset)
2. Copy your modified/new app folder to `/apps/<app_name>/` on the BADGER drive
3. The badge will use your version instead of the `/system/apps/<app_name>/` version
4. To modify the menu, copy and edit `/apps/menu/__init__.py`

**Example**: To customize the gallery app, copy the entire `/apps/gallery/` folder structure to `/apps/gallery/` on the BADGER drive, then modify it.

### Adding Gallery Images

For the gallery app, create the folder structure and add images:
- Full-size PNG images: `/apps/gallery/images/`
- Thumbnail images: `/apps/gallery/thumbnails/`

Ensure the thumbnail images correspond to the full-size images for proper display.

### WiFi Configuration

Create or edit `/secrets.py` on the BADGER drive:
```python
WIFI_SSID = "your_wifi_network"
WIFI_PASSWORD = "your_password"
GITHUB_USERNAME = "your_github_username"
```

This file contains default WiFi details for a WiFi access point available in the 'Hack the Badge' space at GitHub Universe. But you need to edit this file to add your own WiFi credentials and GitHub username.

### Finishing Up

When done copying files, safely eject the `BADGER` drive before unplugging or pressing Reset to return to normal mode.

## Running the Apps

To run the apps on the badge, press the `Reset` button once to enter normal mode. The badge will boot and look for `/main.py` on the visible partition. If it doesn't exist, it will use `/system/main.py` which runs the startup animation followed by the menu app launcher.

You can press the `Home` button on the back of the badge to return to the menu app launcher at any time.

In the menu, navigate the apps from the launcher by using `UP`, `DOWN`, `A` and `C` to move around the menu grid. Select the app you want to run and press the `B` button to launch it.

## Pre-installed Apps

### Badge
GitHub profile statistics viewer that displays:
- Your contribution graph
- Follower count
- Repository count
- Total contributions
- Profile avatar

Requires WiFi configuration and GitHub Username configuration in `/secrets.py`. Press A+C together to force refresh data.

### Flappy Mona
A Flappy Bird style game featuring Mona. Press A to jump and avoid obstacles. Try to beat your high score!

### Gallery
Browse through images with smooth thumbnail navigation. Press A/C to navigate, B to toggle UI visibility.

### Mona Pet
A virtual pet simulator. Take care of Mona by:
- Pressing A to play (increase happiness)
- Pressing B to feed (decrease hunger)
- Pressing C to clean (increase cleanliness)

Keep all stats above 30% or Mona will get sad! Stats are automatically saved.

### Quest
An IR beacon scavenger hunt for exploring the conference. Walk around and look for "Mona's Quest" signs to find IR beacons at different locations to unlock quest achievements. Progress is saved automatically.

### Sketch
A drawing application where you can create pixel art. Use arrow keys and A/C to move the cursor and draw. Watch Mona run away from your cursor!

## Development

For developing your own apps, see the [Copilot Instructions](.github/copilot-intructions.md) which provide comprehensive guidance on:
- Badge hardware specifications
- App structure and requirements
- The badgeware library API
- Example code patterns
- Best practices

### App Icon Requirements

Each app must include an `icon.png` file in its root directory:
- **Size**: 24x24 pixels
- **Format**: Color PNG with optional transparency
- **Purpose**: Used by the menu launcher to display your app

All apps in `badge/apps/` serve as working examples of different features and techniques.
