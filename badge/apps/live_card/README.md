# KD's GitHub Badge

KD's GitHub Badge displays named messages and browsable history from a configurable web service.

![The badge showing a synced message](assets/live_card_screenshot.png)

## Usage

Install **Live Card** from the [badge app store](https://badger.github.io/apps/).
The launcher tile is **KD's GitHub Badge** with this repository's updated menu,
or **Live Card** on an older menu. UP selects a newer message and DOWN
selects an older one, fetching another page when needed. LEFT/RIGHT scroll
long message text. Enter (SELECT) refreshes and returns to the newest message.
HOME returns to the menu.

The newest page refreshes every 15 seconds, preserving the selected message by
ID when it remains on that page. Older pages are not refreshed automatically.
Only one page (up to 10 messages) is held in memory; cursor bookmarks allow
returning to newer pages. The newest page is cached under `/state/` for offline
use; uncached older pages need a connection. Errors preserve the displayed page.
Until a successful sync, the screen says "No messages yet". Names, headlines,
and messages must use printable ASCII.

## Configuration

The default history endpoint is `https://github-badge.exe.xyz/api/history`.
That endpoint must be reachable without the hosting provider's browser login.
Configure Wi-Fi in Settings and open the app; the default public endpoint needs
no access key. Anyone visiting `https://github-badge.exe.xyz/` can post messages.
All installations using this endpoint share the same feed, not a private feed
for each badge. Messages may contain unmoderated content, and availability
depends on this independently hosted service. Use your own compatible history
endpoint below for a separate feed.

For private servers, add these values to the **physical badge's**
`/system/secrets.py` using USB Disk Mode, never the tracked `badge/secrets.py`:

```python
LIVE_CARD_HISTORY_URL = "https://github-badge.exe.xyz/api/history"
LIVE_CARD_READ_TOKEN = "<reader key from the service's keys.json>"
```

Only the read-only reader key belongs on the badge. Do not copy the editor key.
For public endpoints, omit `LIVE_CARD_READ_TOKEN` or set it to `""`.
For a trusted local-network test only, set `LIVE_CARD_ALLOW_HTTP = True` and
use `http://<computer-LAN-IP>:8765/api/history`. HTTP exposes the reader key and messages
to the network; use HTTPS for real deployment. Never send these keys to another
host. The badge uses the existing firmware's asynchronous `fetch` helper
(10-second network timeout), leaving navigation responsive during a fetch.
Responses must be JSON objects under 12 KiB, containing `messages` (at most
10 entries, newest first) and `next_cursor` (null or a nonempty string, at most
512 characters). Each entry has a unique stable `id` (at most 128 characters),
`name` (1-32), `title` (1-32), `message` (1-160), `theme` (`lime`, `blue`, or
`pink`), and `created_at` (UTC ISO 8601 timestamp). The next page is requested
with a URL-encoded `cursor` query parameter. Empty history must use a null
cursor. Public history GET responses need `Access-Control-Allow-Origin: *`
for the simulator.

The endpoint must implement the history contract above; a single-card
`/api/card` service is not compatible. The old `LIVE_CARD_URL` setting does not
override the new history URL.
The simulator can fetch the public history endpoint through its browser network
bridge. Physical Wi-Fi, TLS, and controls still need hardware verification.
