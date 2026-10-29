# Mona's Universe Agenda

Mona's Universe Agenda shows your saved Universe sessions and on-screen reminders across the awake badge's apps.

## Account connection

**Direct Universe account sync is not implemented.** A badge GitHub username
is not an authentication credential. Sign in at
https://reg.githubuniverse.com/flow/github/universe26/attendee-portal/login
using **Sign in with GitHub** or your Universe account. If login fails, use
the portal's account-recovery flow. Never put a password, cookie, OAuth code
or token in this app or in chat.

The app starts empty: no demo sessions are presented as your agenda.
An authorized agenda transfer is still required. No supported attendee-agenda
API has been verified, so this app does not scrape private endpoints or claim
live account synchronization. The transfer format below is a local integration
contract, not an assertion that the Universe portal exports this format.

## Usage

- LEFT/RIGHT switches between agenda and settings.
- UP/DOWN browses sessions or settings.
- SELECT in the agenda reloads `agenda.json`; in settings it changes the
  selected option or syncs the clock.
- Reminder lead time is selectable: 5, 10 (default), 15 or 30 minutes.
- Reminders can be disabled. HOME returns to the launcher.

Settings, sessions and already-notified session IDs persist under `/state`.
Simultaneous reminders queue one at a time. Each reminder appears for 12 seconds
without intercepting the current app's controls, once per session start.
The session is still available in the agenda after the banner disappears.
Past sessions do not trigger catch-up notifications.

## Agenda transfer format

Place a private `agenda.json` in this app directory during USB Disk Mode,
then select **reload agenda**. It is ignored by Git. It must contain a `source`
string describing the authorized source and an `events` array (maximum 128).
Each session requires unique string `id`, string `title`, UTC `start` and `end`
in `YYYY-MM-DDTHH:MM:SSZ` format, and optional string `location`.
Dates must be in 2026-2099, with end after start. An empty `events` array clears
the agenda. Imports validate completely before replacing existing sessions.
No personal agenda or credentials are bundled in the repository.

## Cross-app runtime installation

**Installing only this app is not sufficient for cross-app reminders.**
The integration deliberately also changes `/system/main.py` and adds
`/system/universe_agenda.py` and `/system/utc_clock.py`. Back up the existing
files and copy these three system files along with this app through USB Disk
Mode only, following `hardware/USB_SERIAL.md`. Do not deploy without approval.

`main.py` installs a cooperative wrapper around the firmware's `run` class
before launching the startup screen, menu or an app. This retains launcher
return values, loop duration, progress and HOME's normal reset behavior.
State survives HOME's reset, so already-delivered reminders are not replayed.
All standard `run(update)` apps, including the menu, receive the banner.
Apps using custom native/blocking loops cannot display it while blocked.
This is not a background OS process: no alerts during deep sleep, power-off,
USB Disk Mode, a stopped/crashed app or a blocking network operation.
There is no phone push notification or sound.

## Clock

Use Settings > Sync clock via WiFi after installing, especially if a USB tool
previously set the RTC to local time. Wi-Fi credentials belong in the badge's
standard Settings/secrets configuration, not this app. Sync sets the internal
clock to UTC and, when available, updates the firmware RTC helper. It verifies
the saved clock marker; a missing firmware helper is logged as internal-only sync.
Until a successful sync, reminders are held and an unset-clock message is shown.
Existing local RTC values cannot be reliably distinguished from UTC.

The agenda displays San Francisco (US Pacific) time with automatic daylight
saving transitions. Time-zone offsets are display-only; both RTCs remain UTC.
Full power-loss retention depends on the actual badge hardware/firmware and is
not guaranteed by this app.

## Verification

Host-side tests cover reminders, reboot deduplication, UTC conversion and runtime
wrapping. Static validation is not firmware or physical verification.
Before relying on reminders, test on the actual badge: sync time, import your
authorized agenda, check a near-future reminder in the menu and another app,
HOME/reopen, both orientations, enabled/disabled settings, overlapping sessions,
an invalid import, a failed sync and reboot. Verify the app's custom icon in
the menu (stock firmware may need the documented menu icon patch).
