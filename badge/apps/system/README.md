# System

A small status + settings screen for the badge.

- **Clock** — current local time and date.
- **Battery** — charge level and charging / on-battery state.
- **Time sync** — fetches UTC over NTP when WiFi is configured and writes it to
  the battery-backed PCF85063A RTC, so the clock survives a power cycle even
  without WiFi on the next boot.

## Controls

| Button   | Action                     |
|----------|----------------------------|
| **UP**   | Timezone +1 hour           |
| **DOWN** | Timezone −1 hour           |
| **A**    | Re-sync the time over NTP  |

The timezone offset (UTC−12 … UTC+14) is changed live with **UP** / **DOWN** and
saved automatically via the badge `State` store (`/state/system.json`), then
restored on the next boot. The RTCs always hold UTC; the offset is applied only
for display.
