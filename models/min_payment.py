"""
How a card's minimum payment is worked out.

Card issuers use a handful of formulas: a percentage of the balance, often
plus the month's interest, never less than a floor (and never more than the
balance). Installment financing (furniture, medical) asks a fixed amount.

A card can be given its own rule (``CreditAccount.min_rule``); without one it
uses ``DEFAULT_RULE``. ``match(...)`` takes the minimum printed on a
statement and finds which rules give that amount, so the app's projections
use the same minimum the issuer will ask for.

A rule is a small dict, saved as JSON:

* ``{"pct": 1, "interest": True, "floor": 25}`` - 1% of the balance plus
  interest, at least $25
* ``{"pct": 2, "floor": 35}`` - 2% of the balance, at least $35
* ``{"fixed": 178.09}`` - the same amount every month
"""

from __future__ import annotations

import math

# The most common formula among major issuers. It always pays down the
# balance, unlike a flat 2%, which is less than the interest above 24% APR.
DEFAULT_RULE = {"pct": 1.0, "interest": True, "floor": 25.0}

# Formulas tried when matching a statement, most common first (that order
# breaks ties when several give the same amount)
FORMULAS = [(1.0, True), (2.0, False), (3.0, False), (2.0, True), (2.5, False), (4.0, False), (5.0, False),
            (1.5, True), (3.5, False), (1.5, False), (1.0, False), (3.0, True), (2.5, True), (4.0, True),
            (5.0, True)]
FLOORS = [25.0, 35.0, 40.0, 30.0, 20.0, 15.0, 27.0, 29.0, 50.0, 10.0, 0.0]
# Slack for the balance itself (statements are to the cent)
TOLERANCE = 0.01
# With no exact match, the nearest formula is used if it's at least this close
CLOSE_PCT = 0.05
CLOSE_DOLLARS = 3.0


def normalize(rule) -> dict | None:
    """A clean copy of ``rule``, or None if it isn't a valid rule."""
    if not isinstance(rule, dict):
        return None
    try:
        if rule.get("fixed") is not None:
            fixed = round(float(rule["fixed"]), 2)
            return {"fixed": fixed} if fixed > 0 else None
        pct = float(rule.get("pct", 0) or 0)
        floor = float(rule.get("floor", 0) or 0)
    except (TypeError, ValueError):
        return None
    if not 0 < pct <= 100 or floor < 0:
        return None
    return {"pct": pct, "interest": bool(rule.get("interest")), "floor": floor}


def monthly_interest(balance: float, apr: float) -> float:
    """About a month of interest on ``balance`` (what a statement charges)."""
    return max(0.0, balance) * max(0.0, apr) / 100 / 12


def amount(rule: dict | None, balance: float, interest: float = 0.0) -> float:
    """The minimum ``rule`` asks for on ``balance`` (``interest``: the month's interest charge)."""
    rule = normalize(rule) or DEFAULT_RULE
    if balance <= 0.005:
        return 0.0
    if "fixed" in rule:
        return round(min(rule["fixed"], balance), 2)
    base = balance * rule["pct"] / 100 + (max(0.0, interest) if rule["interest"] else 0.0)
    return round(min(balance, max(rule["floor"], base)), 2)


def _money(x: float) -> str:
    return f"${x:,.2f}".replace(".00", "")


def _pct(x: float) -> str:
    return f"{x:g}%"


def describe(rule: dict | None) -> str:
    """Plain-English rule, e.g. "1% of the balance + interest, at least $25"."""
    rule = normalize(rule) or DEFAULT_RULE
    if "fixed" in rule:
        return f"Fixed {_money(rule['fixed'])} a month"
    text = f"{_pct(rule['pct'])} of the balance" + (" + interest" if rule["interest"] else "")
    return text + (f", at least {_money(rule['floor'])}" if rule["floor"] > 0 else "")


def floor_decides(rule: dict, balance: float, interest: float) -> bool:
    """True if the floor (or the balance itself) sets the amount, not the percentage."""
    if "fixed" in rule:
        return False
    base = balance * rule["pct"] / 100 + (max(0.0, interest) if rule["interest"] else 0.0)
    return base <= rule["floor"] + 0.005 or balance <= rule["floor"] + 0.005 or balance <= base + 0.005


def _gives(value: float, minimum: float, slack: float) -> bool:
    """``value`` is ``minimum`` as printed: to the cent, or rounded to whole dollars (down, nearest or up)."""
    return any(abs(v - minimum) <= slack + 0.005
               for v in (value, math.floor(value), round(value), math.ceil(value)))


