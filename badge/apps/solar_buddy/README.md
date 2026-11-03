# Solar Buddy

An animated solar companion that reads Home Assistant power sensors and recommends appliances after stable surplus.

This app targets the GitHub Universe 2026 Badgeware runtime at 320 x 240. Copy the
folder into `/system/apps/solar_buddy` through USB mass-storage mode, leaving out
`solar_buddy_secrets.json` and `__pycache__` (see below).

It starts with simulated data and requires no network in demo mode. Left/right
switch screens, up/down select a scenario or appliance, Select opens appliance
details or toggles demo/live in Settings, Back returns to Buddy, Menu opens Settings,
and Home returns to the launcher. Shake briefly wakes the face.

Copy `settings.example.json` to `settings.json` to customize thresholds, estimated
appliance loads, polling, freshness, and the 30-second stability period. The default
safety reserve is 100 W. All recommendations are read-only and apply to one load
at a time; they do not guarantee a solar-only appliance cycle.

An explicit offline/stale state suppresses advice when data is missing or invalid.
The app assumes there is no home battery. Only Solar Superstar is implemented;
daily statistics achievements need additional sensors.

## Home Assistant credentials

Live mode reads a private JSON file from `/state/solar_buddy_secrets.json` on the
badge or in the canvas. It never reads credentials from the app folder, and Wi-Fi
uses the badge's existing Wi-Fi settings (`/system/secrets.py` or the Settings app).

**On your computer**, keep the private copy at
`badge\apps\solar_buddy\solar_buddy_secrets.json`. The app's `.gitignore` excludes
it from Git; check with `git check-ignore -v badge/apps/solar_buddy/solar_buddy_secrets.json`.
Start from the committed, credential-free template and fill in your Home Assistant
URL, IPv4 address, long-lived access token, and three instantaneous power sensor
IDs. Replace the template's example sensor IDs if they do not match your setup;
never put a real token in the `.example.json` file.

```powershell
Copy-Item badge\apps\solar_buddy\solar_buddy_secrets.example.json `
  badge\apps\solar_buddy\solar_buddy_secrets.json
```

Create the token under your Home Assistant profile, **Security**, **Long-lived
access tokens**. Use three different instantaneous power sensors reported in W, kW,
or MW (find their IDs in **Developer tools**, **States**). `connect_ip` is required
unless `base_url` already uses an IPv4 address, so the badge avoids blocking DNS.
`allow_insecure_http` must be `true` for `http://` because the token travels
unencrypted; use it only on a trusted LAN. For `https://` on the badge, copy the
CA certificate to the badge (for example `/state/solar_buddy_ca.pem`), set
`"ca_file"` to that path, and make sure the badge clock is correct.

**On the badge**, copy the file over USB serial (`/state` is writable; `/system`
is not), then reset. Run one `mpremote` command at a time:

```powershell
mpremote devs
mpremote connect COM7 fs cp badge\apps\solar_buddy\solar_buddy_secrets.json :/state/solar_buddy_secrets.json
mpremote connect COM7 reset
```

Replace `COM7` with the port from `mpremote devs`. If `/state` is missing, run
`mpremote connect COM7 fs mkdir :/state` first. Do not copy
`solar_buddy_secrets.json` into `apps/solar_buddy` on the BADGER volume: the
Badge Simulator **Deploy** button and `deploy_app.py` copy the whole folder, so
delete `apps/solar_buddy/solar_buddy_secrets.json` from BADGER if it was copied.
Open Solar Buddy, press Menu, then Select to switch to live mode.

**In the Badge Simulator canvas**, the private file in the app folder is staged
(read-only) at `/system/apps/solar_buddy/solar_buddy_secrets.json`. Ask Copilot
to copy it to `/state`, or run this with the canvas `exec` action. It validates
the private copy made from the example above and does not print its contents:

```python
import json, os, config
with open("/system/apps/solar_buddy/solar_buddy_secrets.json") as f:
    data = f.read()
config.validate_secrets(json.loads(data))
try:
    os.mkdir("/state")
except OSError:
    pass
with open(config.DEVICE_SECRETS, "w") as f:
    f.write(data)
print("Copied to", config.DEVICE_SECRETS)
```

Then reload the app and switch to live mode in Settings. Repeat the copy after a
full canvas runtime restart (for example after files are added to, removed from,
or renamed in the app folder) or after editing the private file. A missing copy
shows `Live setup: No /state/solar_buddy_secrets.json` and Offline. See the next
section for canvas networking requirements.

## Badge Simulator canvas

Live mode automatically uses asynchronous browser HTTP on the canvas's
WebAssembly runtime. Physical badges and the desktop preview retain the
socket client. Requests remain read-only, time out, reject redirects, limit
responses to 16 KiB, and can be cancelled without blocking badge controls.

`/state/solar_buddy_secrets.json` lives in the canvas's **virtual** filesystem,
not on Windows; copy it there as described above. `settings.json` contains only
app settings, not connection details.

Browser networking uses `base_url` and browser DNS, not `connect_ip` (which is
still validated). `localhost`
means the computer hosting the canvas. Allow the canvas's exact origin (including
its port, shown in the canvas URL) in Home Assistant's `http.cors_allowed_origins`.
Browsers hide the HTTP `Date` header unless the server sends
`Access-Control-Expose-Headers: Date`, which Home Assistant's CORS settings
cannot configure. When `Date` is hidden, the canvas checks sensor freshness
against the computer's UTC clock instead and prints a one-time console notice.
Keep the computer and Home Assistant clocks synchronised (for example with NTP):
a skewed clock makes readings look stale, or rejects them as being ahead of the
clock. The physical badge always uses Home Assistant's `Date` header.
CORS, unreachable servers, authentication failures, and stale readings
are reported as errors; they never fall back to fabricated live data.
HTTPS uses browser certificate trust; `ca_file` is not supported in the canvas.
See [Home Assistant HTTP configuration](https://www.home-assistant.io/integrations/http/)
for CORS configuration. Do not disable browser security or TLS verification.
