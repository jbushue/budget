"""
Alerts: the things worth knowing about today, in one list.

* overdue bills, and bills that can't be covered
* bills due in the next few days (Settings: alert_days_before_due)
* checking projected to drop below your cushion
* budgets that are over, or on pace to go over
* bill payments found in transactions waiting for review

Each alert has a stable ``key``; dismissing it hides it (for a number of
days, or until the situation changes and a new key appears). The same list
feeds the bell in the web UI, browser notifications, and the optional daily
email digest.
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from models import database as db

SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2}


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _dismissed(today: date) -> set[str]:
    session = db.get_session()
    try:
        rows = session.query(db.DismissedAlertModel).all()
        return {r.key for r in rows if r.until is None or r.until >= today}
    finally:
        session.close()


def dismiss(key: str, days: int | None = None, today: date | None = None) -> None:
    """Hide an alert; ``days`` = snooze length (None = until it changes)."""
    today = today or date.today()
    until = today + timedelta(days=days) if days else None
    session = db.get_session()
    try:
        row = session.query(db.DismissedAlertModel).filter_by(key=key).first()
        if row is None:
            session.add(db.DismissedAlertModel(key=key, until=until))
        else:
            row.until = until
        session.commit()
    finally:
        session.close()


def build_alerts(manager, today: date | None = None, include_dismissed: bool = False) -> list[dict]:
    from models.app_settings import get_settings
    from models.dashboard import build_dashboard
    today = today or date.today()
    settings = get_settings()
    alerts: list[dict] = []

    def add(key, severity, title, detail, link="/", when=None):
        alerts.append({"key": key, "severity": severity, "title": title, "detail": detail,
                       "link": link, "date": (when or today).isoformat()})

    dash = build_dashboard(manager, today)
    soon = today + timedelta(days=settings["alert_days_before_due"])
    for b in dash["bills_this_period"]:
        due = date.fromisoformat(b["due_date"])
        if b["status"] == "overdue":
            add(f"overdue:{b['bill_name']}:{b['due_date']}", "danger", f"{b['name']} is overdue",
                f"{_money(b['amount'])} was due {due:%b} {due.day}",
                "/bills", due)
        elif b["status"] == "short":
            add(f"short:{b['bill_name']}:{b['due_date']}", "danger", f"Not enough to pay {b['name']}",
                f"{_money(b['amount'])} due {due:%b %d} — short by {_money(b['short_by'] or b['amount'])}",
                "/optimizer", due)
        elif b["status"] in ("covered", "covered_by_plan") and today <= due <= soon:
            when = "today" if due == today else ("tomorrow" if due == today + timedelta(days=1) else f"{due:%a %b %d}")
            add(f"due:{b['bill_name']}:{b['due_date']}", "info", f"{b['name']} due {when}",
                f"{_money(b['amount'])}" + (f" from {b['source_account']}" if b.get("source_account") else ""),
                "/bills", due)

    if settings["alert_low_balance"] and dash.get("lowest_date"):
        lowest, cushion = dash["lowest_balance"], dash["cushion"]
        if lowest < cushion:
            low_day = date.fromisoformat(dash["lowest_date"])
            sev = "danger" if lowest < 0 else "warning"
            add(f"low:{dash['lowest_date']}:{int(lowest // 50)}", sev,
                "Checking is projected to go negative" if lowest < 0 else "Checking dips below your cushion",
                f"Lowest point {_money(lowest)} on {low_day:%b %d} (cushion {_money(cushion)})", "/timeline", low_day)

    try:
        from models.ledger import budget_status
        month = today.strftime("%Y-%m")
        for line in budget_status(month, today)["lines"]:
            if line["status"] == "over":
                add(f"budget-over:{line['category']}:{month}", "warning", f"{line['category']} is over budget",
                    f"{_money(line['spent'])} of {_money(line['budget'])} this month", "/budgets")
            elif line["status"] == "warning":
                add(f"budget-pace:{line['category']}:{month}", "info", f"{line['category']} is on pace to go over",
                    f"{_money(line['spent'])} spent, heading for {_money(line['projected'])} of "
                    f"{_money(line['budget'])}", "/budgets")
    except Exception:
        pass

    try:
        from models.bill_matching import suggestions
        pending = suggestions(manager, today)
        if pending:
            ids = ",".join(str(m["transaction"]["id"]) for m in pending)
            add(f"matches:{ids}", "info", f"{len(pending)} bill payment{'s' if len(pending) != 1 else ''} to review",
                "Found in your transactions — confirm so the bills show as paid", "/transactions")
    except Exception:
        pass

    if not include_dismissed:
        hidden = _dismissed(today)
        alerts = [a for a in alerts if a["key"] not in hidden]
    return sorted(alerts, key=lambda a: (SEVERITY_ORDER[a["severity"]], a["date"]))


# ─────────────────────────────────────────────────────────────────────────
#  Email digest
# ─────────────────────────────────────────────────────────────────────────

def digest_text(manager, today: date | None = None) -> tuple[str, str]:
    """(subject, body) for the daily digest."""
    from models.dashboard import build_dashboard
    today = today or date.today()
    dash = build_dashboard(manager, today)
    alerts = build_alerts(manager, today, include_dismissed=True)
    lines = [
        dash["status_title"],
        dash["status_detail"],
        "",
        f"Safe to spend: {_money(dash['safe_to_spend'])}"
        + (f" (about {_money(dash['safe_per_day'])}/day until payday)" if dash.get("next_payday") else ""),
        f"Checking now: {_money(dash['checking_now'])}; lowest ahead: {_money(dash['lowest_balance'])}",
        "",
    ]
    if alerts:
        lines.append("Needs attention:")
        lines += [f"  • {a['title']} — {a['detail']}" for a in alerts]
    else:
        lines.append("Nothing needs your attention today.")
    upcoming = [b for b in dash["bills_this_period"] if b["status"] != "paid"]
    if upcoming:
        lines += ["", "Bills this pay period:"]
        lines += [f"  {b['due_date']}  {b['name']:<28} {_money(b['amount']):>12}  {b['status'].replace('_', ' ')}"
                  for b in upcoming]
    icon = {"ok": "✅", "warning": "⚠️", "danger": "🚨"}.get(dash["status"], "")
    subject = f"{icon} Budget: {_money(dash['safe_to_spend'])} safe to spend" + (
        f", {sum(1 for a in alerts if a['severity'] == 'danger')} urgent" if any(a["severity"] == "danger" for a in alerts) else "")
    return subject, "\n".join(lines)


def send_digest(manager, force: bool = False, today: date | None = None) -> str:
    """Email the digest (once a day unless forced). Returns a status message; raises on SMTP errors."""
    from models.app_settings import get_settings, update_settings
    today = today or date.today()
    s = get_settings()
    if not force:
        if not s["email_enabled"]:
            return "Email digest is turned off"
        if s["last_digest_date"] == today.isoformat():
            return "Already sent today"
    if not s["smtp_host"] or not s["email_to"]:
        raise ValueError("Set the SMTP server and the email address to send to")
    subject, body = digest_text(manager, today)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s["smtp_user"] or s["email_to"]
    msg["To"] = s["email_to"]
    msg.set_content(body)
    port = int(s["smtp_port"] or 587)
    if port == 465:
        server = smtplib.SMTP_SSL(s["smtp_host"], port, timeout=20, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(s["smtp_host"], port, timeout=20)
        if s["smtp_use_tls"]:
            server.starttls(context=ssl.create_default_context())
    try:
        if s["smtp_user"]:
            server.login(s["smtp_user"], s["smtp_password"])
        server.send_message(msg)
    finally:
        server.quit()
    update_settings({"last_digest_date": today.isoformat()})
    return f"Digest sent to {s['email_to']}"


def digest_due(now: datetime | None = None) -> bool:
    """True when today's digest hasn't gone out yet (after 7am)."""
    from models.app_settings import get_settings
    now = now or datetime.now()
    s = get_settings()
    return bool(s["email_enabled"] and s["smtp_host"] and s["email_to"]
                and now.hour >= 7 and s["last_digest_date"] != now.date().isoformat())
