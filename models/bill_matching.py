"""
Recognize bill payments in your transactions, and spot recurring charges
that aren't set up as bills yet.

Matching
--------
An outgoing transaction matches a bill when it's near one of the bill's due
dates (10 days before to 7 days after) and the amount fits. Confidence:

* high   — the amount fits AND the description names the bill (or matches
           the payee of an earlier confirmed payment for it)
* medium — the amount is an exact match but the description doesn't say

High-confidence matches are recorded automatically after an import when
"auto_match_bills" is on (Settings). Everything else is offered as a
suggestion. Recording a match marks the bill paid WITHOUT moving money —
the transaction already happened, your balances already reflect it.

Recurring charges
-----------------
Outgoing transactions from the same payee that repeat on a steady schedule
(weekly, every two weeks, monthly, quarterly, yearly) with similar amounts
are offered as "add this as a bill?" suggestions, unless they're already a
bill or you dismissed them.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from models import database as db
from models import ledger
from models.fixed_bill import AccountLinkedBill, FloatingBill, GroupLinkedBill

NOT_A_BILL = "__none__"  # matched_bill value for "this transaction isn't a bill payment"
EARLY_DAYS, LATE_DAYS = 10, 7
LOOKBACK_DAYS = 45

_STOP = {"payment", "bill", "the", "and", "auto", "loan", "card", "pmt", "online", "inc", "llc", "co", "com"}


def _words(text: str) -> set[str]:
    return {w for w in ledger.normalize_payee(text).split() if len(w) >= 3 and w not in _STOP} | \
        {w for w in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split()
         if len(w) >= 3 and w not in _STOP and not w.isdigit()}


def _bill_words(bill) -> set[str]:
    names = [bill.bill_name.replace("[Auto]", "")]
    if isinstance(bill, AccountLinkedBill):
        names += [bill.linked_bank_name, bill.linked_account.account_name]
    if isinstance(bill, GroupLinkedBill):
        names.append(bill.linked_group.group_name)
    out = set()
    for n in names:
        out |= _words(n)
    return out


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _nearest_due(bill, when: date) -> date | None:
    """The bill due date closest to `when` within the matching window."""
    try:
        d = bill.get_next_due_date(when - timedelta(days=LATE_DAYS + 1))
    except Exception:
        return None
    if d == date.max or not (when - timedelta(days=LATE_DAYS) <= d <= when + timedelta(days=EARLY_DAYS)):
        return None
    return d


def _already_paid(bill, due: date, exclude: tuple | None = None) -> bool:
    history = bill.payment_history
    if isinstance(bill, GroupLinkedBill) and not history:
        history = bill.linked_group.payment_history
    for h in history:
        d = _as_date(h.get("date"))
        if d is None:
            continue
        if exclude and d == exclude[0] and abs(float(h.get("amount_paid") or 0) - exclude[1]) < 0.01:
            continue
        if due - timedelta(days=EARLY_DAYS + 20) <= d <= due + timedelta(days=LATE_DAYS):
            return True
    return False


def _amount_fits(bill, amount: float) -> tuple[bool, bool]:
    """(fits, exact)."""
    expected = bill.effective_amount
    if isinstance(bill, AccountLinkedBill):
        owed = bill.linked_account_balance
        exact = abs(amount - expected) <= 0.01 or abs(amount - owed) <= 0.01
        return (0 < amount <= max(owed, expected) + 1.0), exact
    exact = abs(amount - expected) <= max(0.01, expected * 0.005)
    if isinstance(bill, FloatingBill):
        lo = getattr(bill, "min_amount", None) or expected * 0.6
        hi = getattr(bill, "max_amount", None) or expected * 1.5
        return lo * 0.9 <= amount <= hi * 1.1, exact
    return abs(amount - expected) <= max(1.0, expected * 0.03), exact


def _learned_payees() -> dict[str, set[str]]:
    """bill name -> normalized payees of transactions previously matched to it."""
    out: dict[str, set[str]] = {}
    session = db.get_session()
    try:
        for t in session.query(db.LedgerTransactionModel).filter(
                db.LedgerTransactionModel.matched_bill.isnot(None),
                db.LedgerTransactionModel.matched_bill != NOT_A_BILL).all():
            key = ledger.normalize_payee(t.description)
            if key:
                out.setdefault(t.matched_bill, set()).add(key)
    finally:
        session.close()
    return out


def score(bill, txn: dict, learned: dict | None = None) -> dict | None:
    """Match details for one bill/transaction pair, or None if they don't match."""
    amount = -txn["amount"]
    when = _as_date(txn["date"])
    if amount <= 0 or when is None:
        return None
    due = _nearest_due(bill, when)
    if due is None:
        return None
    fits, exact = _amount_fits(bill, amount)
    if not fits:
        return None
    named = bool(_bill_words(bill) & _words(txn["description"] + " " + (txn.get("payee") or "")))
    seen = ledger.normalize_payee(txn["description"]) in (learned or {}).get(bill.bill_name, set())
    if named or seen:
        confidence = "high"
        reason = "same payee as before" if seen else "description names the bill"
    elif exact and not isinstance(bill, AccountLinkedBill):
        confidence = "medium"
        reason = "exact amount near the due date"
    else:
        return None
    return {"bill": bill, "due": due, "confidence": confidence, "reason": reason,
            "amount": round(amount, 2), "days_from_due": (when - due).days}


