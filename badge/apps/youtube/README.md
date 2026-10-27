# YouTube slideshow

Browse a YouTube channel's latest six videos with thumbnails, view counts, relative publication dates, and QR links.

## Setup

Configure Wi-Fi in the badge's Settings app. Set `CHANNEL_HANDLE` and
`CHANNEL_ID` in `config.py` to your channel's handle and 24-character ID
(starting with `UC`), then open **Youtube**.

The app uses YouTube's public feed without an API key. Slides advance every
10 seconds and refresh every 15 minutes. Cached videos remain available offline.
Scan a video's QR code with your phone to watch it.

The original blue-and-white video-player icon is included under the project's MIT license.
The app is self-contained; no badge menu changes are required.

## Controls

| Button | Action |
| --- | --- |
| Left / Right | Previous / next video |
| Select | Pause / resume slideshow |
| Up | Refresh and retry downloads |
| Down | Return to the home menu |
