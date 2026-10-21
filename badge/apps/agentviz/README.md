# AgentViz

Explore live coding-agent activity on the badge with color-coded tracks, recent-event replay, and session statistics.

This is a badge-native adaptation of [Jay Parikh's AgentViz](https://github.com/jayparikh/agentviz),
not a browser port or a mascot/status demo. Its five lanes show **reasoning,
tool calls, context, output, and subagent lifecycle events**. Inspect individual
events with a playhead, see overlapping spans, highlight errors, replay recent
activity, and switch to counts, token totals, and common tools.

The small [host bridge](../../../tools/agentviz/README.md) uses **AgentViz's actual
format detection, parsers, and tool-result pairing**, not a second set of
badge-specific parsers. It supports Claude Code, Copilot CLI, Codex, VS Code
Copilot Chat, Copilot prompt exports, and ATIF imports at the pinned upstream
revision. This app does not use Agent Buddy or modify the existing Copilot app.

## Install on a Universe 2026 badge

Requires the current **October 2026 Badgeware firmware**, with native `badge`,
graphics, logical buttons, and MicroPython `network`/UDP sockets. Neither
`badge25/` nor upstream Tufty simulators establish compatibility.
No special hardware, inference API, account token, or cloud service is needed.
Live use requires the badge and bridge computer on the same trusted Wi-Fi LAN;
offline Demo needs no configuration.

Before deployment, discover the actual badge with `mpremote devs`, then use a
single explicit serial connection to check its firmware:

```sh
mpremote connect <port> exec "import sys, os; print(sys.implementation); print(os.uname())"
mpremote connect <port> fs ls :/system/apps
```

Read the [USB guide](../../../hardware/USB_SERIAL.md). Enter USB mass-storage
mode using the badge's Mass Storage app or supported reset gesture. **Inspect
the mounted volume first:** if it contains `apps/` and `main.py`, its root is
already `/system`; copy this complete `agentviz/` directory into `apps/`. If it
instead contains `system/`, copy into `system/apps/`. The final device path must
be **`/system/apps/agentviz/__init__.py`**, never `/system/system/apps/...`.
Eject cleanly and reset, then select **agentviz** in the launcher.

Keep `__init__.py`, `agentviz_client.py`, `icon.png`, this README, and
`LICENSE.agentviz` together. Do not replace firmware, launcher, other apps, or
`secrets.py`. Normal REPL `/system` writes are read-only; `mpremote fs cp` is
only used below for private config on the writable root.

## Connect live activity

Follow the [bridge setup](../../../tools/agentviz/README.md), including generating
a random shared token. Create a **private**, uncommitted `agentviz_config.json`:

```json
{
  "host": "192.168.1.10",
  "token": "REPLACE_WITH_32_LOWERCASE_HEX_CHARACTERS",
  "ssid": "YOUR_WIFI",
  "password": "YOUR_WIFI_PASSWORD"
}
```

`host` is the **sending computer's IPv4 LAN address**, not the badge address.
Copy the private file to the writable badge root, then reset:

```sh
mpremote connect <port> fs cp /path/to/private/agentviz_config.json :/agentviz_config.json
mpremote connect <port> reset
```

Omit `ssid`/`password` to reuse an already-connected badge Wi-Fi connection.
An optional integer `port` changes UDP port **9138**; use the same port in the
bridge config. The app displays its own IPv4 address while waiting. Pass that
address as `badge` in the host's config and allow **outbound UDP** to the badge
through the computer firewall. LAN client isolation can prevent delivery.
There is no UDP discovery, broadcast, inbound host listener, or pairing daemon.

The token is a separate random local secret, **not** a GitHub/API token.
Updates are accepted only from the configured host address, with the matching
token, bounded schema, and increasing sequence within a bridge epoch.
UDP is **unencrypted** and is not tamper-proof against a LAN observer who
captures the token. Use a trusted LAN; do not forward ports or use public Wi-Fi.
Only timing, track, sanitized tool/agent names, error flags and aggregate counts
leave the computer. No event text, prompts, code, paths, tool arguments, results,
transcripts, or credentials are forwarded.

## Controls and honest state

| Control | Action |
| --- | --- |
| Left / Right | Step through recent events; leave follow mode |
| Select | Play/pause recent events; at the end, restart from the oldest |
| Up | Follow newest activity; reload config and retry when offline |
| Down | Switch tracks / session statistics |
| Menu | Toggle clearly labeled synthetic Demo / real feed |
| Back | Exit and release sockets; retain previously managed Wi-Fi |

**LIVE FEED means the local bridge is connected**, not that an agent is running.
Unchanged session logs continue to receive connection heartbeats; historical
imports remain historical even with a connected bridge. Waiting, source errors,
configuration errors, and Wi-Fi failures are explicit. After **5 seconds** without
an accepted heartbeat, cached events remain inspectable but are marked
**OFFLINE**, never live. Wi-Fi loss invalidates live status immediately.
Menu Demo is always labeled **DEMO / SYNTHETIC**, never substituted for a lost
connection; live packets continue to be received in the background.

The badge retains the latest **24 normalized events**, not the whole transcript.
Statistics cover the complete parsed session. Review selection survives appends
until its event leaves the window, when a visible notice explains the move.
Source replacement/truncation, reordered normalized events, or bridge restart
starts a new epoch and resets the playhead instead of reassigning selected
evidence. Up resumes follow. Equal-time events remain separately selectable.

Durations marked `~` and bar spans are **upstream normalized durations**; some
formats use display placeholders rather than measured execution times.
Replay compresses gaps to 150-2000 ms per event; it is an activity review, not
wall-clock playback. Unknown token usage is `?`, not zero. There is no inferred
cost/health score, AI coach, transcript display, graph editor, cross-session
comparison, or independent agent monitoring platform.

## Source, attribution, and validation

Adapted from AgentViz commit
[`b4c924022745a588497098c241a91458213cf1a3`](https://github.com/jayparikh/agentviz/tree/b4c924022745a588497098c241a91458213cf1a3)
(MIT, Copyright (c) 2026 Jay Parikh). Track colors and the tracks/replay
interaction derive from its `theme.js`, Tracks/Replay views and normalized
session interfaces. See `LICENSE.agentviz`. The launcher icon is original
badge artwork; no screenshots or upstream transcript fixtures are packaged.

See the bridge README for reproducible host tests and an honestly labeled
drawing preview. Host tests cover real upstream parsers, HTTP/UDP, packet bounds,
privacy filtering, stale state/tick wrap, replay, demo separation, Wi-Fi loss,
and config errors. They do **not** verify native fonts, drawing, radio drivers,
touch/physical buttons, or automatic inversion.

Hardware-only acceptance: verify the actual 2026 runtime, install through mass
storage, confirm icon and readable five-lane rendering in both orientations,
join the real LAN, drive a real local coding session through the bridge, step
and replay events, disconnect/reconnect Wi-Fi and stop/restart the bridge,
check OFFLINE after five seconds, test Menu Demo and Back, and confirm the
normal launcher startup after reset. No physical badge was available in the
cloud implementation session.
