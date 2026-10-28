# Shared libraries

Modules here are shared by several badge apps. On the badge they live in
`/system/lib` (the `lib/` folder next to `apps/` on the `BADGER` drive).

## Depending on a shared module

The badge's default import path is `['', '.frozen', '/rom', '/rom/lib',
'/lib']`. That doesn't include `/system/lib`, so add it before importing:

```python
import sys

if "/system/lib" not in sys.path:
    sys.path.append("/system/lib")

import inference
```

A module with the same name in the app's own folder wins, because the app's
folder comes first on the path.

- **Deploying:** `deploy_app.py` (in the `hyb26-skill`) copies every shared
  module an app imports, and the ones those import, into `lib/`. It keeps a
  backup of any module it changes. To copy by hand, put the module in `lib/`
  next to `apps/` on the `BADGER` drive.
- **Simulator:** the Badge Simulator canvas sends `badge/lib` along with the
  app, so dependent apps run there unchanged. It finds them even without the
  `sys.path` line, so `validate_app.py` warns when an app leaves that line out.
- **App store:** an app installed on its own, such as from the app store,
  doesn't bring its shared modules with it.

Shared modules must keep working on MicroPython. They must not block the frame
loop. They must not use the name of a firmware module (`wifi`, `fetch`,
`secrets`, ...). Never put credentials in them.

## `inference`: ask an LLM from any app

[`inference.py`](inference.py) sends a question to an OpenAI-compatible chat
completions gateway and hands back plain text the badge fonts can draw. That
gateway can be CLIProxyAPI, the badge bridge in front of it, or anything else
that speaks `POST /v1/chat/completions`. On the badge the request runs over the
firmware's `fetch.AsyncFetch` a little each frame, so the screen keeps
animating while the model thinks. The connection is reused between questions.
[Ask](../apps/ask/) is the reference app.

```python
engine = inference.from_secrets()        # reads secrets.py; raises inference.ConfigError

engine.ask("Summarise this build log in one sentence: ...")

def update():
    state = engine.update()              # call once a frame
    if state == inference.BUSY:
        draw_spinner()
    elif state == inference.DONE:
        draw_text(engine.answer)
    elif state == inference.FAILED:
        draw_text(engine.error)          # a short, screen-ready reason
```

### Settings

Settings come from `secrets.py` on the badge.

| Setting | Meaning |
| --- | --- |
| `GATEWAY_URL` | Gateway base URL, its `/v1` URL, or the full `/v1/chat/completions` URL |
| `GATEWAY_KEY` | Sent as `Authorization: Bearer ...`; optional |
| `BADGE_BRIDGE_URL`, `BADGE_BRIDGE_TOKEN` | Used when `GATEWAY_URL` is unset: questions go to the bridge's `/gateway` route with the bridge token |
| `GATEWAY_MODEL` | Model, or a comma-separated list (`inference.models()`); defaults to `claude-opus-5-5` |

The key always comes from the same pair as the URL, so a bridge token is never
sent to another gateway. Anyone holding the badge can read `secrets.py` in disk
mode, so use a revocable bridge token or a key limited to the models you want
to pay for.

### API

| Name | What it does |
| --- | --- |
| `from_secrets(model=None, **options)` | An `Engine` for the settings above. `options`: `system`, `max_tokens`, `timeout` |
| `missing()` | Settings to pass to `missing_details.show()`, or `[]` |
| `models()` | The `GATEWAY_MODEL` list |
| `Engine(url, key="", model=..., system=SYSTEM_PROMPT, max_tokens=400, timeout=45)` | One gateway, one question at a time |
| `engine.ask(prompt, history=None)` | Start a question. `history` is earlier `{"role", "content"}` messages, for follow-ups; asking again cancels any question still in flight |
| `engine.update()` | Move it along; returns `IDLE`, `BUSY`, `DONE` or `FAILED` |
| `engine.cancel()` | Drop the question in flight |
| `engine.answer`, `engine.error` | The plain-text answer, or why there isn't one |
| `engine.truncated` | The answer hit `max_tokens` |
| `engine.elapsed` | How long the last question took, in ms |
| `engine.model`, `engine.system` | Change between questions |
| `plain(text)` | Fold text into what the badge fonts can draw and strip markdown |
| `SYSTEM_PROMPT`, `DEFAULT_MODEL`, `__version__` | Defaults and the module version |

The default system prompt asks for plain text of at most 60 words. Pass your
own `system=` for other jobs, such as summarising an app's status.
`max_tokens=400` leaves room for models that think before answering. A
starved model fails with "used up its N tokens before it answered" rather than
an empty answer. The timeout counts seconds without any data.

## `wifi_networks`: several Wi-Fi networks

[`wifi_networks.py`](wifi_networks.py) lets the badge keep several Wi-Fi
networks and join whichever is in range. The firmware's `wifi.connect()` only
knows `WIFI_SSID`, and when it gives up it shows a full-screen error. A
`Roamer` works differently:

1. It tries the active network first.
2. If that fails, it scans and tries the saved networks in range, strongest
   first. Each network gets a second attempt, because a weak signal often fails
   once. A network that has joined but is still waiting for an address gets 10
   more seconds.
3. The network that works becomes the active one, so apps that only know
   `WIFI_SSID` join it next time.
4. If none works, `update()` returns `FAILED` and `status` says why. The roamer
   tries again on its own after 20 seconds, then 40, then every minute, as long
   as the app keeps calling `update()`. `restart()` tries again at once.

[Ask](../apps/ask/) is the reference app: it uses a `Roamer` to get online.

```python
roamer = wifi_networks.Roamer()

