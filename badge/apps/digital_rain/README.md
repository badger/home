# Digital Rain

A green falling-code screen saver that decodes your name, job title, company and GitHub handle in large text.

![Digital Rain decoding a name over falling green code](screenshot.png)

## Usage

Launch **Digital Rain** from the menu. Your details cycle just above the middle
of the screen, each one resolving out of scrambled glyphs, holding, then dissolving
back into the rain.

| Control | Action |
| --- | --- |
| Select | Show the next detail now |
| Up / Down | Faster / slower rain |
| Home | Return to the menu |

## Settings

The app shows these values from `secrets.py` on the badge, in this order:

| Key | Where to set it |
| --- | --- |
| `CONTACT_NAME` | **Settings** app (Contact Name) or `secrets.py` |
| `CONTACT_TITLE` | `secrets.py`, for example `CONTACT_TITLE = "Badge Hacker"` |
| `CONTACT_COMPANY` | `secrets.py`, for example `CONTACT_COMPANY = "Universe Labs"` |
| `GITHUB_USERNAME` | **Settings** app (GitHub Username) or `secrets.py` |

Empty values are skipped; with none set, the app asks you to add your details
in Settings.

No Wi-Fi or extra hardware is needed.
