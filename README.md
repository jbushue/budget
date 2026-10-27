# Budget Manager

A personal finance planner that models your accounts, income, and bills, projects your balances day by day, and answers two questions at a glance: **can my bills be paid?** and **how much can I spend without going under?** It also tracks real transactions, budgets, and savings goals, recommends the best way to get every bill paid, and alerts you when something needs attention.

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

**Dashboard**
- A status banner (are all bills covered, and through when?)
- **Safe to spend** — based on your *lowest* projected checking balance through your second payday, minus a cushion you choose, overdue bills, bills that can't be covered, and money set aside for goals; also shown per day until payday
- A pay-period checklist of bills (paid / covered / short / overdue) with one-click **Mark paid**
- Everyday spending (groceries, gas, eating out) built into every projection — enter a weekly amount or let it be learned from your transactions

**Transactions, budgets, and goals**
- Transactions from SimpleFIN (automatic), your bank's CSV export (columns detected for you), or manual entry
- Categories with "everyday" flags and monthly budgets; auto-categorizing keyword rules that learn from your choices
- **Budgets** page with progress and month-end pace
- **Savings goals and sinking funds** — money set aside in checking is kept out of Safe to spend; non-monthly bills get "save up for this" suggestions
- Bill payments are **recognized in your transactions** and marked paid automatically (no money moved twice); repeating charges that aren't bills yet are suggested

**Planning and analysis**
- **Timeline** — a day-by-day projection with a financial calendar
- **Payment Optimizer** — compares *paying every bill on its due date* with an *optimized plan* (savings sweeps, HELOC parking, promo payoffs) and explains, in plain language:
  - which bills will be short and how to fix it
  - which payments are worth making early on payday (and how much that saves) — and which aren't
  - how a loan group's payment is split, and what aiming it at the highest rate or paying a little more would save
  - which 0% promos are on track before they expire
- **Debt Payoff** — minimum-only vs. avalanche vs. snowball
- **What-If Scenarios** — job loss, a raise, new or cut bills, paid-off debts — with a plain-language verdict
- **Late and overdraft fees** are modeled (app-wide defaults plus a per-bill late fee)
- **Reports** — income vs. spending, where the money went, category trends, net worth over time

**Alerts**
- A bell with everything that needs attention: overdue or short bills, bills due soon, a low balance ahead, budgets running over, payments to review
- Optional browser notifications and a daily email digest

**Data and access**
- Everything is saved automatically to a local SQLite database
- Excel import/export and a fill-in template, a transactions CSV, and one-click database **backup / restore** — all from Settings
- Optional **password login** to use it from your phone or other devices on your network; installable as an app (PWA)

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

The web dev server proxies the API (`/graphql`, `/files`, `/auth`), so only port 3000 needs to be opened in the browser.

**One server instead of two:** after `cd web-ui && npm run build`, `python api_server.py` also serves the built web interface at http://localhost:4000 — and from there it can be installed as an app.

### Using it from your phone
The web interface (port 3000) listens on your network, but the API only answers this computer until you **set a password** in *Settings → Security*. After that, open `http://<this computer's address>:3000` on your phone and sign in (sessions last 30 days). Adding it to the home screen works there too; the offline app shell needs HTTPS or localhost.

### Where your data lives
`~/.budget_app/finance.db` (on Windows `C:\Users\<you>\.budget_app\finance.db`). *Settings → Data & backup → Download backup* saves a copy of it; restoring keeps a copy of the replaced data in `~/.budget_app/backups/`.

### Server options
| Environment variable | Default | Purpose |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Address the API listens on. The default is right when you use the web interface (it reaches the API through its proxy). If you expose the API directly, set a password first. |
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
  dashboard.py           Dashboard summary: bills status, safe to spend, pay-period checklist
  app_settings.py        App settings (cushion, everyday spending, fees, alerts, email)
  ledger.py              Transactions, CSV/SimpleFIN import, categories, rules, budgets, reports
  goals.py               Savings goals and sinking funds
  bill_matching.py       Recognize bill payments in transactions; detect recurring charges
  alerts.py              Alerts and the daily email digest
  auth.py, web_routes.py Password login, access rules, file routes, serving the built UI
  debt_estimator.py      Debt payoff strategies
  bank.py, bank_account.py, credit_card_account.py, mortgage_account.py, heloc_account.py
  fixed_bill.py          Bills, variable bills, and auto-created linked bills
  bill_group.py          Loan groups and payment allocation
  income_source.py       Income schedules and distribution
  database.py, db_repository.py   SQLite schema, migrations, persistence
  graphql_schema.py      GraphQL types, queries, and mutations (core)
  gql_ext.py, gql_ledger.py, gql_goals.py   GraphQL for the features above
  data_import_export.py  Excel import/export
  simplefin.py           SimpleFIN Bridge client
web-ui/                  Vue 3 + Vite + Apollo + Chart.js web interface
  src/views/             One file per page
  src/components/        Shared pieces (alert bell, mark-paid dialog, settings sections, ...)
  src/graphql/           GraphQL documents used by the UI
  public/                PWA manifest, service worker, icons
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

Working end to end: accounts (including mortgages, HELOCs, promos), bills and loan groups, income, payments and history, projections, the dashboard and safe-to-spend, transactions, budgets, goals and sinking funds, bill matching, recurring-charge detection, alerts and the email digest, the optimizer and its recommendations, fees, debt payoff, what-if scenarios, reports, persistence, Excel import/export, backup/restore, SimpleFIN sync, password login, and the installable app.

Known limitations:
- Weekly/bi-weekly items without a start date guess their schedule; set a start date for accuracy.
- What-If compares plain simulations (without optimizer moves).
- Excel export covers accounts, bills, and income — not payment status, transactions, budgets, goals, or settings. Use **Download backup** for a complete copy.
- The optimizer's "pay off a specific card" goal is available from Python only, not the web interface.
- Bill matching looks at the last 45 days of transactions; older payments can be marked paid by hand.
- The email digest is sent by the running API server, so it only goes out while the app is running.
- No HTTPS of its own: on your home network the password protects access, but traffic isn't encrypted. Don't expose it to the internet without a reverse proxy that adds HTTPS.

No license has been chosen yet.
