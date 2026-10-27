"""
Ledger: real-world transactions, categories, rules, and budgets.

Transactions come from SimpleFIN (automatic), CSV files from your bank, or
manual entry. Amounts are signed: negative = money out, positive = money in.

Categories have a kind (expense / income / transfer), an optional monthly
budget, and an "everyday" flag. Everyday categories (groceries, gas, dining,
...) are the spending that isn't entered as bills; their recent average is
what "Learn it from my transactions" uses for the everyday spending
allowance in projections.

Rules map text in the description to a category. Your own rules win over
the built-in keyword list.
"""

from __future__ import annotations

import csv
import io
import re
from calendar import monthrange
from datetime import date, datetime, timedelta

from models import database as db

# (name, kind, is_everyday, color)
DEFAULT_CATEGORIES = [
    ("Groceries", "expense", True, "#16a34a"),
    ("Dining", "expense", True, "#f97316"),
    ("Gas & Transport", "expense", True, "#0ea5e9"),
    ("Shopping", "expense", True, "#a855f7"),
    ("Entertainment", "expense", True, "#ec4899"),
    ("Health", "expense", True, "#14b8a6"),
    ("Personal Care", "expense", True, "#f43f5e"),
    ("Household", "expense", True, "#84cc16"),
    ("Kids & Pets", "expense", True, "#eab308"),
    ("Gifts & Donations", "expense", True, "#8b5cf6"),
    ("Travel", "expense", False, "#06b6d4"),
    ("Housing", "expense", False, "#64748b"),
    ("Utilities", "expense", False, "#0284c7"),
    ("Insurance", "expense", False, "#475569"),
    ("Subscriptions", "expense", False, "#d946ef"),
    ("Debt Payments", "expense", False, "#dc2626"),
    ("Fees & Interest", "expense", False, "#b91c1c"),
    ("Taxes", "expense", False, "#78716c"),
    ("Other", "expense", True, "#94a3b8"),
    ("Income", "income", False, "#22c55e"),
    ("Transfer", "transfer", False, "#9ca3af"),
]

# Built-in keyword rules (lowercase "contains" match), checked after user rules
DEFAULT_KEYWORDS = {
    "Groceries": ["kroger", "safeway", "aldi", "publix", "whole foods", "trader joe", "wegmans", "heb ",
                  "food lion", "giant eagle", "meijer", "sprouts", "grocery", "costco", "sam's club",
                  "walmart grocery", "instacart", "albertsons", "winco", "hy-vee", "fresh market"],
    "Dining": ["restaurant", "mcdonald", "starbucks", "chipotle", "subway", "taco bell", "wendy",
               "burger king", "chick-fil-a", "dunkin", "pizza", "doordash", "grubhub", "uber eats",
               "panera", "cafe", "coffee", "bar & grill", "diner", "kfc", "sonic drive", "domino"],
    "Gas & Transport": ["shell", "exxon", "chevron", "bp ", "marathon", "speedway", "sunoco", "valero",
                        "circle k", "wawa", "sheetz", "quiktrip", "gas station", "fuel", "uber", "lyft",
                        "parking", "toll", "transit", "metro"],
    "Shopping": ["amazon", "amzn", "target", "walmart", "best buy", "ebay", "etsy", "kohl", "macy",
                 "home depot", "lowe's", "lowes", "ikea", "tj maxx", "marshalls", "old navy"],
    "Entertainment": ["netflix", "hulu", "disney+", "spotify", "steam", "playstation", "xbox", "nintendo",
                      "cinema", "theater", "theatre", "amc ", "ticketmaster"],
    "Health": ["pharmacy", "cvs", "walgreens", "rite aid", "doctor", "dental", "hospital", "clinic",
               "medical", "optometr", "urgent care"],
    "Personal Care": ["salon", "barber", "spa ", "ulta", "sephora", "gym", "fitness", "planet fitness"],
    "Utilities": ["electric", "power", "energy", "water", "sewer", "gas co", "natural gas", "comcast",
                  "xfinity", "spectrum", "verizon", "at&t", "t-mobile", "internet", "duke energy"],
    "Insurance": ["insurance", "geico", "progressive", "state farm", "allstate", "liberty mutual"],
    "Housing": ["rent", "mortgage", "hoa ", "property mgmt", "apartments"],
    "Subscriptions": ["subscription", "membership", "patreon", "apple.com/bill", "google *", "adobe",
                      "microsoft*", "youtube premium", "audible"],
    "Debt Payments": ["loan pmt", "loan payment", "nelnet", "navient", "mohela", "sallie mae",
                      "credit card payment", "card payment", "autopay"],
    "Fees & Interest": ["fee", "interest charge", "finance charge", "overdraft"],
    "Transfer": ["transfer", "xfer", "zelle to", "venmo", "paypal transfer", "online banking transfer"],
    "Income": ["payroll", "direct dep", "salary", "paycheck", "deposit from"],
}

