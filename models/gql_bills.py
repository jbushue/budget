"""
GraphQL for paying bills by due date: the month view (every due date of
every bill in a month, with what's paid and what's left), undoing a payment
and skipping a due date.

Mixed into the root Query/Mutation through gql_ext.
"""

from __future__ import annotations

from datetime import date, timedelta

import graphene

from models import occurrences as occ
from models.date_utils import add_months
from models.fixed_bill import AccountLinkedBill, FloatingBill, GroupLinkedBill


def _manager(info):
    return info.context.get('manager')


def find_bill(manager, bill_name: str):
    return next((b for b in manager.bills if b.bill_name == bill_name), None)


def display_name(bill) -> str:
    if isinstance(bill, GroupLinkedBill):
        return bill.linked_group.group_name
    if isinstance(bill, AccountLinkedBill):
        return f"{bill.linked_account.account_name} payment"
    return bill.bill_name


def kind_of(bill) -> str:
    if isinstance(bill, GroupLinkedBill):
        return "group"
    if isinstance(bill, AccountLinkedBill):
        return bill.linked_account_type
    return "floating" if isinstance(bill, FloatingBill) else "bill"


def month_range() -> tuple[str, str]:
    """First and last month the month view offers (YYYY-MM): a year back, a year ahead."""
    today = date.today()
    y0, m0 = add_months(today.year, today.month, -12)
    last = today + timedelta(days=occ.AHEAD_DAYS)
    return f"{y0:04d}-{m0:02d}", f"{last.year:04d}-{last.month:02d}"


def resolve_due(bill, text: str | None, pay_date: date | None = None) -> date:
    """
    The due date a payment/skip is for: the one given (any day in the same
    month counts for a monthly bill), else the oldest still owed, else the next.
    Raises ValueError for a date that isn't one of the bill's due dates.
    """
    if not text:
        due = occ.default_due(bill, pay_date or date.today())
        if due is None:
            raise ValueError("This bill has no due date to pay")
        return due
    try:
        wanted = date.fromisoformat(text[:10])
    except ValueError:
        raise ValueError(f"Invalid due date '{text}'. Use YYYY-MM-DD.")
    if wanted > date.today() + timedelta(days=occ.AHEAD_DAYS):
        raise ValueError("Bills can be paid up to a year ahead")
    key = occ.period(bill, wanted)
    if isinstance(key, tuple):  # monthly or longer: find that month's due date
        start = date(key[0], key[1], 1)
        y, m = add_months(key[0], key[1], 1)
        candidates = occ.due_dates(bill, start, date(y, m, 1) - timedelta(days=1))
    else:
        candidates = [d for d in occ.due_dates(bill, wanted, wanted)]
    if not candidates:
        raise ValueError(f"{display_name(bill)} isn't due on {wanted.isoformat()}")
    return candidates[0]


def _find_bank(manager, name):
    return next((b for b in manager.banks if b.name == name), None)


def reverse_payment(manager, bill, entry: dict) -> list[str]:
    """
    Put back money a recorded payment moved: back into the account it came
    from, and (for cards, HELOCs, mortgages and loan groups) back onto the
    debt it paid down. Returns what was put back, for the message.
    """
    amount = float(entry.get("amount_paid") or 0.0)
    done = []
    if amount <= 0 or not entry.get("moved_money"):
        return done
    day = occ.paid_on(entry) or date.today()
    bank = _find_bank(manager, entry.get("source_bank") or "")
    name = entry.get("source_account") or ""
    if bank and name in bank.accounts:
        bank.accounts[name].deposit(amount, description=f"Undo payment: {display_name(bill)}", transaction_date=day)
        done.append(f"${amount:,.2f} back in {name}")
    elif bank and name in bank.credit_accounts:
        card = bank.credit_accounts[name]
        card.balance = round(card.balance - amount, 2)
        card.regular_balance = max(0.0, round(card.regular_balance - amount, 2))
        done.append(f"${amount:,.2f} taken off {name}")

    def owe_again(account, owed):
        account.balance = round(account.balance + owed, 2)
        if hasattr(account, "regular_balance"):
            account.regular_balance = round(account.regular_balance + owed, 2)

    def unpay_loan(account, paid):
        """Put back the principal a loan payment took off (its interest was owed anyway)."""
        record = next((r for r in reversed(getattr(account, "payment_history", []))
                       if occ.paid_on(r) == day and abs(float(r.get("total_amount") or 0) - paid) < 0.01), None)
        principal = record.get("principal", 0.0) if record else 0.0  # includes any extra principal
        if principal:
            account.current_principal = round(account.current_principal + principal, 2)
            account.payment_history.remove(record)

    if isinstance(bill, AccountLinkedBill):
        account = bill.linked_account
        if bill.linked_account_type == "mortgage":
            unpay_loan(account, amount)
        else:
            owe_again(account, amount)
        done.append(f"{account.account_name} owes it again")
    elif isinstance(bill, GroupLinkedBill):
        for sub in entry.get("sub_payments") or []:
            b = _find_bank(manager, sub.get("bank_name") or "")
            name = sub.get("account_name")
            if b and name in b.mortgage_accounts:  # a loan in a loan group
                unpay_loan(b.mortgage_accounts[name], float(sub.get("amount") or 0.0))
                continue
            account = b.credit_accounts.get(name) if b else None
            if account is not None:
                owe_again(account, float(sub.get("amount") or 0.0))
        done.append(f"{bill.linked_group.group_name} owes it again")
    return done


