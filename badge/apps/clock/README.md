# Clock

Display the time with selectable clock styles and time zones.

## Requirements

The time is fetched over the network (NTP), so Wi-Fi is required. Add your Wi-Fi details and the `REGION` and `TIMEZONE` values to `secrets.py` on the badge before using the app. `REGION` selects the daylight saving rules (us, cuba, eu, moldova, lebanon, egypt, chile, australia, nz).

## Usage

Use the buttons to switch between clock styles. The app connects to Wi-Fi and syncs the time when it starts.

SELECT retries a failed sync; it does not continuously retry every frame.
The internal RTC and firmware RTC helper now keep **UTC**. Timezone and
daylight-saving offsets are applied only to the displayed time, so opening
Clock no longer shifts time used by other apps or Universe reminders.
Sync once after updating if the RTC was previously set to local time.
Deploy the shared `badge/utc_clock.py` as `/system/utc_clock.py` along with
this app. Clock does not require the agenda app or reminder wrapper.
