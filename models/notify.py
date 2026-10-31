"""
Phone push notifications through ntfy (https://ntfy.sh, or a self-hosted server).

Install the ntfy app, subscribe to a topic with a hard-to-guess name, and put
the topic URL in Settings → Alerts. New alerts at or above the chosen severity
are pushed once each; optionally a short summary goes out every morning.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime

PRIORITY = {"danger": "high", "warning": "default", "info": "low"}
TAGS = {"danger": "rotating_light", "warning": "warning", "info": "information_source"}
SEVERITY_RANK = {"info": 0, "warning": 1, "danger": 2}
MAX_PER_RUN = 5          # don't flood the phone after a long gap
REMEMBER = 300           # alert keys remembered as already pushed


def _header(value: str) -> str:
    # HTTP headers are Latin-1; ntfy reads RFC 2047 for anything else
    try:
        value.encode("latin-1")
        return value
    except UnicodeEncodeError:
        import base64
        return "=?UTF-8?B?" + base64.b64encode(value.encode()).decode() + "?="


def send(title: str, message: str, priority: str = "default", tags: str = "", click: str = "",
         settings: dict | None = None) -> None:
    """Send one notification. Raises ValueError (not set up) or OSError (couldn't reach ntfy)."""
    from models.app_settings import get_settings
    s = settings or get_settings()
    if not s["ntfy_url"]:
        raise ValueError("Set the ntfy topic URL first")
    headers = {"Title": _header(title), "Priority": priority}
    if tags:
        headers["Tags"] = tags
    if click:
        headers["Click"] = click
    if s["ntfy_token"]:
        headers["Authorization"] = f"Bearer {s['ntfy_token']}"
    req = urllib.request.Request(s["ntfy_url"], data=message.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise OSError(f"ntfy answered {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise OSError(f"Couldn't reach ntfy: {e.reason}") from e


def _link(s: dict, path: str) -> str:
    return s["public_url"].rstrip("/") + (path or "/") if s["public_url"] else ""


def push_new_alerts(manager, settings: dict | None = None) -> int:
    """Push alerts that haven't been pushed yet. Returns how many went out."""
    from models.alerts import build_alerts
    from models.app_settings import get_settings, update_settings
    s = settings or get_settings()
    if not (s["push_enabled"] and s["ntfy_url"]):
        return 0
    floor = SEVERITY_RANK[s["push_min_severity"]]
    pushed = list(s["pushed_alert_keys"])
    sent = 0
    for a in build_alerts(manager):
        if sent >= MAX_PER_RUN:
            break
        if SEVERITY_RANK.get(a["severity"], 0) < floor or a["key"] in pushed:
            continue
        send(a["title"], a["detail"], PRIORITY[a["severity"]], TAGS[a["severity"]], _link(s, a.get("link")), s)
        pushed.append(a["key"])
        sent += 1
    if sent:
        update_settings({"pushed_alert_keys": pushed[-REMEMBER:]})
    return sent


def summary_due(now: datetime | None = None, settings: dict | None = None) -> bool:
    from models.app_settings import get_settings
    now = now or datetime.now()
    s = settings or get_settings()
    return bool(s["push_enabled"] and s["ntfy_url"] and s["push_daily_summary"]
                and now.hour >= 7 and s["last_push_summary_date"] != now.date().isoformat())


def push_summary(manager, now: datetime | None = None) -> str:
    """The morning summary: the digest's subject as the title, its first lines as the body."""
    from models.alerts import digest_text
    from models.app_settings import get_settings, update_settings
    now = now or datetime.now()
    s = get_settings()
    subject, body = digest_text(manager, now.date())
    short = "\n".join(body.split("\n")[:12])
    send(subject, short, "low", "moneybag", _link(s, "/"), s)
    update_settings({"last_push_summary_date": now.date().isoformat()})
    return "Summary pushed"


def send_test() -> str:
    from models.app_settings import get_settings
    s = get_settings()
    send("Budget test notification", "Push notifications are working. 🎉", "default", "white_check_mark",
         _link(s, "/settings"), s)
    return "Test notification sent — check your phone"
