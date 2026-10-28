# AutoGPT

AutoGPT shows the live status of your AutoGPT agent runs and AutoPilot chats.

It talks to the AutoGPT Platform's v2 API with your API key over plain HTTPS,
so it only needs Wi-Fi. When the badge has the shared `wifi_networks` module
in `/system/lib`, it also joins any network saved in `WIFI_NETWORKS`.

- **Runs**: how many runs are running, queued or waiting for review, how many
  failed in the last 24 hours, your credit balance, the next scheduled run,
  and the six most recent runs with agent name, age, duration and cost.
- **AutoPilot**: your most recent Otto and Expert chats, and whether each is
  working, queued, idle or waiting on you. This tab needs the v2
  `GET /autopilot/sessions` endpoint and stays hidden on servers without it
  (it is retried every five minutes, so it appears once the server has it).
- **Case lights** pulse while a run waits for review or a chat needs you,
  blink after a new failure, and breathe while work is running.

## Controls

| Button | Action |
| --- | --- |
| Left / Right | Switch between Runs and AutoPilot |
| Up / Down | Choose a row (in details: previous / next) |
| Select | Open or close details, or retry after an error |
| Back | Close details |
| Menu | Case lights on or off |

## Setup

1. Create an API key at <https://platform.agpt.co/settings/api-keys> (dev:
   <https://dev-builder.agpt.co/settings/api-keys>) with read-only
   permissions: `IDENTITY`, `READ_RUN`, `READ_GRAPH`, `READ_LIBRARY`,
   `READ_CREDITS` and `READ_SCHEDULE`, plus `READ_AUTOPILOT` for the AutoPilot
   tab. Keys only work on the environment that issued them.
2. Add these lines to the badge's `secrets.py`, next to your Wi-Fi details.
   That's usually `secrets.py` on the `BADGER` volume (USB Disk Mode). If the
   badge's Settings app has saved its own `/secrets.py`, that file takes
   precedence: edit it over USB serial instead (`mpremote cp :/secrets.py .`,
   then copy it back).

   ```python
   AUTOGPT_API_KEY = "agpt_..."
   AUTOGPT_API_URL = "https://dev-server.agpt.co/api/v2"  # optional
   ```

   `AUTOGPT_API_URL` defaults to production (`https://backend.agpt.co/api/v2`).
   The header shows `prod`, `dev` or the host you set.

Anyone holding your badge can read `secrets.py` over USB, so use a
read-only key and revoke it when you no longer need it. Never commit a filled
`secrets.py`.

## How it works

Requests go one at a time over a single keep-alive TLS connection: run counts
and the run list every 30 seconds, credits and schedules every five minutes,
and each agent's name once (names are cached in `/state`). That is a handful
of requests a minute, far below the API's limit of 200. A rejected key (401)
or a server without the v2 API (404) stops polling until you press Select.
Times come from the API's `Date` header, so the badge clock doesn't need to be
set.

The browser simulator can't reach AutoGPT directly because the API doesn't
allow cross-origin requests from it; test against the real API on the badge.
