# Ask

Ask your own AI gateway a question and read the answer on your badge.

The badge has no keyboard, so Ask offers a few ready-made prompts: an icebreaker,
a git tip, a haiku, a fortune cookie, a five-year-old explanation, a hot take
and a pep talk. Pick one and the badge sends it to an OpenAI-compatible chat
completions endpoint. That can be a [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
gateway, any other OpenAI-compatible server, or a bridge in front of one. The
answer appears as plain text.

## Requirements

Ask needs Wi-Fi and a gateway the badge's network can reach. Add these to
`secrets.py` on the badge (put it in disk mode by double-tapping RESET):

```python
WIFI_SSID = "your network"
WIFI_PASSWORD = "your password"
GATEWAY_URL = "https://gateway.example.com:8317"   # base URL, /v1, or the full /v1/chat/completions URL
GATEWAY_KEY = ""                                   # sent as "Authorization: Bearer ..."; leave empty if not needed
GATEWAY_MODEL = "claude-opus-5-5"                  # optional; a comma-separated list adds a model switcher
```

A badge already set up for the badge bridge (`BADGE_BRIDGE_URL` and
`BADGE_BRIDGE_TOKEN`) doesn't need the `GATEWAY_URL` and `GATEWAY_KEY` lines.
Ask then uses the bridge's `/gateway` route.

To use more than one Wi-Fi network, save the others too, for example
`WIFI_NETWORKS = {"Office Guest": "its password"}`. Ask joins the active
network if it can, and otherwise the strongest saved one in range. That network
then becomes the active one for every app.

Anyone holding your badge can read `secrets.py` in disk mode. Don't put a key
there that you can't afford to lose. Prefer a bridge that adds the real gateway
key on the server side and only takes a revocable token from the badge.
Otherwise use a key restricted to cheap, fast models (CLIProxyAPI's key scopes
can do this). Never commit a filled-in `secrets.py`.

The badge can't join a tailnet. A gateway that is only reachable over Tailscale
has to be exposed to the badge another way, for example through a bridge
published with Tailscale Funnel.

## Usage

| Button | Prompts | While thinking | Answer |
| --- | --- | --- | --- |
| Up / Down | Choose a prompt | | Scroll |
| Left / Right | Switch model (if more than one) | | |
| Select | Ask | | Ask again |
| Back | | Cancel | Back to the prompts |

The header shows the model in use. When an answer arrives, the footer shows how
long it took. If there is no answer, Ask explains why: the network can't find
the gateway, the key was refused, the model isn't available to that key, the
gateway is out of quota, or nothing came back within 45 seconds. Press Select to
try again.

If no saved Wi-Fi network can be joined, the No Wi-Fi page says why and keeps
trying in the background, counting down to the next try. Ask sends your
question as soon as the badge gets online. Press Select to try again now.

## Installing

Ask depends on the shared `inference` and `wifi_networks` modules in
[`badge/lib`](../../lib/README.md), which the badge keeps in `/system/lib`.
`deploy_app.py` copies them into `lib/` next to `apps/` on the `BADGER` drive
along with the app. To copy by hand, copy `apps/ask/`, `lib/inference.py` and
`lib/wifi_networks.py`.

## For other apps

Ask is the reference app for the shared [`inference`](../../lib/README.md)
module. Any app can use the same engine to ask an LLM a question:

```python
import inference

engine = inference.from_secrets()
engine.ask("Summarise this in one line: ...")
```

Call `engine.update()` once a frame until it returns `inference.DONE` or
`inference.FAILED`.
