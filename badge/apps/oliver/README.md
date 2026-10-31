# Oliver

Follow sailor Oliver Widger's solo nonstop trip around the world on a live map.

The app shows his boat's latest position, speed, 24-hour run, and day of the voyage, with his wake drawn across the map. The boat is *Phoenix do Mar*, and you can follow the story at [@sailing_with_phoenix](https://www.instagram.com/sailing_with_phoenix/).

## Usage

- Left: show the whole world
- Right: close in on the boat
- Up and Down: zoom in or out
- Select: fetch again now

The app checks for a new position every 15 minutes, and the tracker reports about hourly. The last good reading is saved in `/state/oliver.json`, so the map still works offline.

## Requirements

Needs Wi-Fi. Set it in Settings or in `secrets.py`.

Positions come from his public [PredictWind tracker](https://www.predictwind.com/tracking/SY_Phoenix). If that page's layout changes, the app stops updating until it's fixed.

## Credits

Adapted from the ISS app in this repository. This is a fan project, not affiliated with Oliver Widger or PredictWind.
