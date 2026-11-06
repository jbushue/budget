# Budget Manager

A personal finance planner that models your accounts, income, and bills, projects your balances day by day, and answers two questions at a glance: **can my bills be paid?** and **how much can I spend without going under?** It also tracks real transactions, budgets, and savings goals, recommends the best way to get every bill paid, and alerts you when something needs attention.

It runs locally: a Python GraphQL API with a SQLite database, and a Vue 3 web interface.

**📖 New here? Read the [User Guide](docs/USER_GUIDE.md)** — it walks through every page of the web interface and explains every number.

---

## Features

**Accounts**
- Banks with checking and savings accounts (APY and interest dates), plus **every other kind of account**: money market, CDs, cash, prepaid cards, PayPal/Venmo/Cash App, **EBT / SNAP**, HSA, FSA, brokerage, retirement and other
- Each kind is treated the way it works in real life: benefits (EBT, HSA, FSA), CDs and investments never pay bills or count as spending money; investments grow at the rate you expect
- **EBT and other benefit cards**: a monthly benefit deposit on its day, weekly grocery spending that can replace part of your everyday spending (checking takes over when the benefits run out), and the dashboard shows when they'll run out before the next deposit
- Credit cards with APR, statement/due dates, minimum payments, and **0% promo offers** with deferred-interest tracking
- **Mortgages** (amortization, escrow, equity), **auto loans** (vehicle value that depreciates), **student loans** (deferment, with interest capitalized when payments start), **personal and other loans**, and **HELOCs** (draw and repayment phases). Any loan can use the payment from the lender's statement; a loan entered as a card can be converted to a real loan
- Loan groups ("bill groups") — one payment split across several cards and loans (e.g. student loans), proportionally, equally, or by fixed amounts
- Every setting editable later; rename an account or move it to another bank and its bills, history, transactions and links follow
- Optional automatic balance sync through [SimpleFIN Bridge](https://bridge.simplefin.org)
- **Update all balances** in one pass (a quick check-in from your bank apps), and **move money** between accounts at any bank
- Promo offers: charge a purchase to a 0% promo, or **pay a promo down** from checking before it expires
- Loan tools: **amortization schedule** (next 12 payments and year by year), an **early-payoff calculator** (how much sooner and how much interest an extra monthly amount saves), and one-time **extra principal** payments

**Bills and income**
- Fixed and variable bills; one-time, weekly, bi-weekly, monthly, quarterly, semi-annual, and yearly schedules
- Card, loan, HELOC, and loan-group payments are created automatically as bills
- Pay bills month by month (from checking, savings, or a card): pay ahead, catch up on a missed month, skip one, partial payments, undo, and payment history
- Income sources with flexible schedules and per-account distribution — dollar amounts or percentages, plus "the rest"
- Variable bills keep their **amount history** (average, low, high) and go back to the estimate after they're paid — or on demand

**Dashboard**
- A status banner (are all bills covered, and through when?)
- **Safe to spend** — based on your *lowest* projected checking balance through your second payday, after overdue bills and any bill paid late (owed until it's paid), minus a cushion you choose and money set aside for goals; also shown per day until payday
- A pay-period checklist of bills (paid / covered / short / overdue) with one-click **Mark paid**
- Everyday spending (groceries, gas, eating out) built into every projection — enter a weekly amount or let it be learned from your transactions

**Transactions, budgets, and goals**
- Transactions from SimpleFIN (automatic), your bank's CSV export (columns detected for you), or manual entry
- Categories with "everyday" flags and monthly budgets; auto-categorizing keyword rules that learn from your choices
- **Split transactions** across categories, **tags** (e.g. `vacation`, `reimbursable`), filters by tag / amount / direction, and **CSV export** of whatever matches
- **Budgets** page with progress and month-end pace, **rollover** (envelope-style carry-forward), **suggested budgets** from your recent spending, and **left to budget** — expected income minus bills, budgets and goal saving
- **Savings goals and sinking funds** — money set aside in checking is kept out of Safe to spend; non-monthly bills get "save up for this" suggestions
- Bill payments are **recognized in your transactions** and marked paid automatically (no money moved twice); repeating charges that aren't bills yet are suggested

**Planning and analysis**
- **One plan for the whole app** — the plan is worked out once, day by day for a year, and the dashboard, timeline, Plan page, what-if, alerts and the digest all read it, so they agree on every day; period pickers only change how much you see, and checking never drops below your cushion
- **Timeline** — the plan day by day as a calendar, a filterable list (income, bills, cards and loans, transfers), a month-by-month summary, or end balances, for up to a year
- **Plan** (formerly the Payment Optimizer) — tabs for Overview, Bills, Debt and *Can I afford it?*; compares *paying every bill on its due date* with an *optimized plan* (paying down costly debt with spare cash, savings sweeps, HELOC parking, promo payoffs, covering missed bills). Every move is verified in a full simulation, so the plan is never worse than paying on due dates. It explains, in plain language:
  - which bills will be short and how to fix it
  - which payments are worth making early on payday (and how much that saves) — and which aren't
  - how a loan group's payment is split, and what aiming it at the highest rate or paying a little more would save
  - which 0% promos are on track before they expire
  - and lets you choose the goal — **most cash**, **least interest**, or **pay off one card** — and compare all three side by side. The chosen goal is **the plan the whole app follows**: dashboard, bills checklist, timeline, alerts and the digest
  - **0% promos are paid off on time**: every card payment gives each promo its share first, so it's cleared by the payment before it expires; promos that can't be cleared raise an alert
  - **Safe to spend looks ahead** (90 days by default) and holds back money needed for bills after your next paycheck, plus anything the plan can't pay on time
  - **Pay down debt faster**: searches for the most you can put toward debt each month without checking ever dropping below your cushion or a bill going late (every amount is simulated), sends it highest-interest-first or smallest-first, and shows the interest saved and payoff dates
  - **Better due dates**: finds bills due at the wrong time for your paydays and the day to ask the company to move them to
  - **When can I buy it?**: how much you could spend on each day ahead, and the earliest day a purchase fits
  - **When will I be debt-free?**: minimum-only vs. highest interest first vs. smallest balance first
- **What-If Scenarios** — job loss, a raise, new or cut bills, paid-off debts — the plan is re-made for the change and compared with your plan now, with a plain-language verdict
- **Late and overdraft fees** are modeled (app-wide defaults plus a per-bill late fee)
- **Reports** — income vs. spending, where the money went, category trends, net worth over time, and a **year in review** (totals, savings rate, top categories and payees, biggest purchases, spending by tag)
- **Net worth with assets** — vehicles, investments, retirement, property and valuables with value history and equity against their loans, counted in net worth everywhere
- **Financial health check** — a 0–100 score from savings rate, emergency fund, debt-to-income, card utilization, high-interest debt, budgets kept and net worth trend, with what to do about each
- **Subscriptions** — every recurring charge with its monthly and yearly cost, and price increases flagged

**Alerts**
- A bell with everything that needs attention: overdue or short bills, bills due soon, a low balance ahead, budgets running over, payments to review
- Optional browser notifications, **phone push notifications** (ntfy) and a **daily email digest**: a designed HTML email (status, Safe to spend, alerts, this pay period's bills, paychecks, benefits, budgets and optimizer tips) with a plain-text version, previewed in Settings

**Data and access**
- Everything is saved automatically to a local SQLite database
- Excel import/export and a fill-in template, a transactions CSV, and one-click database **backup / restore** — all from Settings, along with record counts and the database size
- **Report downloads** (CSV or Excel): month by month, every projected payment and paycheck, the payment plan, daily balances, and today's accounts; any page prints cleanly to PDF
- A **calendar file** (.ics) of the next six months of bills and paydays, with a reminder the day before each bill, for Google, Apple or Outlook calendar
- **Search and quick actions** (Ctrl+K or /): jump to any page, account, bill, income or goal, search transactions, or start an action (add a bill, move money, update balances...)
- **User accounts**: everyone signs in with their own username and password and shares the same budget; new people join with an invite link from an admin. Works from your phone or other devices on your network; installable as an app (PWA)
- **Activity history** — who changed what, and when; see and sign out your signed-in devices
- **Light and dark themes** (or follow the device's setting), and a layout that adapts to phones, tablets and desktops

**Running it as a server**
- Production web server (waitress), Docker image and compose file, systemd unit, Caddy example for HTTPS
- Background jobs while it runs: daily **automatic backups** (kept on the server, restorable from Settings), **SimpleFIN auto-sync**, bill-period roll-over and net worth history, the email digest and push notifications

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

### The admin account
The first time `python api_server.py` starts, it creates the admin account **admin** with a random password. The password is printed in the server's output and saved in `~/.budget_app/initial-admin-password.txt` until you change it (the file is then deleted). Change it in *Settings → Your account*, or from a shell — handy on a headless server:

```bash
cat ~/.budget_app/initial-admin-password.txt
curl -X POST http://localhost:4000/auth/password -H 'Content-Type: application/json' \
     -d '{"username": "admin", "current_password": "<generated>", "new_password": "<yours>"}'
```

Until you change it, the web UI shows a reminder. Lost it? `python -m models.auth reset-password admin` sets a new one from the server's shell.

### Running it on a headless server
The API server also serves the built web interface, so one process on port 4000 is all you need. Pick one:

**Docker** (simplest):
```bash
TZ=America/Chicago docker compose up -d      # your time zone: bills and backups use local time
docker compose logs budget                     # the generated admin password
```
Data lives in the `budget-data` volume (`/data` in the container).

**systemd** (Linux, no Docker): see the steps at the top of [`deploy/budget.service`](deploy/budget.service). Data goes to `/var/lib/budget`; `journalctl -u budget` shows the admin password.

**By hand:** `cd web-ui && npm ci && npm run build`, then `BUDGET_HOST=0.0.0.0 python api_server.py`.

Then open `http://<server address>:4000`, sign in as **admin**, and change the password (or use the `curl` above).

**HTTPS:** there's none built in. Put a reverse proxy in front — [`deploy/Caddyfile`](deploy/Caddyfile) gets certificates automatically — and set `BUDGET_TRUSTED_PROXIES=1` so the app sees real client addresses and secure cookies work. Without HTTPS, keep it on your home network.

**While it runs** it does the upkeep a long-running server needs (Settings → Background jobs shows the last results): rolls bill periods over and records net worth daily, makes a daily backup (Settings → Data & backup; the newest 14 are kept by default), syncs SimpleFIN every few hours if you turn that on, and sends the email digest and phone notifications if set up.

### Using it from your phone
Open `http://<this computer's address>:3000` on your phone and sign in (sign-ins last 30 days). To add people, create an invite link in *Settings → Users* and send it to them. Adding it to the home screen works there too; the offline app shell needs HTTPS or localhost.

### Where your data lives
`~/.budget_app/finance.db` (on Windows `C:\Users\<you>\.budget_app\finance.db`). *Settings → Data & backup → Download backup* saves a copy of it; restoring keeps a copy of the replaced data in `~/.budget_app/backups/`.

### Server options
| Environment variable | Default | Purpose |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Address the API listens on. The default is right when you use the web interface (it reaches the API through its proxy). Use `0.0.0.0` to reach the built-in web interface (port 4000) from other devices, e.g. on a headless server. |
| `BUDGET_PORT` | `4000` | Port to listen on. |
| `BUDGET_DATA_DIR` | `~/.budget_app` | Where the database, backups and the generated admin password are kept. |
| `BUDGET_TRUSTED_PROXIES` | `0` | Number of reverse proxies in front (e.g. `1` behind Caddy or nginx). Only then are their `X-Forwarded-*` headers believed. |
| `BUDGET_CORS_ORIGINS` | none | Comma-separated origins allowed to call the API from another site (e.g. `https://budget.example.com`). CORS is off by default: the built-in web interface and the Vite dev proxy are same-origin, so they don't need it. |
| `BUDGET_THREADS` | `8` | Web server worker threads. |
| `BUDGET_DEBUG` | off | Set to `1` for Flask's development server with auto-reload. Never on a network: its debugger can run code. |

### Command-line menu
`python cli.py` opens an interactive text menu. The web interface covers the same ground (transfers, promo purchases and payments, mortgage schedules and extra principal, payment strategies, report exports and more).

---

## Project layout

```
api_server.py            Flask + GraphQL API server
cli.py                   Interactive command-line menu
start.bat                Windows launcher (API + web UI)
models/
  finance_manager.py     Orchestrator: holds state, runs projections/optimization, saves/loads
  timeline_simulator.py  Day-by-day simulation of income, bills, interest, and transfers
  payment_optimizer.py   Optimizer: candidate plans and moves, each verified by a full simulation
  account_edit.py        Editing/renaming banks and accounts (references follow)
  payment_insights.py    Plain-language comparison and recommendations for the Optimizer page
  dashboard.py           Dashboard summary: bills status, safe to spend, pay-period checklist
  app_settings.py        App settings (cushion, everyday spending, fees, alerts, email)
  ledger.py              Transactions, CSV/SimpleFIN import, categories, rules, budgets, reports
  goals.py               Savings goals and sinking funds
  assets.py              Assets (cars, investments, property...) with value history; net worth breakdown
  planning.py            Left to budget, financial health check, subscriptions, year in review
  bill_matching.py       Recognize bill payments in transactions; detect recurring charges
  alerts.py              Alerts and the daily email digest
  digest_email.py        The digest as an HTML email
  optimizer_plus.py      Debt boost, due-date moves and the purchase planner (simulation-checked)
  notify.py              Phone push notifications (ntfy)
  jobs.py                Background jobs: daily upkeep, backups, SimpleFIN sync, digest, push
  backups.py             Database backups kept on the server
  activity.py            Activity history (who changed what)
  auth.py, web_routes.py User accounts, invites, sessions, access rules, file routes, serving the built UI
  debt_estimator.py      Debt payoff strategies
  bank.py, bank_account.py, credit_card_account.py, mortgage_account.py, heloc_account.py
  fixed_bill.py          Bills, variable bills, and auto-created linked bills
  bill_group.py          Loan groups and payment allocation
  income_source.py       Income schedules and distribution
  database.py, db_repository.py   SQLite schema, migrations, persistence
  graphql_schema.py      GraphQL types, queries, and mutations (core)
  gql_ext.py, gql_ledger.py, gql_goals.py, gql_planning.py, gql_accounts.py   GraphQL for the features above
  data_import_export.py  Excel import/export
  simplefin.py           SimpleFIN Bridge client
web-ui/                  Vue 3 + Vite + Apollo + Chart.js web interface
  src/views/             One file per page
  src/components/        Shared pieces (alert bell, mark-paid dialog, settings sections, ...)
  src/graphql/           GraphQL documents used by the UI
  public/                PWA manifest, service worker, icons
deploy/                  systemd unit and Caddy (HTTPS) example; Dockerfile and docker-compose.yml at the top
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

Tests use a temporary database, so they never touch your real data. GitHub Actions runs both, plus a Docker build, on every push (`.github/workflows/ci.yml`).

---

## Current status

Working end to end: accounts (including mortgages, HELOCs, promos), bills and loan groups, income, payments and history, projections, the dashboard and safe-to-spend, transactions, budgets, goals and sinking funds, bill matching, recurring-charge detection, alerts and the email digest, the optimizer and its recommendations, fees, debt payoff, what-if scenarios, reports, persistence, Excel import/export, backup/restore, SimpleFIN sync (manual or automatic), user accounts with invites, signed-in devices, the activity history, background jobs (backups, upkeep, push notifications), and the installable app.

Known limitations:
- Weekly/bi-weekly items without a start date guess their schedule; set a start date for accuracy.
- Excel export covers accounts, bills, and income — not payment status, transactions, budgets, goals, or settings. Use **Download backup** for a complete copy.
- Bill matching looks at the last 45 days of transactions; older payments can be marked paid by hand.
- The email digest, push notifications, automatic backups and SimpleFIN auto-sync run inside the API server, so they only happen while it's running.
- No HTTPS of its own: on your home network sign-in protects access, but traffic isn't encrypted. Don't expose it to the internet without a reverse proxy that adds HTTPS.

No license has been chosen yet.