def update():
    if roamer.update() == wifi_networks.CONNECTED:   # call once a frame
        ...                                          # online
    else:
        draw_text(roamer.status)                     # "Joining ...", or why it failed
```

| Setting | Meaning |
| --- | --- |
| `WIFI_SSID`, `WIFI_PASSWORD` | The active network, which every app joins |
| `WIFI_NETWORKS` | The other saved networks, as `{"name": "password", ...}` |

Names match whatever case the network broadcasts.

| Name | What it does |
| --- | --- |
| `Roamer(try_seconds=15, remember=True, retry_seconds=(20, 40, 60))` | Joins a saved network a step at a time. `remember` makes the network that works the active one. After `FAILED` it waits each of `retry_seconds` in turn (the last repeats) and tries again; `None` leaves it `FAILED` until `restart()` |
| `roamer.update()` | Move it along; returns `CONNECTING`, `CONNECTED` or `FAILED`. A dropped connection starts it again |
| `roamer.restart(only=None)` | Start over now, back to the shortest retry wait. `only` joins that one saved network |
| `roamer.status`, `roamer.ssid`, `roamer.problems` | What it is doing (or why it failed), the network, and `(ssid, reason)` for each network that didn't work |
| `roamer.retry_in` | Whole seconds until it tries again on its own, while `FAILED`; otherwise `None` |
| `saved()`, `active()`, `current()` | Saved networks as `(ssid, password)` pairs with the active one first, `WIFI_SSID`, and the network the radio is on |
| `missing()` | `["WIFI_SSID"]` when no network is saved, for `missing_details.show()` |
| `scan()`, `in_range(visible=None)` | Visible networks as `{ssid: rssi}` (blocks about a second), and the saved ones among them, strongest first |
| `remember(ssid, password)` | Save a network and make it the active one |
| `save_settings(values)` | Set values in the badge's `/secrets.py`, keeping the rest. The file is only replaced if it still loads |

Don't call the firmware's `wifi.connect()` while a `Roamer` is joining. A
roamer scans only when the active network fails, so most starts don't stall.

## Simulators

In the simulators the firmware's `fetch` isn't available, so `inference` falls
back to a blocking `requests.post`. It sends that on the frame after `ask()`,
so a waiting screen is drawn first. The canvas simulator makes real requests
through the browser, so the gateway has to allow CORS from the simulator's
loopback origin.