UNCATEGORIZED = None

# Keywords must start at a word boundary ("fee" shouldn't match "coffee", "rent" not "parent")
_KEYWORD_RES = {cat: [re.compile(r"(?<![a-z0-9])" + re.escape(w)) for w in words]
                for cat, words in DEFAULT_KEYWORDS.items()}


def _session():
    return db.get_session()


def _to_dict(t: db.LedgerTransactionModel) -> dict:
    return {
        "id": t.id,
        "date": t.txn_date.isoformat(),
        "description": t.description,
        "payee": t.payee or "",
        "amount": round(t.amount, 2),
        "bank_name": t.bank_name or "",
        "account_name": t.account_name or "",
        "category": t.category,
        "source": t.source,
        "matched_bill": t.matched_bill,
        "notes": t.notes or "",
    }


# ─────────────────────────────────────────────────────────────────────────
#  Categories
# ─────────────────────────────────────────────────────────────────────────

def ensure_defaults() -> None:
    """Seed the default categories the first time the ledger is used."""
    session = _session()
    try:
        if session.query(db.CategoryModel).count() == 0:
            for name, kind, everyday, color in DEFAULT_CATEGORIES:
                session.add(db.CategoryModel(name=name, kind=kind, is_everyday=everyday, color=color))
            session.commit()
    finally:
        session.close()


def list_categories() -> list[dict]:
    ensure_defaults()
    session = _session()
    try:
        rows = session.query(db.CategoryModel).order_by(db.CategoryModel.kind, db.CategoryModel.name).all()
        return [{"name": c.name, "kind": c.kind, "is_everyday": bool(c.is_everyday),
                 "monthly_budget": c.monthly_budget, "color": c.color} for c in rows]
    finally:
        session.close()


def _category_map() -> dict:
    return {c["name"]: c for c in list_categories()}


