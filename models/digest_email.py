"""
The daily digest as an HTML email.

Email clients ignore stylesheets and most modern CSS, so everything is
tables with inline styles, 600px wide, with system fonts. The plain-text
version (models.alerts.digest_text) goes in the same message for clients
that don't show HTML.
"""

from __future__ import annotations

from datetime import date, timedelta
from html import escape

# Palette (matches the web app)
INK = "#0f172a"
MUTED = "#64748b"
FAINT = "#94a3b8"
LINE = "#e2e8f0"
BG = "#f1f5f9"
CARD = "#ffffff"
PRIMARY = "#4f46e5"
TONES = {
    "ok": ("#047857", "#ecfdf5", "#10b981"),        # text, background, accent
    "warning": ("#b45309", "#fffbeb", "#f59e0b"),
    "danger": ("#b91c1c", "#fef2f2", "#ef4444"),
    "info": ("#1d4ed8", "#eff6ff", "#3b82f6"),
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
BILL_STATUS = {
    "covered": ("Covered", "ok"), "covered_by_plan": ("Covered by plan", "info"),
    "short": ("Short", "danger"), "overdue": ("Overdue", "danger"), "paid": ("Paid", "ok"),
}


def _m(v: float) -> str:
    return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"


def _d(iso: str | date | None) -> str:
    if not iso:
        return ""
    d = iso if isinstance(iso, date) else date.fromisoformat(str(iso)[:10])
    return f"{d:%a} {d:%b} {d.day}"


def _pill(text: str, tone: str) -> str:
    fg, bg, _ = TONES.get(tone, TONES["info"])
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:999px;background:{bg};color:{fg};'
            f'font-size:12px;font-weight:600;white-space:nowrap">{escape(text)}</span>')


def _section(title: str, body: str, link: str = "") -> str:
    more = (f'<a href="{escape(link)}" style="color:{PRIMARY};text-decoration:none;font-size:13px;'
            f'font-weight:600">View &rsaquo;</a>') if link else ""
    return f'''
<tr><td style="padding:0 24px 20px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CARD};border:1px solid {LINE};border-radius:12px">
    <tr><td style="padding:16px 18px 6px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{MUTED}">{escape(title)}</td>
        <td align="right">{more}</td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:4px 18px 14px">{body}</td></tr>
  </table>
</td></tr>'''


def _stat(label: str, value: str, sub: str = "", tone: str | None = None) -> str:
    color = TONES[tone][0] if tone else INK
    return f'''
<td valign="top" style="padding:0 6px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CARD};border:1px solid {LINE};border-radius:12px">
    <tr><td style="padding:14px 14px 12px">
      <div style="font-size:12px;color:{MUTED};font-weight:600">{escape(label)}</div>
      <div style="font-size:22px;font-weight:700;color:{color};margin-top:4px;letter-spacing:-.01em">{escape(value)}</div>
      <div style="font-size:12px;color:{FAINT};margin-top:2px">{escape(sub) if sub else "&nbsp;"}</div>
    </td></tr>
  </table>
</td>'''


def _row(left: str, right: str, sub: str = "", last: bool = False) -> str:
    border = "" if last else f"border-bottom:1px solid {LINE};"
    sub_html = f'<div style="font-size:12px;color:{MUTED};margin-top:2px">{sub}</div>' if sub else ""
    return (f'<tr><td style="padding:10px 0;{border}font-size:14px;color:{INK}">{left}{sub_html}</td>'
            f'<td align="right" style="padding:10px 0;{border}font-size:14px;color:{INK};white-space:nowrap">{right}</td></tr>')


def _table(rows: list[str]) -> str:
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _bar(percent: float, tone: str) -> str:
    pct = max(0.0, min(100.0, percent))
    color = TONES[tone][2]
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:6px"><tr>'
            f'<td style="background:{LINE};border-radius:999px;height:6px;line-height:6px;font-size:0">'
            f'<div style="width:{pct:.0f}%;background:{color};height:6px;border-radius:999px"></div></td></tr></table>')


