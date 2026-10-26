"""Optional public-profile lookup on api.github.com to tune a Mona.

Only public fields are kept, and a GITHUB_TOKEN from secrets is sent to
api.github.com and nowhere else.
"""

import mona_dna

API = "https://api.github.com/users/"
USER_AGENT = "GitHub Universe Badge 2026"
KEEP = (
    "login", "name", "bio", "company", "location", "type", "created_at",
    "public_repos", "public_gists", "followers", "following", "site_admin",
)
TEXT_LIMIT = 160


def load_module(name):
    """A firmware module, or None where this runtime lacks it."""
    try:
        if name == "fetch":
            import fetch as module
        elif name == "requests":
            import requests as module
        elif name == "wifi":
            import wifi as module
        elif name == "missing_details":
            import missing_details as module
        elif name == "secrets":
            import secrets as module
        else:
            return None
    except Exception:
        return None
    return module


def token(load=load_module):
    secrets = load("secrets")
    try:
        return str(getattr(secrets, "GITHUB_TOKEN", "") or "").strip()
    except Exception:
        return ""


def headers_for(url, secret=""):
    headers = {"User-Agent": USER_AGENT}
    if secret and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + secret
    return headers


def slim(data):
    """The public profile fields ASCII Mona uses, or None if it isn't one."""
    if not isinstance(data, dict):
        return None
    login = data.get("login")
    if not isinstance(login, str) or not mona_dna.valid_handle(login):
        return None
    out = {}
    for key in KEEP:
        value = data.get(key)
        if isinstance(value, (bool, int)):
            out[key] = value
        elif isinstance(value, str):
            out[key] = mona_dna.clean_text(value, TEXT_LIMIT)
    return out


def reason(data, code=0):
    """A short, drawable reason a lookup failed."""
    if code == 404:
        return "no such GitHub user"
    message = data.get("message") if isinstance(data, dict) else None
    if isinstance(message, str) and message:
        low = message.lower()
        if "rate limit" in low:
            return "GitHub rate limit, try later"
        if "not found" in low:
            return "no such GitHub user"
        return mona_dna.clean_text(message, 40)
    if code == 403 or code == 429:
        return "GitHub rate limit, try later"
    if code and code != 200:
        return "GitHub said %d" % code
    if not isinstance(data, dict):
        return "bad reply from GitHub"
    return "no such GitHub user"