def _candidates(manager):
    grouped = manager.get_grouped_account_keys()
    for bill in manager.bills:
        if isinstance(bill, AccountLinkedBill) and (bill.linked_bank_name, bill.linked_account.account_name) in grouped:
            continue
        yield bill


def find_matches(manager, today: date | None = None, days: int = LOOKBACK_DAYS) -> list[dict]:
    """Best bill for each recent unmatched outgoing transaction."""
    today = today or date.today()
    txns = [t for t in ledger.all_transactions(today - timedelta(days=days))
            if t["amount"] < 0 and not t["matched_bill"] and not t.get("not_a_bill")]
    if not txns:
        return []
    learned = _learned_payees()
    bills = list(_candidates(manager))
    out, used = [], set()
    rank = {"high": 0, "medium": 1}
    scored = []
    for t in txns:
        options = [s for s in (score(b, t, learned) for b in bills) if s]
        options = [s for s in options if not _already_paid(s["bill"], s["due"])]
        if options:
            options.sort(key=lambda s: (rank[s["confidence"]], abs(s["days_from_due"])))
            scored.append((t, options[0]))
    # One transaction per bill due date: keep the strongest, closest one
    scored.sort(key=lambda ts: (rank[ts[1]["confidence"]], abs(ts[1]["days_from_due"])))
    for t, s in scored:
        key = (s["bill"].bill_name, s["due"])
        if key in used:
            continue
        used.add(key)
        out.append({"transaction": t, "bill_name": s["bill"].bill_name, "due_date": s["due"].isoformat(),
                    "confidence": s["confidence"], "reason": s["reason"], "amount": s["amount"]})
    return sorted(out, key=lambda m: m["transaction"]["date"], reverse=True)


def _record(manager, txn: dict, bill, due: date | None, today: date | None = None) -> None:
    from models.dashboard import settle_paid_flag
    manager.record_bill_paid(bill, -txn["amount"], _as_date(txn["date"]),
                             txn["bank_name"] or "", txn["account_name"] or "")
    # The payment was for a due date that has passed: the upcoming one is still owed
    settle_paid_flag(bill, due is not None and due < (today or date.today()))
    ledger.update_transaction(txn["id"], matched_bill=bill.bill_name)


def auto_match(manager, today: date | None = None) -> int:
    """Record high-confidence matches (if enabled in settings). Returns how many."""
    from models.app_settings import get_setting
    if not get_setting("auto_match_bills"):
        return 0
    n = 0
    for m in find_matches(manager, today):
        if m["confidence"] != "high":
            continue
        bill = next((b for b in manager.bills if b.bill_name == m["bill_name"]), None)
        if bill is not None:
            _record(manager, m["transaction"], bill, date.fromisoformat(m["due_date"]), today)
            n += 1
    if n:
        manager.save_to_database()
    return n


def suggestions(manager, today: date | None = None) -> list[dict]:
    """Matches waiting for you to confirm (everything not auto-recorded)."""
    from models.app_settings import get_setting
    auto = get_setting("auto_match_bills")
    return [m for m in find_matches(manager, today) if not (auto and m["confidence"] == "high")]


def confirm_match(manager, txn_id: int, bill_name: str) -> None:
    bill = next((b for b in manager.bills if b.bill_name == bill_name), None)
    if bill is None:
        raise ValueError(f"Bill '{bill_name}' not found")
    txn = _get_txn(txn_id)
    if txn["amount"] >= 0:
        raise ValueError("Only money going out can pay a bill")
    if txn["matched_bill"]:
        raise ValueError(f"Already recorded as {txn['matched_bill']}")
    _record(manager, txn, bill, _nearest_due(bill, _as_date(txn["date"])))
    manager.save_to_database()


