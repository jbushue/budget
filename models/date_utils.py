"""
Small date helpers shared by bills, income sources, and loan accounts.

All "day of month" schedules clamp to the last day of short months
(e.g. a bill due on the 31st falls on Feb 28/29, Apr 30, ...).
"""

import calendar
from datetime import date, timedelta


def last_day_of_month(year: int, month: int) -> int:
    """Return the number of days in the given month."""
    return calendar.monthrange(year, month)[1]


def clamped_date(year: int, month: int, day: int) -> date:
    """Build a date, clamping ``day`` to the last day of the month."""
    return date(year, month, min(day, last_day_of_month(year, month)))


def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    """Shift a (year, month) pair by ``months`` (may be negative)."""
    index = year * 12 + (month - 1) + months
    return index // 12, index % 12 + 1


def is_clamped_day(current: date, day: int) -> bool:
    """True when ``current`` is the (clamped) ``day`` of its month.

    Used for monthly events keyed on a day-of-month, so that day 31 fires on
    the last day of 30-day months and February instead of being skipped.
    """
    return current.day == min(day, last_day_of_month(current.year, current.month))


def next_by_days(anchor: date, step_days: int, reference_date: date, allow_before: bool = True) -> date:
    """
    Next occurrence strictly after ``reference_date`` of a series that starts
    at ``anchor`` and repeats every ``step_days`` days.

    When ``allow_before`` is False the series has no occurrences before the
    anchor (the anchor is the first occurrence).
    """
    if reference_date < anchor and not allow_before:
        return anchor
    k = (reference_date - anchor).days // step_days + 1
    return anchor + timedelta(days=k * step_days)


def next_by_months(
    anchor_year: int,
    anchor_month: int,
    day: int,
    step_months: int,
    reference_date: date,
    allow_before: bool = True,
) -> date:
    """
    Next occurrence strictly after ``reference_date`` of a series that falls on
    ``day`` (clamped) every ``step_months`` months, phased from
    (``anchor_year``, ``anchor_month``).

    When ``allow_before`` is False the anchor month is the first occurrence.
    """
    anchor_index = anchor_year * 12 + (anchor_month - 1)
    ref_index = reference_date.year * 12 + (reference_date.month - 1)
    k = (ref_index - anchor_index) // step_months
    if not allow_before:
        k = max(k, 0)
    while True:
        y, m = add_months(anchor_year, anchor_month, k * step_months)
        candidate = clamped_date(y, m, day)
        if candidate > reference_date:
            return candidate
        k += 1
