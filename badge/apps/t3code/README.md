# T3 Code

T3 Code shows which of your T3 Code agent threads are working, waiting on you, or done.

The badge can't join a tailnet, so a small bridge does that part: the
[badge bridge](../../../tools/badge_bridge/README.md) follows each of your T3
Code servers over Tailscale with a read-only token and publishes a compact
summary through Tailscale Funnel. The badge only needs Wi-Fi and plain HTTPS.

- Counts of threads that need you (an approval or a question), are working,
  failed in the last 24 hours, or finished in the last 24 hours and are unseen.
- Up to twelve threads, most urgent first, with host, project, status and age.
- Details for a thread: title, project, model, host and the latest message.
- Left and Right switch between all hosts and one host at a time.
- Case lights pulse while a thread needs you and breathe while agents work.

## Controls

| Button | Action |
| --- | --- |
| Up / Down | Choose a thread (in details: previous / next) |
| Select | Open or close details, or retry after an error |
| Back | Close details |
| Left / Right | All hosts, or one T3 Code host at a time |
| Menu | Case lights on or off |

## Setup

Run the badge bridge with your T3 Code servers configured (see its README),
then put the badge in USB Disk Mode and add these lines to `secrets.py` on the
`BADGER` volume, next to your Wi-Fi details:

```python
BADGE_BRIDGE_URL = "https://<bridge-host>.<tailnet>.ts.net:10000/badge"
BADGE_BRIDGE_TOKEN = "<the bridge's BADGE_BRIDGE_TOKEN>"
```

The app asks the bridge for `/t3/status` every five seconds and keeps showing
the last answer, marked stale, if the bridge can't be reached. A refused token
stops polling until you press Select. Never commit a filled `secrets.py`.