def upsert_category(name: str, kind: str = "expense", is_everyday: bool = False,
                    monthly_budget: float | None = None, color: str | None = None,
                    rename_from: str | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name is required")
    if kind not in ("expense", "income", "transfer"):
        raise ValueError("kind must be expense, income or transfer")
    if monthly_budget is not None and monthly_budget < 0:
        raise ValueError("Budget can't be negative")
    ensure_defaults()
    session = _session()
    try:
        row = session.query(db.CategoryModel).filter_by(name=rename_from or name).first()
        if rename_from and rename_from != name and session.query(db.CategoryModel).filter_by(name=name).first():
            raise ValueError(f"A category named '{name}' already exists")
        if row is None:
            if rename_from:
                raise ValueError(f"Category '{rename_from}' not found")
            row = db.CategoryModel(name=name)
            session.add(row)
        if rename_from and rename_from != name:
            session.query(db.LedgerTransactionModel).filter_by(category=rename_from).update({"category": name})
            session.query(db.CategoryRuleModel).filter_by(category=rename_from).update({"category": name})
        row.name = name
        row.kind = kind
        row.is_everyday = bool(is_everyday) and kind == "expense"
        row.monthly_budget = monthly_budget if monthly_budget else None
        if color:
            row.color = color
        session.commit()
        return {"name": row.name, "kind": row.kind, "is_everyday": row.is_everyday,
                "monthly_budget": row.monthly_budget, "color": row.color}
    finally:
        session.close()


def set_budget(name: str, monthly_budget: float | None) -> None:
    c = _category_map().get(name)
    if c is None:
        raise ValueError(f"Category '{name}' not found")
    upsert_category(name, c["kind"], c["is_everyday"], monthly_budget, c["color"])


def delete_category(name: str) -> None:
    session = _session()
    try:
        row = session.query(db.CategoryModel).filter_by(name=name).first()
        if row is None:
            raise ValueError(f"Category '{name}' not found")
        session.query(db.LedgerTransactionModel).filter_by(category=name).update({"category": None})
        session.query(db.CategoryRuleModel).filter_by(category=name).delete()
        session.delete(row)
        session.commit()
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────
#  Rules and auto-categorization
# ─────────────────────────────────────────────────────────────────────────

def list_rules() -> list[dict]:
    session = _session()
    try:
        rows = session.query(db.CategoryRuleModel).order_by(db.CategoryRuleModel.priority.desc(),
                                                            db.CategoryRuleModel.id).all()
        return [{"id": r.id, "pattern": r.pattern, "category": r.category, "priority": r.priority} for r in rows]
    finally:
        session.close()


def add_rule(pattern: str, category: str, priority: int = 0, apply_to_existing: bool = True) -> dict:
    pattern = (pattern or "").strip()
    if len(pattern) < 2:
        raise ValueError("Rule text must be at least 2 characters")
    if category not in _category_map():
        raise ValueError(f"Category '{category}' not found")
    session = _session()
    try:
        row = db.CategoryRuleModel(pattern=pattern, category=category, priority=priority)
        session.add(row)
        session.commit()
        out = {"id": row.id, "pattern": row.pattern, "category": row.category, "priority": row.priority}
    finally:
        session.close()
    if apply_to_existing:
        out["applied"] = recategorize(only_uncategorized=False, pattern=pattern)
    return out


def delete_rule(rule_id: int) -> None:
    session = _session()
    try:
        n = session.query(db.CategoryRuleModel).filter_by(id=rule_id).delete()
        session.commit()
        if not n:
            raise ValueError("Rule not found")
    finally:
        session.close()


def normalize_payee(text: str) -> str:
    """'KROGER #1234 COLUMBUS OH 10/12' -> 'kroger' — a stable key for rules and recurring detection."""
    t = (text or "").lower()
    t = re.sub(r"(pos|debit|purchase|card|recurring|ach|ppd|web|id:)\s", " ", t)
    t = re.sub(r"[#*]\s*\w*\d\w*", " ", t)        # store / reference numbers
    t = re.sub(r"\d+[/-]\d+([/-]\d+)?", " ", t)    # dates
    t = re.sub(r"\b\d+\b", " ", t)
    t = re.sub(r"\b[a-z]{2}\b\s*$", " ", t.strip())  # trailing state code
    t = re.sub(r"[^a-z&+' ]", " ", t)
    words = [w for w in t.split() if len(w) > 1][:3]
    return " ".join(words)


def categorize(description: str, amount: float, rules: list[dict] | None = None,
               categories: dict | None = None) -> str | None:
    text = (description or "").lower()
    rules = rules if rules is not None else list_rules()
    for r in sorted(rules, key=lambda r: (-r["priority"], -len(r["pattern"]))):
        if r["pattern"].lower() in text:
            return r["category"]
    categories = categories if categories is not None else _category_map()
    for cat, patterns in _KEYWORD_RES.items():
        if cat in categories and any(p.search(text) for p in patterns):
            # Money in that matched an expense keyword is a refund — still that category
            return cat
    if amount > 0 and "Income" in categories:
        return "Income"
    return UNCATEGORIZED


def recategorize(only_uncategorized: bool = True, pattern: str | None = None) -> int:
    """Re-run categorization; returns how many transactions changed."""
    rules, cats = list_rules(), _category_map()
    session = _session()
    changed = 0
    try:
        q = session.query(db.LedgerTransactionModel)
        if only_uncategorized:
            q = q.filter(db.LedgerTransactionModel.category.is_(None))
        for t in q.all():
            if pattern and pattern.lower() not in (t.description or "").lower():
                continue
            new = categorize(t.description, t.amount, rules, cats)
            if new and new != t.category:
                t.category = new
                changed += 1
        session.commit()
    finally:
        session.close()
    return changed


# ─────────────────────────────────────────────────────────────────────────
#  Transactions
# ─────────────────────────────────────────────────────────────────────────

def add_transaction(txn_date: date, description: str, amount: float, bank_name: str = "",
                    account_name: str = "", category: str | None = None, notes: str = "",
                    source: str = "manual", external_id: str | None = None, payee: str = "",
                    session=None) -> dict | None:
    """Add one transaction. Returns None if it's a duplicate."""
    description = (description or "").strip()
    if not description:
        raise ValueError("Description is required")
    own = session is None
    session = session or _session()
    try:
        if external_id and session.query(db.LedgerTransactionModel).filter_by(external_id=external_id).first():
            return None
        if source == "csv":
            dup = session.query(db.LedgerTransactionModel).filter_by(
                txn_date=txn_date, amount=round(amount, 2), description=description,
                bank_name=bank_name or None, account_name=account_name or None).first()
            if dup:
                return None
        if category is None:
            category = categorize(description, amount)
        elif own and category not in _category_map():
            raise ValueError(f"Category '{category}' not found")
        row = db.LedgerTransactionModel(
            txn_date=txn_date, description=description, payee=payee or None, amount=round(amount, 2),
            bank_name=bank_name or None, account_name=account_name or None, category=category,
            source=source, external_id=external_id, notes=notes or None)
        session.add(row)
        if own:
            session.commit()
        else:
            session.flush()
        return _to_dict(row)
    finally:
        if own:
            session.close()


def update_transaction(txn_id: int, **fields) -> dict:
    session = _session()
    try:
        t = session.get(db.LedgerTransactionModel, txn_id)
        if t is None:
            raise ValueError("Transaction not found")
        if "category" in fields:
            cat = fields["category"] or None
            if cat is not None and cat not in _category_map():
                raise ValueError(f"Category '{cat}' not found")
            t.category = cat
        if fields.get("notes") is not None:
            t.notes = fields["notes"] or None
        if fields.get("description"):
            t.description = fields["description"]
        if fields.get("amount") is not None:
            t.amount = round(float(fields["amount"]), 2)
        if fields.get("txn_date"):
            t.txn_date = fields["txn_date"]
        if "matched_bill" in fields:
            t.matched_bill = fields["matched_bill"] or None
        session.commit()
        return _to_dict(t)
    finally:
        session.close()


def delete_transaction(txn_id: int) -> None:
    session = _session()
    try:
        n = session.query(db.LedgerTransactionModel).filter_by(id=txn_id).delete()
        session.commit()
        if not n:
            raise ValueError("Transaction not found")
    finally:
        session.close()


def search_transactions(text: str = "", category: str | None = None, account: str = "",
                        date_from: date | None = None, date_to: date | None = None,
                        uncategorized: bool = False, limit: int = 100, offset: int = 0) -> dict:
    """Filtered, newest-first page of transactions plus totals for the whole filter."""
    M = db.LedgerTransactionModel
    session = _session()
    try:
        q = session.query(M)
        if text:
            like = f"%{text}%"
            q = q.filter((M.description.ilike(like)) | (M.notes.ilike(like)) | (M.payee.ilike(like)))
        if uncategorized:
            q = q.filter(M.category.is_(None))
        elif category:
            q = q.filter(M.category == category)
        if account and ":" in account:
            bank, acct = account.split(":", 1)
            q = q.filter(M.bank_name == bank, M.account_name == acct)
        if date_from:
            q = q.filter(M.txn_date >= date_from)
        if date_to:
            q = q.filter(M.txn_date <= date_to)
        rows = q.order_by(M.txn_date.desc(), M.id.desc()).all()
        total_in = sum(t.amount for t in rows if t.amount > 0)
        total_out = sum(-t.amount for t in rows if t.amount < 0)
        page = rows[offset: offset + max(1, min(limit, 500))]
        return {"items": [_to_dict(t) for t in page], "total": len(rows),
                "total_in": round(total_in, 2), "total_out": round(total_out, 2)}
    finally:
        session.close()


def all_transactions(date_from: date | None = None) -> list[dict]:
    M = db.LedgerTransactionModel
    session = _session()
    try:
        q = session.query(M)
        if date_from:
            q = q.filter(M.txn_date >= date_from)
        return [_to_dict(t) for t in q.order_by(M.txn_date).all()]
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────
#  CSV import
# ─────────────────────────────────────────────────────────────────────────

_HEADER_HINTS = {
    "date": ["transaction date", "posting date", "posted date", "trans date", "date", "posted"],
    "description": ["description", "payee", "merchant", "name", "details", "memo", "transaction"],
    "amount": ["amount", "amt", "transaction amount"],
    "debit": ["debit", "withdrawal", "withdrawals", "money out", "charge"],
    "credit": ["credit", "deposit", "deposits", "money in", "payment"],
}
_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y",
                 "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]


def _parse_amount(text: str) -> float | None:
    t = (text or "").strip()
    if not t:
        return None
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-") or t.endswith("-")
    t = re.sub(r"[^\d.]", "", t)
    if not t:
        return None
    v = float(t)
    return -v if neg else v


def _parse_date(text: str, fmt: str | None = None) -> date | None:
    t = (text or "").strip()
    for f in ([fmt] if fmt else _DATE_FORMATS):
        try:
            return datetime.strptime(t, f).date()
        except ValueError:
            continue
    return None


def detect_columns(header: list[str]) -> dict:
    """Map our fields to CSV column indexes using common bank header names."""
    lower = [h.strip().lower() for h in header]
    found = {}
    for field, hints in _HEADER_HINTS.items():
        for hint in hints:  # most specific hint first
            idx = next((i for i, h in enumerate(lower) if h == hint), None)
            if idx is None:
                idx = next((i for i, h in enumerate(lower) if hint in h and i not in found.values()), None)
            if idx is not None and idx not in found.values():
                found[field] = idx
                break
    return found


def parse_csv(content: str, mapping: dict | None = None, invert: bool = False,
              date_format: str | None = None) -> dict:
    """
    Parse a bank CSV. Returns {"columns", "mapping", "rows": [{date, description, amount}],
    "errors": [...]}. ``mapping`` = {"date": i, "description": i, "amount": i} or with
    "debit"/"credit" instead of "amount". ``invert`` flips signs (for files where
    purchases are positive).
    """
    text = content.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = list(csv.reader(io.StringIO(text), dialect))
    reader = [r for r in reader if any(c.strip() for c in r)]
    if not reader:
        raise ValueError("The file is empty")
    header = reader[0]
    mapping = {k: int(v) for k, v in (mapping or detect_columns(header)).items() if v is not None and v != ""}
    if "date" not in mapping or "description" not in mapping or not (
            "amount" in mapping or "debit" in mapping or "credit" in mapping):
        raise ValueError("Couldn't find the date, description and amount columns — choose them manually")

    rows, errors = [], []
    for n, r in enumerate(reader[1:], start=2):
        def col(field):
            i = mapping.get(field)
            return r[i] if i is not None and i < len(r) else ""
        d = _parse_date(col("date"), date_format)
        if d is None:
            errors.append(f"Row {n}: can't read date '{col('date')}'")
            continue
        if "amount" in mapping:
            amt = _parse_amount(col("amount"))
        else:
            debit, credit = _parse_amount(col("debit")), _parse_amount(col("credit"))
            amt = (abs(credit) if credit else 0.0) - (abs(debit) if debit else 0.0)
            if debit is None and credit is None:
                amt = None
        if amt is None:
            errors.append(f"Row {n}: can't read amount")
            continue
        if invert:
            amt = -amt
        desc = col("description").strip() or "(no description)"
        rows.append({"date": d, "description": desc, "amount": round(amt, 2)})
    return {"columns": header, "mapping": mapping, "rows": rows, "errors": errors}


def import_csv(content: str, bank_name: str, account_name: str, mapping: dict | None = None,
               invert: bool = False, date_format: str | None = None) -> dict:
    parsed = parse_csv(content, mapping, invert, date_format)
    rules, cats = list_rules(), _category_map()
    imported = duplicates = 0
    session = _session()
    try:
        for row in parsed["rows"]:
            added = add_transaction(row["date"], row["description"], row["amount"], bank_name, account_name,
                                    category=categorize(row["description"], row["amount"], rules, cats),
                                    source="csv", session=session)
            if added is None:
                duplicates += 1
            else:
                imported += 1
        session.commit()
    finally:
        session.close()
    return {"imported": imported, "duplicates": duplicates, "errors": parsed["errors"]}


# ─────────────────────────────────────────────────────────────────────────
#  SimpleFIN import
# ─────────────────────────────────────────────────────────────────────────

def import_simplefin(days: int = 90) -> dict:
    """Store transactions for all mapped SimpleFIN accounts (duplicates skipped)."""
    import time
    from models.simplefin import SimplefinClient, get_simplefin_connection, get_simplefin_mappings
    conn = get_simplefin_connection()
    if not conn:
        raise ValueError("SimpleFIN isn't connected")
    mappings = get_simplefin_mappings()
    if not mappings:
        return {"imported": 0, "duplicates": 0, "errors": []}
    start_ts = int(time.time()) - days * 86400
    accounts = SimplefinClient.fetch_accounts(conn["access_url"], start_date=start_ts)
    rules, cats = list_rules(), _category_map()
    imported = duplicates = 0
    errors = []
    session = _session()
    try:
        for acc in accounts:
            m = mappings.get(acc.id)
            if not m:
                continue
            for txn in acc.transactions:
                try:
                    when = datetime.fromtimestamp(txn.posted or time.time()).date()
                    desc = txn.description or txn.payee or "(no description)"
                    added = add_transaction(when, desc, float(txn.amount), m["bank_name"], m["account_name"],
                                            category=categorize(desc, float(txn.amount), rules, cats),
                                            source="simplefin", external_id=f"sfin:{acc.id}:{txn.id}",
                                            payee=txn.payee or "", session=session)
                    if added is None:
                        duplicates += 1
                    else:
                        imported += 1
                except Exception as e:  # one bad transaction shouldn't stop the import
                    errors.append(f"{acc.name}: {e}")
        session.commit()
    finally:
        session.close()
    return {"imported": imported, "duplicates": duplicates, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────
#  Budgets, reports, learned spending
# ─────────────────────────────────────────────────────────────────────────

def _month_bounds(month: str | None) -> tuple[date, date]:
    if month:
        y, m = (int(x) for x in month.split("-"))
    else:
        t = date.today()
        y, m = t.year, t.month
    return date(y, m, 1), date(y, m, monthrange(y, m)[1])


def budget_status(month: str | None = None, today: date | None = None) -> dict:
    """Spent vs. budget per expense category for a month ('YYYY-MM', default this month)."""
    today = today or date.today()
    start, end = _month_bounds(month)
    cats = _category_map()
    txns = [t for t in all_transactions(start) if date.fromisoformat(t["date"]) <= end]
    spent: dict = {}
    uncategorized = 0.0
    income = 0.0
    for t in txns:
        c = cats.get(t["category"]) if t["category"] else None
        if c is None:
            if t["amount"] < 0:
                uncategorized += -t["amount"]
            continue
        if c["kind"] == "expense":
            spent[c["name"]] = spent.get(c["name"], 0.0) - t["amount"]  # refunds reduce spending
        elif c["kind"] == "income":
            income += t["amount"]

    is_current = start <= today <= end
    elapsed = (today - start).days + 1 if is_current else (end - start).days + 1
    days = (end - start).days + 1
    lines = []
    for name, c in cats.items():
        if c["kind"] != "expense":
            continue
        s = round(spent.get(name, 0.0), 2)
        budget = c["monthly_budget"]
        if not budget and not s:
            continue
        projected = round(s / elapsed * days, 2) if is_current and elapsed else s
        lines.append({
            "category": name, "color": c["color"], "is_everyday": c["is_everyday"],
            "budget": budget, "spent": s,
            "remaining": round(budget - s, 2) if budget else None,
            "percent": round(s / budget * 100, 1) if budget else None,
            "projected": projected,
            "status": ("over" if budget and s > budget else
                       "warning" if budget and projected > budget else
                       "ok" if budget else "no_budget"),
        })
    lines.sort(key=lambda line: (line["budget"] is None, -(line["percent"] or 0), -line["spent"]))
    total_budget = sum(line["budget"] or 0 for line in lines)
    total_spent = sum(line["spent"] for line in lines)
    return {
        "month": start.strftime("%Y-%m"),
        "days_elapsed": elapsed, "days_in_month": days,
        "lines": lines,
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "total_budgeted_spent": round(sum(line["spent"] for line in lines if line["budget"]), 2),
        "uncategorized_spent": round(uncategorized, 2),
        "income": round(income, 2),
    }


def spending_report(months: int = 6, today: date | None = None) -> dict:
    """Income, spending and spending by category for the last `months` months."""
    today = today or date.today()
    y, m = today.year, today.month
    keys = []
    for _ in range(max(1, min(months, 24))):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    cats = _category_map()
    first = date.fromisoformat(keys[0] + "-01")
    rows = {k: {"month": k, "income": 0.0, "spending": 0.0, "by_category": {}} for k in keys}
    for t in all_transactions(first):
        k = t["date"][:7]
        if k not in rows:
            continue
        c = cats.get(t["category"]) if t["category"] else None
        kind = c["kind"] if c else ("income" if t["amount"] > 0 else "expense")
        if kind == "transfer":
            continue
        if kind == "income":
            rows[k]["income"] += t["amount"]
        else:
            name = c["name"] if c else "Uncategorized"
            rows[k]["spending"] -= t["amount"]
            rows[k]["by_category"][name] = rows[k]["by_category"].get(name, 0.0) - t["amount"]
    out = []
    for k in keys:
        r = rows[k]
        out.append({"month": k, "income": round(r["income"], 2), "spending": round(r["spending"], 2),
                    "net": round(r["income"] - r["spending"], 2),
                    "by_category": {n: round(v, 2) for n, v in sorted(r["by_category"].items(), key=lambda x: -x[1])}})
    colors = {n: c["color"] for n, c in cats.items()}
    colors["Uncategorized"] = "#cbd5e1"
    return {"months": out, "colors": colors}


def learned_everyday_weekly(weeks: int = 8, today: date | None = None) -> float | None:
    """
    Average weekly spending in everyday categories over the last `weeks` weeks
    (transactions matched to bills excluded). None when there's under 3 weeks
    of history to learn from.
    """
    today = today or date.today()
    start = today - timedelta(days=weeks * 7)
    txns = all_transactions(start)
    if not txns:
        return None
    earliest = min(date.fromisoformat(t["date"]) for t in txns)
    span_days = (today - max(earliest, start)).days
    if span_days < 21:
        return None
    cats = _category_map()
    total = 0.0
    for t in txns:
        c = cats.get(t["category"]) if t["category"] else None
        if c and c["is_everyday"] and not t["matched_bill"]:
            total -= t["amount"]
    return round(max(0.0, total) / (span_days / 7.0), 2)
