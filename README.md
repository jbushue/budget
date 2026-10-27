# Budget Manager

A personal finance planner that models your accounts, income, and bills, projects your balances day by day, and recommends the best way to get every bill paid — when to pay, from which account, and what paying early, late, or differently would change.

It runs locally: a Python GraphQL API with a SQLite database, and a Vue 3 web interface.

**📖 New here? Read the [User Guide](docs/USER_GUIDE.md)** — it walks through every page of the web interface and explains every number.

---

## Features

**Accounts**
- Banks with checking and savings accounts (APY and interest dates)
- Credit cards with APR, statement/due dates, minimum payments, and **0% promo offers** with deferred-interest tracking
- **Mortgages** (amortization, escrow, equity) and **HELOCs** (draw and repayment phases)
- Loan groups ("bill groups") — one payment split across several loans (e.g. student loans), proportionally, equally, or by fixed amounts
- Optional automatic balance sync through [SimpleFIN Bridge](https://bridge.simplefin.org)

**Bills and income**
- Fixed and variable bills; one-time, weekly, bi-weekly, monthly, quarterly, semi-annual, and yearly schedules
- Card, mortgage, HELOC, and loan-group payments are created automatically as bills
- Mark bills paid (from checking, savings, or a card), with partial payments, carryover, and payment history
- Income sources with flexible schedules and per-account distribution (fixed, percentage, remainder)

**Planning and analysis**
- **Dashboard** — net worth, *Discretionary Funds* (what's safe to spend before your next paychecks), upcoming bills, and the top recommendations
- **Timeline** — a day-by-day projection with a financial calendar
- **Payment Optimizer** — compares *paying every bill on its due date* with an *optimized plan* (savings sweeps, HELOC parking, promo payoffs) and explains, in plain language:
  - which bills will be short and how to fix it
  - which payments are worth making early on payday (and how much that saves) — and which aren't
  - how a loan group's payment is split, and what aiming it at the highest rate or paying a little more would save
  - which 0% promos are on track before they expire
- **Debt Payoff** — minimum-only vs. avalanche vs. snowball
- **What-If Scenarios** — job loss, a raise, new or cut bills, paid-off debts — with a plain-language verdict

**Data**
- Everything is saved automatically to a local SQLite database
- Excel import/export and a fill-in template (via the command-line menu)

---

## Getting started

### Requirements
- Python 3.13+
- Node.js 20+

### Windows: one click
Double-click **`start.bat`**. It installs missing dependencies, starts the API and the web interface in two windows, and opens your browser at http://localhost:3000.

### Manual start
```bash
# Python dependencies (use a virtual environment if you like)
pip install flask flask-cors graphene sqlalchemy openpyxl
#   or, with uv:  uv sync

# Terminal 1 — API server (http://127.0.0.1:4000, GraphQL playground at /graphql)
python api_server.py

# Terminal 2 — web interface (http://localhost:3000)
cd web-ui
npm install
npm run dev
```

The web dev server proxies `/graphql` to the API, so only port 3000 needs to be opened in the browser.

### Where your data lives
`~/.budget_app/finance.db` (on Windows `C:\Users\<you>\.budget_app\finance.db`). Back up that file to back up everything.

### Server options
| Environment variable | Default | Purpose |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Address the API listens on. Keep the default unless you know you need network access — the API has no login. |
| `BUDGET_DEBUG` | off | Set to `1` for Flask debug mode. |

### Command-line menu
`python cli.py` opens an interactive text menu with the same features, plus Excel import/export and report exports.

---

## Project layout

```
api_server.py            Flask + GraphQL API server
cli.py                   Interactive command-line menu
start.bat                Windows launcher (API + web UI)
models/
  finance_manager.py     Orchestrator: holds state, runs projections/optimization, saves/loads
  timeline_simulator.py  Day-by-day simulation of income, bills, interest, and transfers
  payment_optimizer.py   Two-pass optimizer (routing, sweeps, HELOC parking, promo payoffs)
  payment_insights.py    Plain-language comparison and recommendations for the Optimizer page
  debt_estimator.py      Debt payoff strategies
  bank.py, bank_account.py, credit_card_account.py, mortgage_account.py, heloc_account.py
  fixed_bill.py          Bills, variable bills, and auto-created linked bills
  bill_group.py          Loan groups and payment allocation
  income_source.py       Income schedules and distribution
  database.py, db_repository.py   SQLite schema, migrations, persistence
  graphql_schema.py      GraphQL types, queries, and mutations
  data_import_export.py  Excel import/export
  simplefin.py           SimpleFIN Bridge client
web-ui/                  Vue 3 + Vite + Apollo + Chart.js web interface
  src/views/             One file per page
  src/graphql/queries.ts All GraphQL documents used by the UI
docs/USER_GUIDE.md       Web interface user guide
tests/                   pytest suite
```

---

## Using it as a Python library

```python
from datetime import date, timedelta
from models.bank import Bank
from models.fixed_bill import Bill
from models.income_source import IncomeSource
from models.finance_manager import FinanceManager

bank = Bank("My Bank")
bank.add_account("checking", "Checking", starting_balance=2500.00)
bank.add_account("savings", "Savings", starting_balance=10000.00, interest_rate=4.5)
bank.add_credit_account("Visa", credit_limit=8000, interest_rate=22.0, payment_due_date=20)

salary = IncomeSource("Salary", 5000.00, frequency="monthly", pay_date=1,
                      distribution={"Checking": 3500.00, "Savings": "remainder"})
rent = Bill("Rent", 1500.00, due_date=1, frequency="monthly")

manager = FinanceManager([bank], [salary], [rent])

# Projected balances in 30 days
print(manager.get_balance_on_date(date.today() + timedelta(days=30)))

# Optimized plan for the next 90 days
plan = manager.optimize_payments(end_date=date.today() + timedelta(days=90))
print(plan.final_discretionary, plan.violations)

# Plain-language recommendations (what the Optimizer page shows)
insights = manager.payment_insights(days=90)
print(insights["headline"])
for item in insights["insights"]:
    print(item["severity"], item["title"])
```

`FinanceManager` also offers `project_balances`, `forecast_cash_flow`, `calculate_safe_to_spend`, `run_what_if_scenario`, report generators (`generate_snapshot`, `generate_payment_schedule`, …), and `save_to_database` / `load_from_database`. [QUICK_REFERENCE.md](QUICK_REFERENCE.md) has more library examples, and `example.py` / `demo_promos.py` are runnable demos.

---

## Development

```bash
pytest                         # backend test suite
cd web-ui && npm run build     # type-check (vue-tsc) and production build
```

Tests use a temporary database, so they never touch your real data.

---

## Current status

Working end to end: accounts (including mortgages, HELOCs, promos), bills and loan groups, income, payments and history, projections, the optimizer and its recommendations, debt payoff, what-if scenarios, persistence, Excel import/export, and SimpleFIN sync.

Known limitations:
- Weekly/bi-weekly items without a start date guess their schedule; set a start date for accuracy.
- What-If compares plain simulations (without optimizer moves).
- Excel export doesn't include payment status (paid this period, carryover, history).
- The optimizer's "pay off a specific card" goal is available from Python only, not the web interface.
- Fees (late fees, overdraft fees) aren't modeled.
- The API has no authentication — it's meant to run on your own machine.

No license has been chosen yet.