def undo_payments(manager, bill, due: date) -> tuple[int, list[str]]:
    """Remove every payment recorded for ``due`` (putting moved money back)."""
    entries = occ.payments_for(bill, due)
    notes = []
    for entry in entries:
        notes += reverse_payment(manager, bill, entry)
    bill.payment_history = [e for e in bill.payment_history if all(e is not x for x in entries)]
    return len(entries), notes


# ─────────────────────────────────────────────────────────────────────────
#  Month view
# ─────────────────────────────────────────────────────────────────────────

class BillPaymentEntryType(graphene.ObjectType):
    date = graphene.String()
    amount = graphene.Float()
    source_bank = graphene.String()
    source_account = graphene.String()
    moved_money = graphene.Boolean()


class BillOccurrenceType(graphene.ObjectType):
    """One due date of one bill."""
    bill_name = graphene.String()
    display_name = graphene.String()
    kind = graphene.String(description="bill | floating | credit | mortgage | heloc | group")
    kind_label = graphene.String(description="Loans: Mortgage, Auto loan, Student loan, ...")
    due_date = graphene.String()
    amount = graphene.Float(description="What the due date owes")
    paid = graphene.Float()
    remaining = graphene.Float()
    status = graphene.String(description="paid | partial | skipped | none | overdue | unpaid | untracked")
    paid_on = graphene.String(description="Date of the latest payment for this due date")
    payments = graphene.List(BillPaymentEntryType)
    source_bank = graphene.String()
    source_account = graphene.String()
    is_floating = graphene.Boolean()
    has_actual_amount = graphene.Boolean()
    estimated_amount = graphene.Float()
    bank_name = graphene.String(description="Card/loan bank (credit, mortgage, HELOC)")
    account_name = graphene.String(description="Card/loan account (credit, mortgage, HELOC)")
    group_name = graphene.String()
    balance_owed = graphene.Float(description="What the card/loan/group still owes in total")


class BillMonthTotalsType(graphene.ObjectType):
    due = graphene.Float()
    paid = graphene.Float()
    remaining = graphene.Float()
    overdue = graphene.Float()


class BillMonthType(graphene.ObjectType):
    month = graphene.String()
    first_month = graphene.String()
    last_month = graphene.String()
    occurrences = graphene.List(BillOccurrenceType)
    totals = graphene.Field(BillMonthTotalsType)
    overdue_before = graphene.Float(description="Still owed from due dates before this month")


def _occurrence(manager, bill, due: date, today: date) -> BillOccurrenceType:
    entries = occ.payments_for(bill, due)
    st = occ.status(bill, due, today)
    owed = occ.amount_due(bill, due)
    # Before the bill was tracked by due date there's nothing to count as owed
    left = 0.0 if st in occ.SETTLED or st == "untracked" else occ.remaining(bill, due)
    last = max((occ.paid_on(e) for e in entries if occ.paid_on(e)), default=None)
    out = dict(
        bill_name=bill.bill_name, display_name=display_name(bill), kind=kind_of(bill),
        due_date=due.isoformat(), amount=round(owed, 2), paid=occ.paid_amount(bill, due),
        remaining=round(left, 2), status=st, paid_on=last.isoformat() if last else None,
        payments=[BillPaymentEntryType(date=(occ.paid_on(e) or due).isoformat(), amount=float(e.get("amount_paid") or 0),
                                       source_bank=e.get("source_bank") or "",
                                       source_account=e.get("source_account") or "",
                                       moved_money=e.get("moved_money")) for e in entries],
        source_bank=bill.preferred_source_bank or "", source_account=bill.preferred_source_account or "",
        is_floating=isinstance(bill, FloatingBill),
        has_actual_amount=isinstance(bill, FloatingBill) and occ.actual_for(bill, due) is not None,
        estimated_amount=getattr(bill, "estimated_amount", None),
    )
    if isinstance(bill, AccountLinkedBill):
        out.update(bank_name=bill.linked_bank_name, account_name=bill.linked_account.account_name,
                   balance_owed=round(bill.linked_account_balance, 2),
                   kind_label=getattr(bill.linked_account, "kind_label", None))
    elif isinstance(bill, GroupLinkedBill):
        out.update(group_name=bill.linked_group.group_name,
                   balance_owed=round(bill.linked_group.get_total_balance(manager.banks), 2))
    return BillOccurrenceType(**out)


