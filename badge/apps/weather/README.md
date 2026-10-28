# Weather

Weather shows live conditions and a forecast for your location over Wi-Fi.

## Usage

Open **Weather** from the badge menu. It shows current conditions and a
three day forecast.

- LEFT / RIGHT: switch place (the first is your location, found from your IP).
- UP / DOWN: switch between Celsius and Fahrenheit.
- SELECT: refresh now.
- HOME: return to the menu.

Requires Wi-Fi: set your network in Settings (`WIFI_SSID` / `WIFI_PASSWORD`).
Data comes from open-meteo.com and ip-api.com, neither of which needs a key.

Each time your own location ("Here") is refreshed, the app saves a matching icon
to `/state/weather_icon.png`, and the menu (see `badge/apps/menu/app.py`) shows
it as the Weather tile. The menu picks it up the next time it opens.
