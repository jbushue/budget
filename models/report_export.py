"""
Downloadable reports (CSV or Excel) and a calendar file of upcoming bills
and paydays. Served from /files/reports/<kind>.<csv|xlsx> and
/files/calendar.ics (see models/web_routes.py).

Each report is a title, column headers and rows built from the same
projection the Timeline and Optimizer pages use.
"""

from __future__ import annotations

import csv
import io
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone

REPORTS = {
    "timeline": "Every projected payment, paycheck and transfer, day by day",
    "monthly": "Month-by-month income, payments and ending balances",
    "balances": "Each account's projected balance at the end of every day",
    "plan": "When to pay each bill, and from which account",
    "snapshot": "Every account and what it holds or owes today",
}

HIDDEN = {"BILL_ALREADY_PAID", "MORTGAGE_ALREADY_PAID", "HELOC_ALREADY_PAID", "BILL_GROUP_ALREADY_PAID"}
TRANSFERS = {"SAVINGS_SWEEP", "SAVINGS_RECALL", "HELOC_PARK", "HELOC_RECALL"}


def event_label(kind: str) -> str:
    return kind.replace("_", " ").capitalize().replace("Heloc", "HELOC")


def _d(v) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _projection(manager, days: int) -> dict:
    return manager.project_balances(end_date=date.today() + timedelta(days=days))


def _timeline(manager, days):
    result = _projection(manager, days)
    rows = []
    for cf in result["cash_flow"]:
        if cf["type"] in HIDDEN:
            continue
        rows.append([_d(cf["date"]), event_label(cf["type"]), cf.get("description", ""), round(cf["amount"], 2),
                     cf.get("bank", cf.get("from_bank", "")), cf.get("account", cf.get("from_account", "")),
                     "Deferred" if cf["type"].endswith("DEFERRED") else ""])
    rows.sort(key=lambda r: r[0])
    return ["Date", "Type", "Description", "Amount", "Bank", "Account", "Note"], rows


def monthly_summary(manager, days: int = 180) -> list[dict]:
    """Per month: money in, money out (bills, card and loan payments, spending, fees), and the
    cash and debt totals at the end of the month."""
    result = _projection(manager, days)
    months: "OrderedDict[str, dict]" = OrderedDict()

    def month(key):
        return months.setdefault(key, {"month": key, "income": 0.0, "payments": 0.0, "spending": 0.0,
                                       "interest": 0.0, "fees": 0.0, "end_cash": 0.0, "end_debt": 0.0})

    for cf in result["cash_flow"]:
        kind = cf["type"]
        if kind in HIDDEN or kind in TRANSFERS or kind.endswith("DEFERRED"):
            continue
        m = month(_d(cf["date"])[:7])
        amt = abs(cf["amount"])
        if kind in ("INCOME", "ACCOUNT_REFILL"):
            m["income"] += amt
        elif kind == "INTEREST":
            m["interest"] += cf["amount"]
        elif kind == "FEE":
            m["fees"] += amt
        elif kind in ("EVERYDAY_SPENDING", "ACCOUNT_SPENDING", "PURCHASE"):
            m["spending"] += amt
        else:
            m["payments"] += amt
    for snap in result["snapshots"]:
        m = month(_d(snap["date"])[:7])
        m["end_cash"] = sum(snap["balances"].values())
        m["end_debt"] = (sum(snap.get("credit_balances", {}).values()) + sum(snap.get("mortgage_balances", {}).values())
                         + sum(snap.get("heloc_balances", {}).values()))
    out = []
    for m in months.values():
        m = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items()}
        m["net"] = round(m["income"] - m["payments"] - m["spending"] - m["fees"] + m["interest"], 2)
        out.append(m)
    return out


def _monthly(manager, days):
    rows = [[m["month"], m["income"], m["payments"], m["spending"], m["fees"], m["interest"], m["net"],
             m["end_cash"], m["end_debt"]] for m in monthly_summary(manager, days)]
    return ["Month", "Income", "Bills & payments", "Everyday spending", "Fees", "Interest (net)", "Net change",
            "Cash at month end", "Debt at month end"], rows