def bill_month(manager, month: str | None, today: date | None = None) -> BillMonthType:
    today = today or date.today()
    if month:
        try:
            year, mon = (int(x) for x in month.split("-")[:2])
            start = date(year, mon, 1)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid month '{month}'. Use YYYY-MM.")
    else:
        start = today.replace(day=1)
    y, m = add_months(start.year, start.month, 1)
    end = date(y, m, 1) - timedelta(days=1)
    grouped = manager.get_grouped_account_keys()
    rows, before = [], 0.0
    for bill in manager.bills:
        if isinstance(bill, AccountLinkedBill) and (bill.linked_bank_name, bill.linked_account.account_name) in grouped:
            continue
        before += sum(left for d, left in occ.overdue(bill, min(start, today)) if d < start)
        for due in occ.due_dates(bill, start, end):
            row = _occurrence(manager, bill, due, today)
            # A paid-off card or loan with nothing recorded has nothing to show
            if row.status == "none" and not row.payments:
                continue
            rows.append(row)
    rows.sort(key=lambda r: (r.due_date, r.display_name.lower()))
    first, last = month_range()
    totals = BillMonthTotalsType(
        due=round(sum(r.amount for r in rows if r.status not in ("skipped", "none", "untracked")), 2),
        paid=round(sum(r.paid for r in rows), 2),
        remaining=round(sum(r.remaining for r in rows), 2),
        overdue=round(sum(r.remaining for r in rows if r.due_date < today.isoformat()), 2),
    )
    return BillMonthType(month=f"{start.year:04d}-{start.month:02d}", first_month=first, last_month=last,
                         occurrences=rows, totals=totals, overdue_before=round(before, 2))


class BillsQuery(graphene.ObjectType):
    bill_month = graphene.Field(BillMonthType, month=graphene.String(description="YYYY-MM (default: this month)"))

    def resolve_bill_month(self, info, month=None):
        manager = _manager(info)
        if not manager:
            return None
        return bill_month(manager, month)


# ─────────────────────────────────────────────────────────────────────────
#  Mutations
# ─────────────────────────────────────────────────────────────────────────

class UndoBillPayment(graphene.Mutation):
    """
    Remove the payments recorded for one due date of a bill, so it's owed
    again. Money the app moved for them is put back (the source account gets
    it back; a card or loan owes it again).
    """
    class Arguments:
        bill_name = graphene.String(required=True)
        due_date = graphene.String(description="YYYY-MM-DD (default: the latest due date with a payment)")

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, due_date=None):
        manager = _manager(info)
        bill = find_bill(manager, bill_name) if manager else None
        if not bill:
            return UndoBillPayment(success=False, message=f"Bill '{bill_name}' not found")
        try:
            due = resolve_due(bill, due_date) if due_date else occ.latest_paid_due(bill)
        except ValueError as e:
            return UndoBillPayment(success=False, message=str(e))
        if due is None or not occ.payments_for(bill, due):
            return UndoBillPayment(success=False, message="No payment recorded for that due date")
        count, notes = undo_payments(manager, bill, due)
        manager.save_to_database()
        extra = f" ({'; '.join(notes)})" if notes else ""
        return UndoBillPayment(success=True, message=(
            f"{display_name(bill)} due {due:%b} {due.day}: {count} payment(s) removed{extra}"))


class SkipBillOccurrence(graphene.Mutation):
    """
    Mark one due date of a bill as not owed (waived, or paid some way the app
    doesn't track) — or owed again with skip: false.
    """
    class Arguments:
        bill_name = graphene.String(required=True)
        due_date = graphene.String(required=True)
        skip = graphene.Boolean(default_value=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, bill_name, due_date, skip=True):
        manager = _manager(info)
        bill = find_bill(manager, bill_name) if manager else None
        if not bill:
            return SkipBillOccurrence(success=False, message=f"Bill '{bill_name}' not found")
        try:
            due = resolve_due(bill, due_date)
        except ValueError as e:
            return SkipBillOccurrence(success=False, message=str(e))
        key = occ.period(bill, due)
        rest = {d for d in bill.skipped if occ.period(bill, d) != key}
        bill.skipped = rest | {due} if skip else rest
        manager.invalidate_plan_cache()
        manager.save_to_database()
        what = "skipped" if skip else "owed again"
        return SkipBillOccurrence(success=True, message=f"{display_name(bill)} due {due.isoformat()} {what}")


class BillsMutation(graphene.ObjectType):
    undo_bill_payment = UndoBillPayment.Field()
    skip_bill_occurrence = SkipBillOccurrence.Field()
