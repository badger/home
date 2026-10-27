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

## For other apps

`gateway.py` works on its own. It runs the request over the firmware's
`fetch.AsyncFetch` a little each frame, so the screen keeps drawing while the
model thinks, and it reuses the connection between questions:

```python
import gateway

ai = gateway.Gateway(url, key, "claude-opus-5-5")
ai.ask("Summarise this in one line: ...")

def update():
    if ai.update() == gateway.DONE:
        screen.text(ai.answer, 10, 10)
    elif ai.state == gateway.FAILED:
        screen.text(ai.error, 10, 10)
```

`ask(prompt, history)` takes earlier `{"role": ..., "content": ...}` messages
for follow-up questions. Answers are folded into characters the badge fonts
can draw, and markdown is stripped.

In the simulators the firmware's fetch library isn't available. `gateway.py`
falls back to a blocking `requests.post`, so it can only get real answers where
the simulator has network access.
