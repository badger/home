# Badge bridge

A small authenticated web service that lets badge apps reach things on your
tailnet without the badge joining it. It runs on an always-on tailnet machine,
and Tailscale Funnel publishes just its `/badge` path over public HTTPS, so the
badge only needs Wi-Fi.

| Route | Auth | Purpose |
| --- | --- | --- |
| `GET /health` | none | Liveness probe, `{"ok":true}` |
| `GET /t3/status[?src=<host>]` | bearer | Compact T3 Code status for the `t3code` app |
| `POST /gateway/v1/chat/completions` | bearer | Clamped proxy to an OpenAI-compatible LLM gateway |

Every route also answers under `/badge/...`, which is how Funnel forwards them.

Node 22 or later, no dependencies.

## T3 Code status

For each configured T3 Code server the bridge opens the protocol-2 Effect RPC
WebSocket (`orchestration.subscribeShell`): one snapshot, then live deltas, so
a large history is sent once rather than polled. If the socket can't be opened
it falls back to `GET /api/orchestration/shell`. Each top-level thread becomes:

- `attention`: an approval or user-input request is pending (including one
  raised by a subagent)
- `working`: a run is preparing, queued, running or waiting, or background
  work holds completion
- `error`: the last run failed (or hit a usage limit) in the last 24 hours
- `done`: a run finished in the last 24 hours and the thread hasn't been viewed
- `idle`: everything else

The answer lists every source's health, the counts and up to twelve threads,
most urgent first, as ASCII-only text (about 3 KB). `?src=<name>` limits the
counts and threads to one source.

Each server needs a read-only `orchestration:read` token. On the server, with
the same T3 build as the running server:

```sh
t3 auth session issue --scope orchestration:read --label badge-bridge --ttl 30d --token-only
```

Or, from anywhere on the tailnet, create a pairing link in that server's T3
UI (Settings > Sharing & access) and exchange it:

```sh
curl -s -X POST "https://<host>.<tailnet>.ts.net/oauth/token" \
  --data-urlencode grant_type=urn:ietf:params:oauth:grant-type:token-exchange \
  --data-urlencode subject_token=<pairing token> \
  --data-urlencode subject_token_type=urn:t3:params:oauth:token-type:environment-bootstrap \
  --data-urlencode requested_token_type=urn:ietf:params:oauth:token-type:access_token \
  --data-urlencode scope=orchestration:read
```

Pairing tokens are single-use. Tokens expire after 30 days.

## Configuration

Keep the configuration in a private env file (mode 600), never in this
repository:

```sh
BADGE_BRIDGE_TOKEN=<random, 24+ characters; comma-separate several badges>
BADGE_BRIDGE_HOST=127.0.0.1
BADGE_BRIDGE_PORT=8787
BADGE_BRIDGE_RATE_PER_MIN=60

# T3 Code servers: name@url, each with BADGE_BRIDGE_T3_TOKEN_<NAME>
BADGE_BRIDGE_T3_SOURCES=laptop@https://laptop.example.ts.net,desktop@https://desktop.example.ts.net
BADGE_BRIDGE_T3_TOKEN_LAPTOP=<orchestration:read token>
BADGE_BRIDGE_T3_TOKEN_DESKTOP=<orchestration:read token>

# Optional LLM gateway proxy
BADGE_BRIDGE_GATEWAY_URL=http://127.0.0.1:8317
BADGE_BRIDGE_GATEWAY_KEY=<gateway key>
BADGE_BRIDGE_GATEWAY_MODELS=claude-opus-5-5
BADGE_BRIDGE_GATEWAY_MAX_TOKENS=400
```

Generate a token with `node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"`.

## Running it

Directly:

```sh
node --env-file=/path/to/env tools/badge_bridge/bridge.mjs
```

Or in Docker with host networking. Pin each T3 server's tailnet address if
the host doesn't resolve MagicDNS names (otherwise a Funnel-enabled name
resolves to its public ingress):

```sh
docker run -d --name badge-bridge --restart unless-stopped --network host \
  --add-host laptop.example.ts.net:100.x.y.z \
  --user 1000:1000 --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 512m --log-opt max-size=10m \
  -v /path/to/badge_bridge:/app:ro -v /path/to/env:/config/env:ro \
  node:24-bookworm-slim node --env-file=/config/env /app/bridge.mjs
```

Then publish only `/badge`, on a Funnel port that serves nothing else:

```sh
tailscale funnel --bg --https=10000 --set-path=/badge http://127.0.0.1:8787
```

Funnel is enabled per port, so never put it on a port that also serves
tailnet-only services. On Unraid, the Tailscale plugin removes Funnel every
minute unless Settings > Tailscale > Allow Funnel is on; its watcher only
reads that setting when it starts.

Check it from outside your tailnet (the name must resolve publicly):

```sh
curl https://<host>.<tailnet>.ts.net:10000/badge/health
```

### Port 443 for strict Wi-Fi

Guest and venue networks often allow only port 443. If the host already
serves something on 443, give the bridge its own Tailscale node and publish it
there. The node runs in userspace beside the bridge, with its own state:

```sh
docker run -d --name badge-funnel --restart unless-stopped --network host \
  -v /path/to/badge-funnel/state:/var/lib/tailscale \
  --entrypoint tailscaled tailscale/tailscale:stable \
  --tun=userspace-networking --statedir=/var/lib/tailscale \
  --socket=/tmp/tailscaled.sock --port=41642
TS="docker exec badge-funnel tailscale --socket=/tmp/tailscaled.sock"
$TS up --hostname=badge --accept-dns=false   # open the printed login link once
$TS funnel --bg --set-path=/badge http://127.0.0.1:8787
```

Badges then use `BADGE_BRIDGE_URL = "https://badge.<tailnet>.ts.net/badge"`.
The Funnel setting is kept in the node's state, so it survives restarts.
Run `tailscaled` directly as above: the image's default entrypoint exits if
the login link isn't approved within a minute, which restarts the container
and replaces the link.

## Security

- Every route but `/health` needs `Authorization: Bearer <BADGE_BRIDGE_TOKEN>`,
  compared in constant time. Each token is limited to
  `BADGE_BRIDGE_RATE_PER_MIN` requests a minute, and more than 30 bad tokens a
  minute locks out unauthenticated callers.
- T3 Code tokens are read-only (`orchestration:read`) and never leave the
  bridge. T3 Code itself stays tailnet-only.
- The gateway proxy replaces the badge's token with the gateway key, allows
  only the listed models, clamps `max_tokens`, forces `stream:false` and caps
  request bodies at 16 KB.
- CORS is allowed only for loopback origins, for the badge simulator.
- Logs record method, path, status and timing, never headers or bodies.

Anyone holding a badge can read its `secrets.py`, including the bridge token,
in USB Disk Mode. Rotate `BADGE_BRIDGE_TOKEN` if a badge is lost.

## Tests

```sh
cd tools/badge_bridge && node --test
```