def build(manager, today: date | None = None) -> tuple[str, str]:
    """(subject, html) for today's digest."""
    from models.alerts import build_alerts, digest_text
    from models.app_settings import get_settings
    from models.dashboard import build_dashboard

    today = today or date.today()
    subject, _ = digest_text(manager, today)
    dash = build_dashboard(manager, today)
    alerts = build_alerts(manager, today, include_dismissed=True)
    base = (get_settings().get("public_url") or "").rstrip("/")
    link = (lambda path: base + path) if base else (lambda path: "")
    tone = dash["status"] if dash["status"] in TONES else "info"
    fg, bg, accent = TONES[tone]
    icon = {"ok": "&#10004;", "warning": "!", "danger": "!"}.get(tone, "i")

    parts: list[str] = []

    # Status banner
    parts.append(f'''
<tr><td style="padding:0 24px 20px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{bg};border-radius:12px;border-left:5px solid {accent}">
    <tr>
      <td width="44" valign="top" style="padding:16px 0 16px 16px">
        <div style="width:30px;height:30px;line-height:30px;border-radius:999px;background:{accent};color:#fff;text-align:center;font-weight:700;font-size:15px">{icon}</div>
      </td>
      <td style="padding:16px 18px 16px 10px">
        <div style="font-size:17px;font-weight:700;color:{fg}">{escape(dash["status_title"])}</div>
        <div style="font-size:14px;color:{INK};margin-top:4px;line-height:1.45">{escape(dash["status_detail"])}</div>
      </td>
    </tr>
  </table>
</td></tr>''')

    # Stat tiles
    per_day = f"about {_m(dash['safe_per_day'])}/day until payday" if dash.get("next_payday") else ""
    low_tone = "danger" if dash["lowest_balance"] < 0 else ("warning" if dash["lowest_balance"] < dash["cushion"] else None)
    parts.append(f'''
<tr><td style="padding:0 18px 20px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    {_stat("Safe to spend", _m(dash["safe_to_spend"]), per_day, "ok" if dash["safe_to_spend"] > 0 else "warning")}
    {_stat("Checking now", _m(dash["checking_now"]), f"next payday {_d(dash['next_payday'])}" if dash.get("next_payday") else "")}
    {_stat("Lowest ahead", _m(dash["lowest_balance"]), _d(dash.get("lowest_date")), low_tone)}
  </tr></table>
</td></tr>''')

    # Needs attention
    if alerts:
        rows = []
        for i, a in enumerate(alerts[:8]):
            t = a["severity"] if a["severity"] in TONES else "info"
            rows.append(f'''<tr><td style="padding:8px 0{'' if i == len(alerts[:8]) - 1 else f';border-bottom:1px solid {LINE}'}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td width="6" style="background:{TONES[t][2]};border-radius:3px">&nbsp;</td>
    <td style="padding:2px 0 2px 12px">
      <div style="font-size:14px;font-weight:600;color:{INK}">{escape(a["title"])}</div>
      <div style="font-size:13px;color:{MUTED};margin-top:2px">{escape(a["detail"])}</div>
    </td>
  </tr></table>
</td></tr>''')
        if len(alerts) > 8:
            rows.append(f'<tr><td style="padding:8px 0 0;font-size:13px;color:{MUTED}">and {len(alerts) - 8} more</td></tr>')
        parts.append(_section(f"Needs attention ({len(alerts)})", _table(rows), link("/")))
    else:
        parts.append(_section("Needs attention",
                              f'<div style="font-size:14px;color:{TONES["ok"][0]};padding:6px 0">'
                              "&#10004; Nothing needs your attention today.</div>"))

    # Bills this pay period
    upcoming = [b for b in dash["bills_this_period"] if b["status"] != "paid"]
    paid = [b for b in dash["bills_this_period"] if b["status"] == "paid"]
    if upcoming or paid:
        rows = []
        for i, b in enumerate(upcoming):
            label, t = BILL_STATUS.get(b["status"], (b["status"].replace("_", " ").title(), "info"))
            src = f" &middot; from {escape(b['source_account'])}" if b.get("source_account") else ""
            rows.append(_row(f'<strong style="font-weight:600">{escape(b["name"])}</strong>',
                             f'<div style="font-weight:600">{_m(b["amount"])}</div><div style="margin-top:3px">{_pill(label, t)}</div>',
                             f"{_d(b['due_date'])}{src}", last=i == len(upcoming) - 1))
        total = sum(b["amount"] for b in upcoming)
        foot = (f'<div style="font-size:13px;color:{MUTED};padding-top:10px">{len(upcoming)} to pay, '
                f'<strong style="color:{INK}">{_m(total)}</strong> total'
                + (f" &middot; {len(paid)} already paid" if paid else "") + "</div>")
        parts.append(_section("Bills this pay period", _table(rows) + foot, link("/bills")))

    # Paychecks
    if dash.get("upcoming_income"):
        inc = dash["upcoming_income"][:4]
        rows = [_row(escape(i["name"]), f'<span style="color:{TONES["ok"][0]};font-weight:600">+{_m(i["amount"])}</span>',
                     _d(i["date"]), last=n == len(inc) - 1) for n, i in enumerate(inc)]
        parts.append(_section("Money coming in", _table(rows), link("/income")))

    # Benefits and other money
    other = [o for o in dash.get("other_money", []) if o["group"] in ("benefits", "cash") and
             (o["balance"] > 0 or o["refill_amount"] > 0)]
    if other:
        rows = []
        for n, o in enumerate(other):
            notes = [escape(o["label"])]
            if o["runs_out"]:
                notes.append(f'<span style="color:{TONES["warning"][0]}">runs out {_d(o["runs_out"])}</span>')
            if o["next_refill"]:
                notes.append(f"+{_m(o['refill_amount'])} on {_d(o['next_refill'])}")
            rows.append(_row(escape(o["account"]) + (f' <span style="color:{MUTED}">&middot; {escape(o["purpose"])}</span>'
                                                       if o["purpose"] else ""),
                             f'<strong>{_m(o["balance"])}</strong>', " &middot; ".join(notes), last=n == len(other) - 1))
        parts.append(_section("Benefits & other money", _table(rows), link("/accounts")))

    # Budgets
    try:
        from models.ledger import budget_status
        lines = [ln for ln in budget_status(today.strftime("%Y-%m"), today)["lines"] if ln.get("budget")]
        lines.sort(key=lambda ln: -(ln.get("percent") or 0))
        if lines:
            rows = []
            for n, ln in enumerate(lines[:5]):
                t = {"over": "danger", "warning": "warning"}.get(ln["status"], "ok")
                left = (f'<div style="font-weight:600">{escape(ln["category"])}</div>'
                        f'{_bar(ln.get("percent") or 0, t)}')
                right = f'{_m(ln["spent"])} <span style="color:{MUTED}">of {_m(ln.get("available") or ln["budget"])}</span>'
                rows.append(_row(left, right, last=n == len(lines[:5]) - 1))
            parts.append(_section(f"Budgets in {today:%B}", _table(rows), link("/budgets")))
    except Exception:
        pass

    # Tips
    tips = [t for t in dash.get("insights", []) if t.get("severity") in ("savings", "tip", "warning", "urgent")][:3]
    if tips:
        rows = [_row(f'<div style="font-weight:600">{escape(t["title"])}</div>', "",
                     escape(t.get("detail") or ""), last=n == len(tips) - 1) for n, t in enumerate(tips)]
        parts.append(_section("Ideas from the optimizer", _table(rows), link("/optimizer")))

    button = (f'''<tr><td align="center" style="padding:4px 24px 24px">
  <a href="{escape(link('/'))}" style="display:inline-block;background:{PRIMARY};color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 26px;border-radius:10px">Open your budget</a>
</td></tr>''' if base else "")

    html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{BG};font-family:{FONT};-webkit-font-smoothing:antialiased">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(dash["status_title"])} &middot; {_m(dash["safe_to_spend"])} safe to spend</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}">
<tr><td align="center" style="padding:24px 10px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;font-family:{FONT}">
  <tr><td style="padding:4px 24px 18px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <div style="font-size:13px;font-weight:700;color:{PRIMARY};letter-spacing:.04em;text-transform:uppercase">Daily digest</div>
        <div style="font-size:24px;font-weight:700;color:{INK};margin-top:2px;letter-spacing:-.02em">{today:%A}, {today:%B} {today.day}</div>
      </td>
      <td align="right" valign="bottom">{_pill({"ok": "All good", "warning": "Heads up", "danger": "Action needed"}.get(tone, "Update"), tone)}</td>
    </tr></table>
  </td></tr>
  {"".join(parts)}
  {button}
  <tr><td align="center" style="padding:0 24px 8px;font-size:12px;color:{FAINT};line-height:1.6">
    Sent by your budget app &middot; change or turn off in Settings &rsaquo; Alerts<br>
    Numbers assume bills are paid on their due dates and your usual everyday spending.
  </td></tr>
</table>
</td></tr>
</table>
</body></html>'''
    return subject, html