def match(minimum: float, balance: float, interest: float, interest_known: bool = True) -> dict:
    """
    Rules that give ``minimum`` on a statement with ``balance`` and
    ``interest`` charged, and the one to use:

    {"best": rule, "matches": [{"rule", "label", "amount"}], "ambiguous": bool,
     "message": str}

    When only floors match (a small balance, so every percentage gives the
    floor), the floor is known but the percentage isn't: the common
    "1% + interest" is assumed and the message says so. When nothing
    matches, the minimum is taken as a fixed monthly amount.

    ``interest_known``: False if ``interest`` is an estimate (not read off
    the statement); formulas with interest then get some slack.
    """
    if minimum <= 0:
        raise ValueError("Enter the minimum payment from your statement")
    if balance <= 0:
        raise ValueError("Enter the statement balance")
    if minimum > balance + 1.0:
        raise ValueError("The minimum can't be more than the statement balance")

    no_interest = interest <= 0.005
    exact, by_floor = [], []
    for pct, plus_interest in FORMULAS:
        if plus_interest and no_interest:
            continue  # same as the formula without interest
        slack = TOLERANCE + (0.5 + 0.1 * interest if plus_interest and not interest_known else 0.0)
        for floor in FLOORS:
            rule = {"pct": pct, "interest": plus_interest, "floor": floor}
            got = amount(rule, balance, interest)
            if _gives(got, minimum, slack):
                (by_floor if floor_decides(rule, balance, interest) else exact).append((rule, got))

    def rows(found):
        return [{"rule": r, "label": describe(r), "amount": got} for r, got in found]

    if exact:
        # Several percentages can match the same statement (e.g. 2% and
        # "1% + interest" on a 12% card); the floor rarely matters then, so
        # keep one entry per formula
        seen, unique = set(), []
        for r, got in exact:
            key = (r["pct"], r["interest"])
            if key not in seen:
                seen.add(key)
                unique.append((r, got))
        best = unique[0][0]
        ambiguous = len(unique) > 1
        message = (f"Matches {describe(best)}." if not ambiguous else
                   f"{len(unique)} formulas give this minimum at this balance; {describe(best)} is the most "
                   "common. Pick another if you know your card's terms, or check again with a later statement.")
        return {"best": best, "matches": rows(unique), "ambiguous": ambiguous, "close": False, "message": message}

    if by_floor and minimum < balance - 1.0:
        floor = by_floor[0][0]["floor"]
        best = {"pct": DEFAULT_RULE["pct"], "interest": DEFAULT_RULE["interest"], "floor": floor}
        message = (f"At this balance only the {_money(floor)} minimum applies, so the percentage can't be told "
                   f"apart. Assuming {describe(best)}; check again when the balance is higher.")
        floors = []
        for r, got in by_floor:
            if r["floor"] == floor and (r["pct"], r["interest"]) not in [(f["rule"]["pct"], f["rule"]["interest"]) for f in floors]:
                floors.append({"rule": r, "label": describe(r), "amount": got})
        return {"best": best, "matches": [{"rule": best, "label": describe(best), "amount": amount(best, balance, interest)}]
                + [f for f in floors if f["rule"] != best][:4], "ambiguous": True, "close": False, "message": message}

    if minimum >= balance - 1.0:
        return {"best": None, "matches": [], "ambiguous": True, "close": False,
                "message": "The minimum is the whole balance, so it doesn't show the card's formula. "
                           "Try again with a statement that has a larger balance."}

    fixed = {"fixed": round(minimum, 2)}
    fixed_row = {"rule": fixed, "label": describe(fixed), "amount": round(minimum, 2)}
    near = closest(minimum, balance, interest)
    limit = max(CLOSE_DOLLARS, minimum * CLOSE_PCT)
    if near and abs(near[0]["amount"] - minimum) <= limit:
        best = near[0]["rule"]
        off = near[0]["amount"] - minimum
        return {"best": best, "matches": near + [fixed_row], "ambiguous": True, "close": True,
                "message": f"No formula gives exactly {_money(minimum)}. The closest, {describe(best)}, gives "
                           f"{_money(near[0]['amount'])} ({_money(abs(off))} {'more' if off > 0 else 'less'}) and "
                           "will be used as it is. Pick another, adjust it below, or use the fixed amount."}
    return {"best": fixed, "matches": [fixed_row] + near, "ambiguous": False, "close": False,
            "message": "No percentage formula gives this minimum, so it's treated as a fixed monthly payment "
                       "(usual for installment financing). If that's wrong, check the statement balance and "
                       "interest charged, or adjust the formula below."}


def closest(minimum: float, balance: float, interest: float, limit: int = 3) -> list[dict]:
    """The formulas nearest to ``minimum`` (one per percentage formula), nearest first, with how far off each is."""
    best: dict = {}
    for pct, plus_interest in FORMULAS:
        if plus_interest and interest <= 0.005:
            continue
        for floor in FLOORS:
            rule = {"pct": pct, "interest": plus_interest, "floor": floor}
            got = amount(rule, balance, interest)
            off = abs(got - minimum)
            key = (pct, plus_interest)
            if key not in best or off < best[key][0] - 0.005:
                best[key] = (off, rule, got)
    ranked = sorted(best.values(), key=lambda x: x[0])[:limit]
    return [{"rule": r, "label": describe(r), "amount": got, "off": round(got - minimum, 2)} for _, r, got in ranked]
