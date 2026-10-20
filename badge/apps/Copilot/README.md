# Copilot

Monitor your GitHub Copilot coding sessions on the badge with an animated Agent Buddy.

Your **GitHub Copilot Agent Buddy** on the Universe 2026 badge, adapted from
[Dan Wahlin's Agent Buddy](https://github.com/DanWahlin/agent-buddy).
The badge monitors real coding sessions through **Agent Buddy's existing
desktop daemon**, showing Working, Needs attention, Complete, and Idle with the
original animated Copilot character, agent indicators, and usage text.

Only the **device-side client** is included here. The badge speaks Agent Buddy's
Wi-Fi device protocol; the upstream daemon and hooks still detect agent events,
aggregate concurrent sessions, prioritize attention, and calculate usage.
No daemon, hook installer, desktop app, or cloud service is copied into this
repository. The badge is a session display, not an AI inference engine.
An explicitly labeled offline Demo remains available.

## Install

Requires the **October 2026 Badgeware firmware** with the native `badge`,
`image`, `screen`, and logical button APIs. The older 2025 firmware and repository
Pygame simulator are not compatible.

Copy this complete directory to **`/system/apps/Copilot/`**, preserving its
capitalization. In USB mass-storage mode the volume root is `/system`, so copy
it to **`BADGER/apps/Copilot/`**. Eject the volume, restart the badge, and select
**Copilot** in the launcher. Do not replace the badge firmware or launcher.
The launcher discovers the directory automatically; `icon.png` is included for
PNG-based launchers. Launchers with a fixed vector-icon registry may use their
generic icon until a Copilot entry is added to that launcher's registry.

Required files are `__init__.py`, `copilot_monitor.py`, `icon.png`, and the entire `assets/` directory
(including the upstream license). No files from Agent Buddy's desktop or ESP32
firmware are needed. The character pack is under 3 MB on flash. Frames are
192 x 180 RGB PNGs; only one decoded frame is retained, and decoding happens
only when the animation frame changes, not on every display refresh.

| Button | Action |
| --- | --- |
| Up | Open a 60-second pairing window / cancel pairing |
| Down | Switch between live monitoring and the labeled offline demo |
| Left / Right | Change mood in Demo only; cannot override live session state |
| Select | Reload configuration / retry a connection or artwork error |
| Back | Return to the launcher |

## Connect to the existing Agent Buddy daemon

1. Install and configure **the upstream Agent Buddy daemon and agent hooks** on
   your computer using its own setup instructions. Keep both devices on the same
   trusted 2.4 GHz Wi-Fi LAN. Do **not** run its ESP32 firmware installer or
   character-pack uploader on this badge.
2. Create **`/copilot_config.json` on the badge's writable root**, not under
   `/system`, with your Wi-Fi settings:

   ```json
   {"ssid": "YOUR_NETWORK", "password": "YOUR_WIFI_PASSWORD"}
   ```

   If the badge already manages and connects its own Wi-Fi, use `{}` to reuse
   that connection instead. An optional `"port": 8080` changes the HTTP listener
   from its default port 80; discovery reports the chosen port.
   Copy your private configuration using `mpremote fs cp <private-file>
   :/copilot_config.json`; do not commit real credentials to this repository.
3. Launch Copilot. Once an IP address appears, press **Up** to display an
   eight-digit pairing code. In your **upstream Agent Buddy checkout**, run:

   ```sh
   npm run pair -- 12345678
   npm run connection -- wifi
   ```

   Replace the example code with the code on your badge. Agent Buddy discovers
   the badge over UDP port **4666**, then pairs and sends updates over HTTP.
   If broadcast discovery is blocked, the upstream CLI supports
   `npm run pair -- 12345678 --host BADGE_IP` on default HTTP port 80.
   Allow the daemon through the computer's local-network firewall.
4. Run a configured coding agent. The daemon sends the same session states,
   active-agent icons, and usage packets it sends to the original ESP32 device.
   Agent enablement, usage visibility, and usage windows remain settings in
   Agent Buddy. No separate bridge or badge-specific daemon is needed.

UDP broadcast discovery listens on `0.0.0.0` **only during the 60-second pairing
window opened with Up**. Its socket closes on expiry, cancellation, successful
pairing, or five incorrect attempts. The HTTP listener binds only to the badge's
current Wi-Fi address and remains available for authenticated monitoring.

Pairing requires physical access to the badge. The token and device ID persist privately
in **`/state/copilot_pairing.json`**; the daemon stores its side of the pairing
using its existing configuration. Restarting the app does not require pairing
again. Pairing/storage errors are reported instead of silently replacing keys.

The upstream protocol uses **unencrypted local HTTP with a bearer token**.
Use a trusted LAN; do not expose these ports to the Internet. Pairing is not
TLS or Bluetooth bonding. This port supports **Wi-Fi only**, not Agent Buddy's
ESP32 USB serial provisioning, firmware updates, character uploads, orientation
settings, sound, or captive-portal Wi-Fi setup. It identifies itself as
`github-universe-2026`, not an ESP32 board, and rejects update endpoints.

### Connection behavior

The UI explicitly shows configuration, pairing, and connection states. It
switches to live display only after receiving an authenticated state packet.
The daemon's regular authenticated status probes keep long-running work alive.
The daemon remembers the paired address, so normal reconnects do not require
discovery. If DHCP changes the badge's address, its HTTP listener rebinds and
invalidates stale session state. Press Up to temporarily enable discovery so
the daemon can find the new address; existing pairing tokens remain valid.
After 15 seconds without daemon contact, or if Wi-Fi drops, stale work,
indicators, and usage are no longer shown as live. A changed boot epoch causes
the existing daemon to resynchronize its full state on reconnect.

Down starts an independent, clearly marked Demo; incoming session updates
continue in the background. Down again immediately restores the latest real
state. Agent indicators show up to four of the daemon's active agents, with
blue/amber/green role bars. Up to two usage lines use the daemon's actual values.

Copilot still looks around, blinks, and dozes after two minutes in Idle.
Sleep is a character animation only: it does not suspend the device or change
the badge's brightness or power settings, and incoming work wakes it.
Missing or damaged artwork produces an error screen with Select to retry.

## Assets and development

Artwork is derived from Agent Buddy commit
`c246248cc091b59fb199c54ad7f40fab0836e00a` under the MIT license:
Copyright (c) 2026 Dan Wahlin. See `assets/LICENSE.txt` and `assets/sources.json`
for the upstream revision, individual source paths, and checksums. The badge
adaptation resizes the artwork onto black and samples 12 frames per movement;
the original Copilot character is preserved rather than redrawn.

From the repository root, with Pillow available:

```sh
.venv/bin/python tools/build_copilot_assets.py
.venv/bin/python -m unittest discover -s tests -p 'test_copilot*.py'
```

The asset builder downloads only public artwork and metadata from that pinned
revision. Character assets remain local; the monitor receives only bounded
state/icon/usage packets, not code, prompts, or session transcripts.
Compatibility is based on that same upstream revision's `wifi-transport.ts`,
`wifi-config.ts`, `DeviceCommands.h`, and `NetworkManager.cpp` (protocol 8's
state/badge/usage subset). Host tests cover real HTTP/UDP exchanges, pairing,
authentication, bounded parsing, stale sessions, reconnect epochs, live UI,
timing, controls, tick rollover, frame retention, errors, and asset integrity.
Native PNG decoding and display behavior require the real 2026 firmware.

For the hardware check, substitute the badge's serial port:

```sh
mpremote connect <badge-port> mount badge/apps/Copilot run tests/copilot_hardware_probe.py
```

This temporarily streams the app from the computer, checks pairing persistence,
protocol packets, and native HTTP/UDP listener setup, then checks all 101 frames
with native PNG decoding/display calls and checks frame-memory release.
It removes its temporary pairing/PNG test files and resets back to the launcher.
It does not install the app or alter your pairing/settings. Look for both
**`COPILOT_MONITOR_NATIVE_PASS`** and **`COPILOT_NATIVE_PASS 101`**; the final reset
can cause an expected serial disconnect. Confirm USB reappears afterwards.
The probe does not join Wi-Fi; the artwork portion disables the network monitor.
It does not prove a connection
to your desktop daemon; use the setup steps above for that end-to-end check.