def _balances(manager, days):
    result = _projection(manager, days)
    keys: list[tuple[str, str]] = []
    for snap in result["snapshots"]:
        for group in ("balances", "credit_balances", "mortgage_balances", "heloc_balances"):
            for k in snap.get(group, {}):
                if (group, k) not in keys:
                    keys.append((group, k))
    owed = {"credit_balances": " (owed)", "mortgage_balances": " (owed)", "heloc_balances": " (owed)"}
    headers = ["Date"] + [k.replace(":", " / ") + owed.get(g, "") for g, k in keys]
    rows = [[_d(s["date"])] + [round(s.get(g, {}).get(k, 0.0), 2) for g, k in keys] for s in result["snapshots"]]
    return headers, rows


def _plan(manager, days):
    out = manager.payment_insights(days=days)
    rows = []
    for t in out.get("bill_timing", []):
        if t.get("status") == "already_paid":
            continue
        rows.append([t["due_date"], t.get("pay_early_date") or "", t["name"], t["amount"],
                     " / ".join(x for x in (t.get("source_bank"), t.get("source_account")) if x),
                     (t.get("plan_status") or t.get("status") or "").replace("_", " "), t.get("advice", "")])
    return ["Due", "Pay on", "Bill", "Amount", "From", "Status", "Advice"], rows


def _snapshot(manager, days):
    rows = []
    for b in manager.banks:
        for n, a in b.accounts.items():
            rows.append([b.name, n, a.account_type.value.capitalize(), round(a.balance, 2), "", a.interest_rate])
        for n, a in b.credit_accounts.items():
            rows.append([b.name, n, "Card / loan", round(-a.balance, 2), a.credit_limit, a.interest_rate])
        for n, a in b.mortgage_accounts.items():
            rows.append([b.name, n, "Mortgage", round(-a.current_principal, 2), "", a.interest_rate])
        for n, a in b.heloc_accounts.items():
            rows.append([b.name, n, "HELOC", round(-a.balance, 2), a.credit_limit, a.interest_rate])
    total = round(sum(r[3] for r in rows), 2)
    rows.append(["", "Net (accounts only)", "", total, "", ""])
    return ["Bank", "Account", "Type", "Balance", "Limit", "Rate"], rows


BUILDERS = {"timeline": _timeline, "monthly": _monthly, "balances": _balances, "plan": _plan, "snapshot": _snapshot}


def build(manager, kind: str, days: int = 90) -> tuple[list[str], list[list]]:
    if kind not in BUILDERS:
        raise KeyError(kind)
    return BUILDERS[kind](manager, max(7, min(int(days), 730)))


def to_csv(headers, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def to_xlsx(title: str, headers, rows) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2563EB")
    for r in rows:
        ws.append(r)
    money_cols = {i for i, h in enumerate(headers) if h not in ("Date", "Due", "Pay on", "Month", "Rate", "Type",
                                                                 "Description", "Bank", "Account", "Note", "Bill",
                                                                 "From", "Status", "Advice")}
    for row in ws.iter_rows(min_row=2):
        for i, c in enumerate(row):
            if i in money_cols and isinstance(c.value, (int, float)):
                c.number_format = '"$"#,##0.00;[Red]-"$"#,##0.00'
    for i, h in enumerate(headers, 1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:200]]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(width, 60)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Calendar (.ics) ──────────────────────────────────────────────────────

def _ics_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar_ics(manager, days: int = 180) -> bytes:
    """All-day events for every bill due date and payday in the next `days` days."""
    start = date.today()
    end = start + timedelta(days=days)
    events = []
    for bill in manager.bills:
        d = start - timedelta(days=1)
        for _ in range(400):
            nxt = bill.get_next_due_date(d)
            if nxt is None or nxt == date.max or nxt > end:
                break
            if nxt <= d:
                break
            amt = getattr(bill, "effective_amount", bill.amount)
            events.append((nxt, f"{bill.bill_name.replace('[Auto] ', '')} due · ${amt:,.2f}", "bill", bill.bill_name))
            d = nxt
    for inc in manager.income_sources:
        for d in inc.get_pay_dates_in_range(start, end):
            events.append((d, f"Payday: {inc.source_name} · ${inc.amount:,.2f}", "income", inc.source_name))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Budget//Bills and paydays//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Bills & paydays"]
    for d, summary, kind, key in sorted(events):
        uid = f"{kind}-{''.join(ch for ch in key if ch.isalnum())}-{d.isoformat()}@budget"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}", f"SUMMARY:{_ics_text(summary)}",
                  "TRANSP:TRANSPARENT"]
        if kind == "bill":
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_text(summary)}", "TRIGGER:-P1D", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")
