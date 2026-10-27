"""Debt Payoff Estimator - Compare snowball vs avalanche strategies."""
from dataclasses import dataclass, field


@dataclass
class DebtInfo:
    name: str
    balance: float
    interest_rate: float
    minimum_payment: float


@dataclass
class DebtPayoffResult:
    strategy: str
    months_to_payoff: int
    total_interest_paid: float
    total_paid: float
    monthly_breakdown: list = field(default_factory=list)
    payoff_order: list = field(default_factory=list)
    # False when some debt still has a balance when the simulation stops
    # (hit MAX_MONTHS, or payments no longer reduce the total balance).
    # In that case months_to_payoff is the number of months simulated,
    # not a payoff date.
    pays_off: bool = True
    # Total balance left when the simulation stopped (0.0 when fully paid)
    remaining_balance: float = 0.0
    # Names of debts that were never paid off (e.g. minimum <= interest)
    never_amortizes: list = field(default_factory=list)


class DebtPayoffEstimator:
    # Simulation horizon (50 years). Debts still open at this point are
    # reported via pays_off=False instead of being silently truncated.
    MAX_MONTHS = 600

    @staticmethod
    def estimate(debts, extra_monthly=0.0):
        """
        Compare payoff strategies.

        - minimum: pay only each debt's minimum; freed minimums are not reused.
        - avalanche / snowball: fixed monthly budget = sum of all minimums +
          extra_monthly. Each month the minimums of open debts are paid, and
          the rest of the budget (extra + minimums freed by paid-off debts)
          cascades onto targets in order (highest rate first / smallest
          balance first) until it is used up.
        """
        if not debts or all(d.balance <= 0 for d in debts):
            e = DebtPayoffResult('none', 0, 0, 0)
            return {'minimum': e, 'avalanche': e, 'snowball': e}
        return {
            'minimum': DebtPayoffEstimator._sim(debts, 0, 'minimum'),
            'avalanche': DebtPayoffEstimator._sim(debts, extra_monthly, 'avalanche'),
            'snowball': DebtPayoffEstimator._sim(debts, extra_monthly, 'snowball'),
        }

    @staticmethod
    def _sim(debts, extra_monthly, strategy):
        bals = {d.name: d.balance for d in debts if d.balance > 0}
        rates = {d.name: d.interest_rate for d in debts if d.balance > 0}
        mins = {d.name: max(0.0, d.minimum_payment) for d in debts if d.balance > 0}
        if not bals:
            return DebtPayoffResult(strategy, 0, 0, 0)

        # Fixed monthly budget for the cascading strategies
        budget = sum(mins.values()) + max(0.0, extra_monthly or 0.0)

        ti = tp = 0.0
        months = 0
        order = []
        bd = []
        stalled = False

        def settle(n):
            """Mark a debt as paid off if its balance is (nearly) zero."""
            if bals[n] <= 0.01:
                bals[n] = 0
                if n not in order:
                    order.append(n)

        while any(b > 0.01 for b in bals.values()) and months < DebtPayoffEstimator.MAX_MONTHS:
            months += 1
            before = dict(bals)

            # Interest accrues on open balances
            for n in bals:
                if bals[n] > 0:
                    i = bals[n] * rates[n] / 1200
                    bals[n] += i
                    ti += i

            # Minimum payments on every open debt
            paid_this_month = 0.0
            for n in bals:
                if bals[n] > 0:
                    p = min(mins[n], bals[n])
                    bals[n] -= p
                    paid_this_month += p
                    settle(n)

            # Cascade the rest of the budget onto targets in strategy order
            if strategy in ('avalanche', 'snowball'):
                remainder = budget - paid_this_month
                while remainder > 0.005:
                    t = DebtPayoffEstimator._pick(bals, rates, strategy)
                    if not t:
                        break
                    ep = min(remainder, bals[t])
                    bals[t] -= ep
                    paid_this_month += ep
                    remainder -= ep
                    settle(t)

            tp += paid_this_month
            total_after = sum(bals.values())

            if months <= 12 or months % 6 == 0:
                bd.append({'month': months, 'total_remaining': round(total_after, 2)})

            # No debt got smaller this month (payments don't cover interest) —
            # the remaining debts will never pay off, stop instead of looping
            if total_after > 0.01 and not any(bals[n] < before[n] - 1e-9 for n in bals):
                stalled = True
                break

        remaining = round(sum(b for b in bals.values() if b > 0.01), 2)
        if bd and bd[-1]['month'] != months:
            bd.append({'month': months, 'total_remaining': remaining})
        never = [n for n, b in bals.items() if b > 0.01]
        result = DebtPayoffResult(strategy, months, round(ti, 2), round(tp, 2), bd, order)
        result.pays_off = not never
        result.remaining_balance = remaining if never else 0.0
        result.never_amortizes = never
        if stalled or never:
            result.pays_off = False
        return result

    @staticmethod
    def _pick(bals, rates, strategy):
        a = {k: v for k, v in bals.items() if v > 0.01}
        if not a:
            return None
        if strategy == 'avalanche':
            return max(a, key=lambda k: rates.get(k, 0))
        if strategy == 'snowball':
            return min(a, key=lambda k: a[k])
        return None