def ignore_match(txn_id: int) -> None:
    """This transaction isn't a bill payment — stop suggesting it."""
    _get_txn(txn_id)
    ledger.update_transaction(txn_id, matched_bill=NOT_A_BILL)


def unmatch(manager, txn_id: int) -> None:
    """Undo a match: forget the link and remove the payment it recorded."""
    txn = _get_txn(txn_id)
    name = txn["matched_bill"]
    ledger.update_transaction(txn_id, matched_bill=None)
    bill = next((b for b in manager.bills if b.bill_name == name), None) if name else None
    if bill is None:
        return
    when, amount = _as_date(txn["date"]), -txn["amount"]
    histories = [bill.payment_history]
    if isinstance(bill, GroupLinkedBill):
        histories.append(bill.linked_group.payment_history)
    removed_last = False
    for history in histories:
        for i in range(len(history) - 1, -1, -1):
            h = history[i]
            if _as_date(h.get("date")) == when and abs(float(h.get("amount_paid", h.get("amount", 0)) or 0) - amount) < 0.01:
                removed_last = removed_last or i == len(history) - 1
                history.pop(i)
                break
    if removed_last:
        bill.is_paid_this_period = False
        if isinstance(bill, GroupLinkedBill):
            bill.linked_group.is_paid_this_period = False
    manager.save_to_database()


def _get_txn(txn_id: int) -> dict:
    session = db.get_session()
    try:
        t = session.get(db.LedgerTransactionModel, txn_id)
        if t is None:
            raise ValueError("Transaction not found")
        return ledger._to_dict(t)
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────
#  Recurring charges
# ─────────────────────────────────────────────────────────────────────────

_PATTERNS = [  # (frequency, typical days, tolerance)
    ("weekly", 7, 2),
    ("biweekly", 14, 3),
    ("monthly", 30.4, 5),
    ("quarterly", 91, 10),
    ("yearly", 365, 20),
]


def detect_recurring(manager, today: date | None = None, days: int = 400) -> list[dict]:
    """Repeating outgoing charges that aren't bills yet (and weren't dismissed)."""
    from models.app_settings import get_setting
    today = today or date.today()
    dismissed = set(get_setting("dismissed_recurring") or [])
    cats = {c["name"]: c for c in ledger.list_categories()}
    bill_words = [_bill_words(b) for b in manager.bills] if manager else []

    groups: dict[str, list[dict]] = {}
    for t in ledger.all_transactions(today - timedelta(days=days)):
        if t["amount"] >= 0 or t["matched_bill"]:
            continue
        c = cats.get(t["category"]) if t["category"] else None
        if c and c["kind"] != "expense":
            continue
        key = ledger.normalize_payee(t["description"])
        if len(key) >= 3:
            groups.setdefault(key, []).append(t)

    out = []
    for key, txns in groups.items():
        if key in dismissed or len(txns) < 3:
            continue
        words = _words(key)
        if any(words and words & bw for bw in bill_words):
            continue  # already a bill
        dates = sorted({_as_date(t["date"]) for t in txns})
        if len(dates) < 3:
            continue
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        gap = median(gaps)
        pattern = next((p for p in _PATTERNS if abs(gap - p[1]) <= p[2]), None)
        if pattern is None:
            continue
        regular = sum(1 for g in gaps if abs(g - pattern[1]) <= pattern[2] * 1.5)
        if regular < max(2, int(len(gaps) * 0.7)):
            continue
        amounts = [-t["amount"] for t in txns]
        typical = median(amounts)
        spread = (max(amounts) - min(amounts)) / typical if typical else 0
        last = dates[-1]
        # Stale: last charge was more than two cycles ago
        if (today - last).days > pattern[1] * 2 + pattern[2]:
            continue
        step = timedelta(days=round(pattern[1]))
        nxt = last + step
        while nxt < today:
            nxt += step
        out.append({
            "key": key,
            "name": key.title(),
            "description": txns[-1]["description"],
            "frequency": pattern[0],
            "amount": round(typical, 2),
            "variable": spread > 0.1,
            "min_amount": round(min(amounts), 2),
            "max_amount": round(max(amounts), 2),
            "count": len(txns),
            "last_date": last.isoformat(),
            "next_expected": nxt.isoformat(),
            "due_day": last.day,
            "category": txns[-1]["category"],
            "monthly_cost": round(typical * 30.4 / pattern[1], 2),
        })
    return sorted(out, key=lambda r: -r["monthly_cost"])


def dismiss_recurring(key: str) -> None:
    from models.app_settings import get_setting, update_settings
    current = list(get_setting("dismissed_recurring") or [])
    if key not in current:
        current.append(key)
        update_settings({"dismissed_recurring": current})
