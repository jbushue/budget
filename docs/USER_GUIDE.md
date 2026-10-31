# Budget Manager — Web Interface User Guide

Budget Manager models your real finances — bank accounts, credit cards, loans, bills, and income — and projects them forward day by day. The Dashboard answers two questions at a glance: **can my bills be paid?** and **how much can I spend without going under?** It also tracks your real transactions, budgets, and savings goals, recognizes bill payments in your bank activity, warns you before an account runs dry, and suggests where to move money to pay less interest.

This guide covers every page of the web interface, what each number means, and how it is calculated.

---

## Contents

1. [Getting started](#1-getting-started)
2. [Core concepts](#2-core-concepts)
3. [Dashboard](#3-dashboard)
4. [Accounts](#4-accounts)
5. [Bills & Payments](#5-bills--payments)
6. [Loan Groups](#6-loan-groups-bill-groups)
7. [Income](#7-income)
8. [Transactions](#8-transactions)
9. [Budgets](#9-budgets)
10. [Goals & Sinking Funds](#10-goals--sinking-funds)
11. [Timeline & Projection](#11-timeline--projection)
12. [Payment Optimizer](#12-payment-optimizer)
13. [Debt Payoff Estimator](#13-debt-payoff-estimator)
14. [What-If Scenarios](#14-what-if-scenarios)
15. [Reports](#15-reports)
16. [Alerts](#16-alerts)
17. [Settings](#17-settings)
18. [Using it on your phone, and installing it](#18-using-it-on-your-phone-and-installing-it)
19. [Recommended routine](#19-recommended-routine)
20. [Troubleshooting & FAQ](#20-troubleshooting--faq)

---

## 1. Getting started

### Requirements

- **Python 3.13+** with the packages `flask`, `flask-cors`, `graphene`, `sqlalchemy`, `openpyxl`
- **Node.js 20+** (for the web interface)

### Starting the app

**Windows (easiest):** double-click `start.bat` in the project folder. It:

1. activates `.venv` if it exists,
2. installs missing Python and Node dependencies,
3. opens two windows — the API server (port 4000) and the web UI (port 3000),
4. opens your browser at <http://localhost:3000>.

Close the two command windows to stop the app.

**Manually (any OS):**

```bash
# Terminal 1 — API server
python api_server.py            # http://127.0.0.1:4000

# Terminal 2 — web interface
cd web-ui
npm install                     # first time only
npm run dev                     # http://localhost:3000
```

The web UI forwards all data requests (`/graphql`, `/files`, `/auth`, `/health`) to the API server, so both must be running.

**One window instead of two:** run `npm run build` in `web-ui` once; after that `python api_server.py` serves the web interface itself at <http://localhost:4000>.

### Where your data lives

Everything is stored in a single SQLite file: **`~/.budget_app/finance.db`** (on Windows, `C:\Users\<you>\.budget_app\finance.db`). Every change you make in the UI is saved immediately — there is no "Save" step. **Settings → Data & backup → Download backup** saves a copy of it (§17).

### First-time setup checklist

Work through the pages in this order — each step builds on the previous one:

1. **Accounts** → add your bank(s), then checking/savings accounts, credit cards, HELOCs, and your mortgage with their current balances.
2. **Income** → add each paycheck and (optionally) how it is split between accounts.
3. **Bills** → add recurring bills. Credit card, mortgage, and HELOC payments are created for you automatically.
4. **Loan Groups** → (optional) bundle loans that are paid with a single payment, such as student loans.
5. **Settings → Planning** → set your **cushion** and your **everyday spending** (groceries, gas, eating out — anything that isn't a bill). These drive Safe to spend.
6. **Transactions** → (optional, recommended) download them from SimpleFIN or import a CSV from your bank. Bill payments in them are recognized automatically, and everyday spending can be learned from them.
7. **Dashboard** → check that the status and Safe to spend look right.

### Server options

| Environment variable | Default | Effect |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Address the API listens on. Leave as-is: the web interface reaches the API through its proxy, including from your phone (§18). |
| `BUDGET_DEBUG` | off | Set to `1` for auto-reload and detailed errors while developing. **Never** enable this on a shared network — the debugger allows running code on your machine. |

---

## 2. Core concepts

### Units and formats

- **Money** is in dollars. Balances owed on credit cards, loans, and HELOCs are entered as **positive** numbers (a $1,200 card balance is entered as `1200`).
- **Interest rates** are **annual percentages**: enter `19.99` for 19.99% APR, `4.5` for 4.5% APY.
- **Due days / pay days** are days of the month, `1`–`31`. A day that doesn't exist in a month (e.g. the 31st in April) falls on the **last day of that month**.
- **Dates** are `YYYY-MM-DD`; date fields in the UI use your browser's date picker and default to *your local* today.

### Banks and account types

A **bank** is a container for accounts. Each bank has a type (Traditional, Credit Issuer, Mortgage Lender) — this is a label only.

| Account type | Counts as | Notes |
|---|---|---|
| Checking | Asset | Where bills are paid from and paychecks land by default. |
| Savings | Asset | Earns interest (APY); the optimizer may "sweep" spare cash here. |
| Credit card | Liability | Has a limit, APR, due day, statement day, and optional 0% promos. |
| HELOC | Liability | Home-equity line with a draw period (interest-only minimums) followed by a repayment period. |
| Mortgage | Liability | Fixed-rate home loan with a principal/interest/escrow breakdown. Its monthly payment is calculated for you. |

### Bills, and bills that are created for you

A **bill** is anything you pay on a schedule. There are two kinds you create:

- **Fixed** — same amount every period (rent, subscriptions).
- **Variable** — changes each period (utilities). You enter an *estimate* plus an expected min/max range and can record the actual amount when the statement arrives. Once you record actual amounts, the estimate for future periods tracks your recent history.

And bills the app creates and maintains automatically, shown with an **`[Auto]`** name:

- **`[Auto] <card> Payment`** for every credit card with a balance — the amount is the card's current **minimum payment**.
- **`[Auto] <mortgage> Payment`** — the full monthly payment (principal + interest + escrow).
- **`[Auto] <HELOC> Payment`** — the HELOC's minimum payment (interest-only during the draw period).
- **`[Auto] <group> Payment`** for every loan group — the group's total payment.

These follow their account: change the card's due day and the bill's due day changes; delete the card and the bill disappears. You can't edit their amounts directly — update the underlying account instead.

### Credit card minimum payments

The minimum payment is **2% of the regular (non-promo) balance, or $25, whichever is greater**, **plus** for each active 0% promo, enough to pay that promo balance off before it expires (promo balance ÷ months remaining). This is deliberately conservative: it keeps you from being hit by deferred interest.

### 0% promotional offers and deferred interest

A promo carves out part of the card's existing balance as interest-free until the promo's end date. Interest is only charged on the **regular** balance. If a promo **expires with a balance remaining**, the app charges **deferred (retroactive) interest** as if the promo never existed — `remaining × ((1 + APR/12)^months − 1)` — and the leftover amount becomes regular, interest-bearing debt. Projections apply this on the simulated expiry date, so you can see the hit coming.

### "Paid this period" and the billing cycle

Each bill tracks whether it has been **paid this period**. Marking a bill paid:

- withdraws the money from the chosen source account (or charges a credit card if you pay with one),
- records the payment in the bill's history,
- carries any **underpayment** forward to the next period (shown as "+$X carryover").

Paid bills are **reset automatically** once their next due date passes (this runs each time the API server starts, and on demand with **🔄 Auto-Reset** on the Bills page).

In projections, a bill already marked paid is skipped for the *current* period only — every later period is paid normally. Paying an **overdue** bill counts for the missed due date, so the next one still shows as owed.

**Record only.** If your balances are already up to date (for example, synced with SimpleFIN), the payment has already left your account — taking it out again would count it twice. The Pay / Mark paid dialog has a checkbox, *Take the money out of the account in this app now*; leave it off to just record the payment. It's off by default when you use SimpleFIN. Bill payments recognized in your transactions (§8) are always recorded this way.

### Everyday spending and the cushion

Bills aren't everything you spend. **Everyday spending** — groceries, gas, eating out, the odd purchase — is set in *Settings → Planning* as a weekly amount, or learned from your transactions (the average of the last 8 weeks of spending in "everyday" categories, once there are at least 3 weeks of history). Every projection takes it out of checking a day at a time.

The **cushion** is money you always want left in checking for surprises. Safe to spend never dips into it, and alerts warn you when checking is projected to fall below it.

### Fees

Projections charge the fees you'd really pay: a **late fee** when a payment can't be made on its due date (set app-wide in *Settings → Planning*, for cards/HELOCs and for other bills, and per bill on the bill form), and an **overdraft fee** each time checking would go below $0. Fees show up in the Optimizer and What-If comparisons.

### Payment sources

Every bill, group, mortgage, and HELOC can have a **preferred source** (bank + account). When you mark a payment paid without choosing a source, the preferred source is used. In projections, payments come from the preferred source when it has enough money; otherwise from another checking account that does. If no account can cover a payment, the projection marks it **Deferred** and shows a warning.

### Projections

The **Timeline**, **Dashboard chart**, and **Optimizer** run a day-by-day simulation starting today. Each day, in order: income deposits, optimizer moves that bring money back to checking, bill/loan payments, then other optimizer moves and interest. Interest is applied monthly:

- **Savings/checking:** on the account's *Interest Day* at APY/12 (accounts with no Interest Day don't earn interest).
- **Credit cards:** on the statement day at APR/12 on the regular (non-promo) balance; expired promos trigger deferred interest on their expiry date.
- **HELOCs:** on the payment due day at APR/12, just before that day's payment — so an interest-only payment keeps the balance flat.
- Mortgage payments are split into interest, escrow, then principal.

A day of the month that doesn't exist (e.g. the 31st) uses the last day of that month.

### Schedules for weekly, bi-weekly, and other non-monthly items

Monthly items repeat on their day of the month. Items that repeat every 7 or 14 days, or every few months, need to know *one* real date to count from — the **Start / First Due Date** on bills and **First Pay Date** on income. **Set it** for every weekly, bi-weekly, quarterly, semi-annual, yearly, and one-time item. Without it the app guesses: it counts from the first upcoming occurrence of the item's day of month (and, for yearly/semi-annual bills, its Due Month), which may not line up with your real schedule. One-time items show "-" as their next date once they've passed.

The projection is a **copy** — running it never changes your real balances.

---

## 3. Dashboard

**Route:** `/` · Open it and you know where you stand.

### Status banner — can my bills be paid?

One line, colored by how things look:

| Banner | Means |
|---|---|
| ✅ **All bills through *date* are covered** | Every bill and your everyday spending fit, and checking stays above your cushion. The date is at least a month out (through your second payday). |
| ⚠️ **Bills are covered — if you follow the plan** | Paying everything on its due date leaves a bill short, but the Optimizer's plan (moving money from savings, timing payments) covers it. **See the plan** shows how. |
| ⚠️ **Bills past due and not marked paid** | A due date has passed with no payment recorded. Mark them paid if you've paid them; until then their amount is held back from Safe to spend. |
| ⚠️ **Checking gets tight** | Everything is paid, but checking drops below your cushion. |
| 🚨 ***Bill* can't be paid on *date*** | Even the optimized plan comes up short. **See the plan** for ways to cover it. |
| 🚨 **Checking goes negative** | Everyday spending would overdraw checking before the next paycheck. |

### 💵 Safe to spend — how much can I spend?

The extra you can spend **on top of** your usual everyday spending without missing a bill or dipping into your cushion:

```
Safe to spend = lowest projected checking balance, through your second payday
                (after every bill on its due date and your everyday spending)
              − your cushion
              − overdue bills not marked paid
              − bills that can't be covered
              − money set aside in checking for goals
```

It's the *lowest* point that matters, not a total: a dollar spent today lowers every later day's balance too. Below it, **$/day** spreads it over the days until your next paycheck. *How this is worked out* shows each line. If everyday spending isn't set, a warning says so — the number would assume you spend nothing besides bills.

### 🧾 Bills before your next paycheck

A checklist of what's due this pay period (plus anything overdue), each with a status:

| Badge | Means |
|---|---|
| **Paid** | Marked paid for this due date. |
| **Covered** | There will be enough on the due date. |
| **Covered with plan** | Covered if you follow the Optimizer's plan. |
| **Short $X** | There won't be enough; X is how much is missing. |
| **Overdue** | The due date passed with no payment recorded. |

**Mark paid** opens a quick dialog (amount, date, account, and whether to take the money out in the app — see "Record only" in §2). Your next paychecks are listed underneath.

### 🔗 Bill payments found in your transactions

When imported transactions look like bill payments but aren't certain enough to record automatically, they're listed here: **Yes, it's *bill*** records the payment (no money moves), **Not a bill** stops suggesting it. See §8.

### 🧭 What to do next

The three most important recommendations for the next 30 days, from the same analysis as the Payment Optimizer (§12). They're ranked: 🚨 urgent (a bill that can't be paid), ⚠️ warnings, then 💡 money-saving moves, then 📈 tips. **See the full payment plan →** opens the Optimizer.

### Details

Below the summary:

- **Total Assets / Total Liabilities / Net Worth / Banks** – checking + savings; card, mortgage and HELOC balances; the difference (home value isn't included).
- **Banks & Accounts** – every account grouped by bank. Debts are shown as negative. 🔄 marks accounts kept in sync by SimpleFIN.
- **Upcoming Bills (30 days)** and **Upcoming Income (30 days)**.
- **📈 Net Worth Over Time** – from daily snapshots (recorded at server start and the first Dashboard visit each day); appears after two days of history.
- **90-Day Balance Projection** – checking + savings over the next 90 days (the optimized projection, §12).
- **💳 Recent Bill Payments** – the latest payments recorded.

The 🔔 bell at the top right of every page lists alerts (§16). **Refresh** reloads everything.

---

## 4. Accounts

**Route:** `/accounts` · Create and maintain banks and accounts, and keep balances current.

### Adding a bank — **+ Bank**

| Field | Notes |
|---|---|
| Bank Name | Required, must be unique. |
| Type | Traditional (default) / Credit Issuer / Mortgage Lender. Informational. |

**Delete Bank** removes the bank and *all* of its accounts (and their auto-bills) after confirmation.

### Adding an account — **+ Account**

| Field | Applies to | Notes |
|---|---|---|
| Bank | all | Required. |
| Account Name | all | Required; unique within the bank. |
| Account Type | all | Checking, Savings, Credit Card, HELOC, or Mortgage. |
| Starting Balance / Current Balance (owed) | all | For cards, HELOCs, and mortgages this is the amount **owed**. For a mortgage it's the current principal; leave it blank (0) for a brand-new loan to use the original amount. |
| APY % / APR % | all | Annual percentage. |
| Interest Day (1-31, optional) | checking, savings | Day of month interest is credited. Leave blank if the account earns no interest. |
| Credit Limit | credit card, HELOC | Required and must be greater than 0. |
| Payment Due Day (1-31) | credit card, HELOC | Sets the due day of the card's `[Auto]` payment bill. |
| Statement Day (1-31, optional) | credit card | Day interest is charged each month. |
| Draw Period (years) | HELOC | Default 15. During the draw period you can borrow and minimums are interest-only. |
| Total Term (years) | HELOC | Default 30. Includes the draw period; the remainder is the repayment period (principal + interest). |
| HELOC Start Date | HELOC | Optional; defaults to today. |
| Original Loan Amount | mortgage | Required. The amount originally borrowed. |
| Loan Term (years) | mortgage | Default 30. |
| Loan Start Date (optional) | mortgage | When the loan began; for your records (defaults to today). |
| Payment Due Day (1-31) | mortgage | Default 1. Sets the due day of the `[Auto]` mortgage payment bill. |
| Monthly Escrow (optional) | mortgage | Property tax, homeowners insurance, PMI, HOA, and other amounts collected with each payment. |
| Home Market Value (optional) | mortgage | Used to calculate equity (value − principal). |
| Pay From (optional) | mortgage | Preferred bank and account for the payment. Choose both or leave both on Auto. |

For a mortgage, the form shows the **estimated monthly payment** as you type: the standard fixed-rate payment on the original amount over the full term (principal & interest), plus escrow. This is the amount of the `[Auto]` mortgage payment bill.

If anything is wrong (duplicate name, missing limit, invalid day…), you'll see an alert explaining why and nothing is created.

### Bank Accounts table

Columns: **Account** (🔄 SimpleFIN tag if synced), **Type**, **APY**, **Interest Day**, **Balance**.

Actions:

- **Update** – type in the real current balance (e.g. from your banking app). The change is saved and logged.
- **Hist** – balance history: date, previous, new, and change for each update.
- **Txns** – recent transactions pulled from SimpleFIN (synced accounts only, read-only).
- **Del** – delete the account.

### Credit Accounts table

Columns: **Account** (🏷️ N = number of promos), **Status** (active / closed / frozen), **APR**, **Due Day**, **Balance**, **Limit**, **Utilization** (balance ÷ limit; green ≤ 50%, amber ≤ 80%, red above).

Actions: **Update** (new balance owed), **Hist**, **Txns**, **Promos**, **→ HELOC**, **Del**.

#### Promo Offers

The **Promos** dialog shows the card's total and regular (interest-bearing) balance and lists its promos: name, months, promo balance, status (Active / Expired, with an "N d left" badge in the final 30 days), and expiry date.

**+ Add Promo** fields:

| Field | Notes |
|---|---|
| Promo Name | Required, unique per card. |
| Months Interest-Free | Required (default 12). |
| Purchase Limit (optional) | Cap on purchases that qualify. |
| Promo Balance | The portion of the card's **existing** balance that is on this promo. It is moved out of the regular balance — it does not add to the total. |
| Start Date | When the promo began. |
| End Date (optional) | Calculated from start + months if blank. |

**Edit** changes a promo's balance; **Del** removes the promo and returns its balance to the regular balance.

#### Convert to HELOC (**→ HELOC**)

Replaces a credit card with a HELOC, keeping its balance, APR, credit limit, and due day. You choose the draw period, total term (must be longer than the draw period), start date, and optionally a new name. The card's payment bill is replaced by the HELOC's.

### Mortgage Accounts table

Columns: **Status**, **APR**, **Due Day**, **Principal**, **Monthly Payment** (P&I + escrow), **P & I** (this month's principal/interest split), **Escrow** (monthly taxes, insurance, PMI, HOA).

Actions: **Update** (set the current principal), **Hist**, **Txns**, **Del**. Mortgage payments are made from the Bills page.

### HELOC Accounts table

Columns: **Phase** (draw / repayment / paid_off), **APR**, **Due Day**, **Balance**, **Limit**, **Available** (draw phase only), **Min Payment** ("interest only" in the draw phase, "P+I" in repayment), **Draw Ends**.

Actions: **Update**, **Hist**, **Txns**, **Del**.

---

## 5. Bills & Payments

**Route:** `/bills` · Everything you pay, in one table, and where you record payments.

### The table

Rows include regular bills, credit card payments (cards with a balance that aren't in a loan group), mortgage and HELOC payments, and loan groups. Unpaid items are listed first, then by due day.

| Column | Meaning |
|---|---|
| Status | **DUE** or **PAID** (paid card rows also show the amount and date). |
| Name | Bill name; card/mortgage/HELOC rows show "Bank · Account". |
| Type | Fixed, Variable, 💳 Credit, 🏠 Mortgage, 🏦 HELOC, 🎓 Group. |
| Frequency / Due Day | Schedule. |
| Amount | Amount due this period, **including carryover**. Card rows show the minimum payment with the full balance underneath. |
| Details | Card: utilization + APR · Group: member count + total balance · Mortgage: principal + APR · HELOC: balance + phase · Bill: carryover, or the actual amount / expected range for Variable bills. |
| Source | Preferred payment source, or "Auto". |

**Filter chips** across the top: All, Fixed, Variable, 💳 Credit, 🎓 Groups, 🏠 Mortgage, 🏦 HELOC, Unpaid, Paid. The footer totals the visible rows.

**Summary cards:**

- **Est. Monthly Obligations** – every item converted to a monthly amount (weekly × 4.33, bi-weekly × 2.17, quarterly ÷ 3, semi-annual ÷ 6, yearly ÷ 12, one-time excluded).
- **Paid This Period** – paid items / total items.
- **Est. Annual Obligations** – monthly × 12.

### Adding a bill — **+ Add Bill**

| Field | Notes |
|---|---|
| Bill Name | Required, unique. |
| Bill Type | **Fixed** or **Variable**. |
| Amount | Fixed: the amount. Variable: your *estimate*. |
| Min Amount / Max Amount | Variable only: the expected range. |
| Due Day (1-31) | Day of month it's due (for weekly/bi-weekly bills, see Start date). |
| Frequency | Monthly, Weekly, Bi-weekly, Quarterly, Semi-annual, Yearly, One-time. |
| Due Month (1-12) | Yearly / Semi-annual: which month it's due (semi-annual repeats six months later). |
| Start / First Due Date (optional) | For weekly, bi-weekly, quarterly, semi-annual, yearly, and one-time bills: the date of one actual occurrence. The schedule repeats from this date (every 7 / 14 days, every 3 / 6 / 12 months, or just once). Set this for accurate weekly and bi-weekly projections. |
| Late fee (optional) | What's charged if it's paid late. Blank uses the default from *Settings → Planning*. |
| Preferred Source Bank / Account (optional) | Where it's normally paid from. "Auto" lets the app choose. |

**Edit** lets you change everything except the name and type. Choosing "Auto (no preference)" clears the preferred source.

### Row actions

| Action | Shown for | What it does |
|---|---|---|
| **Pay** | unpaid bills, cards, mortgages, HELOCs, groups | Opens the payment dialog (below). |
| **$** | unpaid Variable bills | **Set Actual Amount** – record this period's real amount (shows the expected range). |
| **Reset** | paid items | Marks it unpaid again (e.g. you recorded a payment by mistake — note this does *not* refund the money; use Accounts → Update to correct balances). |
| **Edit** / **Del** | regular bills | Edit or delete the bill. |
| **Details →** | groups | Opens Loan Groups. |

### The Pay dialog

| Field | Default |
|---|---|
| Amount Paid | The amount due (bills: amount + carryover; cards: the minimum payment). |
| Source Bank / Account | The preferred source (cards: the first checking account if none). Credit cards are listed as "(credit card)" — paying with a card **charges** that card. |
| Payment Date | Today. |
| Take the money out of the account in this app now | On, unless you use SimpleFIN. Turn it off when your balances already include this payment ("Record only", §2) — then only the paid status and history change. |

On confirm (with money taken out):

- the money leaves the source account (rejected with a message if funds or credit are insufficient — nothing changes),
- **bills:** the bill is marked paid; paying less than due shows "$X will carry over to next period",
- **credit cards:** the card balance drops by the amount paid,
- **mortgages:** the payment is split into interest, escrow, then principal,
- **HELOCs:** the balance drops by the amount paid,
- **groups:** the payment is distributed across the group's loans (see §6),
- the payment is recorded and appears in **Recent Bill Payments** on the Dashboard.

### 🔄 Auto-Reset

Marks paid items unpaid when their next due date (after the last payment) has arrived. This also runs automatically every time the server starts, so you normally don't need it.

### 🔁 Repeating charges that aren't bills yet

When your transactions show the same payee charging you on a steady schedule (weekly, every two weeks, monthly, quarterly, or yearly) with similar amounts, and it isn't a bill yet, it's listed at the top of the Bills page with how often, the typical amount (and range, if it varies), and when it's next expected. **Add as bill** creates it (fixed, or variable if the amount moves around) so projections and Safe to spend account for it; **Dismiss** hides the suggestion for good.

---

## 6. Loan Groups (Bill Groups)

**Route:** `/bill-groups` · Bundle several loans that you pay with **one** payment — typically federal student loans serviced together.

When a card or loan is in a group, it no longer gets its own payment row; the group appears as a single payment instead, everywhere (Bills, Timeline, Optimizer, Debt Payoff).

### Group cards

Each group shows its type icon (🎓 Student Loan, 📦 Bundled Bill, 🏦 Consolidated Loan, 📋 Other), frequency, PAID/DUE status, **Monthly Payment**, **Total Balance** (sum of members), **Sub-Loans** count, **Due Date**, and payment source.

The members table lists each loan's bank, account, APR, balance, allocation method, and **Est. Payment** — how much of the group payment goes to that loan.

### How a group payment is split (allocation)

1. Members with **Fixed amount** get their fixed amount first (scaled down proportionally if the fixed amounts add up to more than the payment).
2. The rest is split among the other members — **Proportional** members by their share of the balance, **Equal** members evenly (members with a $0 balance are skipped).
3. A loan never receives more than it owes; any excess goes to the other members.

### Actions

- **+ New Group** / **Edit**: Group Name (unique), Total Monthly Payment, Due Day, Frequency (Monthly / Bi-weekly / Quarterly), Group Type, Payment Source Bank/Account.
- **+ Member**: pick a bank, then a credit/loan account (each account can be in only one group), and an Allocation Method (Proportional / Equal split / Fixed amount + amount).
- **Remove** a member, or **Delete** the group (its loans go back to having individual payments).
- **Mark Paid**: opens the pay dialog (amount, source, date). The money leaves the source and is split across the loans as described above.

---

## 7. Income

**Route:** `/income` · Your paychecks and other recurring income.

### Table

**Source**, **Frequency**, **Pay Dates**, **Next Pay Date** (a pay date that lands on a weekend moves to the Friday before), **Amount**, **Est. Monthly** (weekly × 4.33, bi-weekly × 2.17, semi-monthly × 2, bi-monthly ÷ 2, quarterly ÷ 3, yearly ÷ 12, one-time excluded), and **Distribution**. Summary cards show estimated monthly and annual income and the number of sources.

### Adding income — **+ Add Income**

| Field | Notes |
|---|---|
| Source Name | Required, unique. |
| Amount (per pay period) | The take-home amount of *one* paycheck. Must be > 0. |
| Frequency | Monthly, Semi-monthly, Bi-weekly, Weekly, Bi-monthly, Quarterly, Yearly, One-time. |
| Pay Day / First & Second Pay Day | **Monthly** and **Semi-monthly** only: day(s) of the month you're paid (e.g. 15 and 31). |
| First Pay Date (optional) | **Weekly, Bi-weekly, Bi-monthly, Quarterly, Yearly, One-time**: the date of any actual paycheck. Pay dates repeat from it (every 7 or 14 days, every 2 / 3 / 12 months, or just once for one-time). Set this so bi-weekly paychecks land on the right Fridays — including the two months a year with three paychecks. |

### Distribution — **Dist**

Controls which accounts a paycheck lands in. Add one row per account (checking/savings only):

- **Amount** – a fixed dollar amount sent to that account each paycheck.
- **Blank** – "remainder": everything left over. Only one account may be the remainder.

Example: $500 → Savings, blank → Checking. With no distribution set, the whole paycheck goes to the first checking account.

---

## 8. Transactions

**Route:** `/transactions` · Your real bank and card activity. Transactions power budgets, reports, the learned everyday spending, and automatic bill matching. Adding them never changes account balances.

### Getting transactions in

- **⟳ Download from SimpleFIN** (when SimpleFIN is connected) – fetches the last 90 days for every mapped account. Run it again any time; transactions already downloaded are skipped.
- **⬆ Import CSV** – download a CSV from your bank's website (usually "Download" or "Export" on the account activity page), pick which account it belongs to, and choose the file. The date, description, and amount columns are detected for you — or pick them yourself, including files with separate *money out* / *money in* columns. Check the preview: money spent should show with a "−"; if it doesn't, tick *Purchases show as positive numbers*. Re-importing the same file skips what's already there.
- **+ Add** – enter one by hand.

### Categories

Every transaction gets a category automatically: your own rules first, then a built-in list of common merchants (Kroger → Groceries, Shell → Gas & Transport, Netflix → Entertainment, …). Change one with the category dropdown in its row. With **Remember category choices for similar transactions** ticked, a rule is added at the same time, so future transactions from that payee (and existing uncategorized ones) get the same category. ⚠ **Uncategorized** in the filter shows what still needs a category.

Filter by text, category, account, and date range; the totals above the table (in / out) cover everything that matches, not just the rows shown.

### Bill payments in your transactions

After every import, outgoing transactions are compared with your bills. A transaction matches a bill when it's within 10 days before to 7 days after a due date and the amount fits:

- **Certain** – the amount fits *and* the description names the bill (or it's the same payee as an earlier confirmed payment). With *Mark bills paid automatically* on (Settings → Alerts), these are recorded right away.
- **Likely** – the exact amount near the due date, but the description doesn't say. These are listed under **🔗 Bill payments found in your transactions** (here and on the Dashboard) for you to confirm or dismiss.

Recording a match marks the bill paid **without moving money** — the payment already happened and your balances already reflect it. Matched transactions show a ✓ badge with the bill name; **undo** removes the match and the payment it recorded.

The **🔁 Repeating charges** list (also on the Bills page, §5) appears at the bottom.

---

## 9. Budgets

**Route:** `/budgets` · Spending by category for a month, against the budgets you set. Use ‹ › or the month picker to look at other months.

- **Summary cards** – spending in budgeted categories vs. the total budgeted, all spending and income, your **learned everyday spending** (weekly, from the last 8 weeks), and how much is still uncategorized (with a link to fix it).
- **Category lines** – spent vs. budget with a progress bar. **On pace** compares how fast you're spending with how far through the month you are: "$X left — on pace for $Y" (amber) means you'll go over at this rate; red means you're already over. Refunds reduce spending. **Set budget / Change** edits a budget (blank or 0 removes it).
- **Categories** – add, rename (transactions and rules follow), recolor, or delete. Each has a type: **Expense**, **Income**, or **Transfer** (moving money between your own accounts — ignored in spending). **Everyday** marks expense categories that aren't covered by bills; these make up the learned everyday spending.
- **Auto-categorize rules** – "description contains *text* → category". Your rules win over the built-in list. **Re-run on uncategorized** applies all rules to transactions that don't have a category yet.

---

## 10. Goals & Sinking Funds

**Route:** `/goals` · Money you're setting aside for something.

A goal has a target amount, an optional target date, and the account the money is kept in. **+ Set aside** records money you've put toward it, **− Use** records spending it; nothing moves between accounts (do that yourself if you want the money in a different account).

- **Main checking / a checking account** – the money set aside is **reserved**: it's subtracted from Safe to spend on the Dashboard, so you don't spend it by accident.
- **A savings account** – it's already out of the way, so it isn't subtracted again.

With a target date, each goal shows what's left, what to set aside **per month** and **per paycheck** to get there, and whether you're **On track** or **Behind** (saved at least as much as the time elapsed since you created it would suggest).

### Sinking funds

Bills that aren't paid monthly (quarterly, semi-annual, yearly) are listed under **💡 Bills that need saving up for**, with what to set aside per month. **Create sinking fund** makes a goal for the bill's amount, due on its next due date. Once that bill has been paid, the fund is used up and moves to the following due date automatically.

---

## 11. Timeline & Projection

**Route:** `/timeline` · A day-by-day forecast of every account.

Choose the period (30, 60, 90, 180 days, or 1 year) and **Refresh**. The forecast is the **optimized** projection — it includes the money moves recommended by the Optimizer (see §12).

### Stat cards

| Card | Meaning |
|---|---|
| Total Income | All paychecks in the period. |
| Total Expenses | All bill, card, mortgage, HELOC, group, extra, and promo payments. |
| Net Change | Change in your total cash (checking + savings) from today to the end of the period. This can be negative even when income exceeds expenses: when the optimizer parks spare cash in a HELOC (see §12), cash goes down but your HELOC debt goes down by the same amount. |
| Projected Net Worth | Final cash − card, mortgage, and HELOC balances (with assets/debt shown underneath). |

### Balance Over Time chart

**Net Balance** (filled), **Cash (Checking/Savings)** (dashed), and **Total Debt** (shown below zero). Tick **Per-account lines** to add a line for each bank account, card, and HELOC.

### Projected Final Balances

Every account's balance at the end of the period, grouped by type, with a Net Worth total.

### 📅 Financial Calendar

A month grid with ← / → navigation. Each day shows colored dots — **green** income, **red** payments, **blue** optimizer transfers, **amber** deferred payments — and today is outlined. Click a day to see:

- **Transactions** – each event with its source account and amount. A deferred payment shows "⚠️ Insufficient funds — payment deferred": the projection found no account able to cover it that day.
- **Expected Account Balances (End of Day)** – every account after that day's events, plus the net total.

---

## 12. Payment Optimizer

**Route:** `/optimizer` · Answers *"what's the best way to get every bill paid?"* for the chosen period (30 days – 1 year, pick it top-right and click **Analyze**). It compares two versions of the same period and explains the difference in plain language:

- **On due date**: every bill comes out of its usual account on the day it's due, and nothing else moves.
- **Optimized**: the same bills, plus the optimizer's routing and transfers (below).

Nothing is changed: it's advice. The Timeline and the Dashboard chart already assume the optimized plan.

### What the optimizer does

- **Savings sweeps** – parks spare checking money in savings (to earn interest) and **recalls** it before bills need it. Money stays parked for at least 7 days.
- **HELOC parking** – if you have a HELOC in its draw period, temporarily pays it down with spare cash (cutting interest) and draws it back before bills are due.
- **Extra credit payments** – only when the optimizer is set to a "pay off a specific card" goal, which is currently available through the Python API/CLI, not the web UI. In the web UI the goal is always "maximize discretionary funds", so this tile normally stays empty.
- **Promo payoffs** – schedules payments so 0% promo balances are cleared *before* they expire and trigger deferred interest.

It always keeps enough in checking to cover upcoming payments.

### The page, top to bottom

**Headline**: one sentence on where you stand, for example *"All 11 upcoming payments are covered on time. Following the optimized plan leaves you $86.52 better off over 90 days."* or *"1 payment can't be covered as things stand: the first is Roof on Oct 28."* Below it is a bullet list of what the plan changes. The left border is red if something is urgent, amber for warnings, and green otherwise.

**⚖️ Paying on due dates vs. the optimized plan**: a side-by-side table. The **Difference** column is green when the plan is better and red when it's worse.

| Row | Meaning |
|---|---|
| Late or missed payments | Bills there isn't enough money for on their due date. |
| Lowest checking balance | Your tightest point in the period, with the account and date. The plan often lowers this on purpose: it puts idle cash to work, but always keeps a buffer (about $300). |
| Cash at the end / Debt at the end | Bank balances / cards + loans + HELOC + mortgage at the end of the period. |
| Interest charged / earned | On cards and HELOCs / on savings and checking. |
| Late & overdraft fees | Shown when either plan would pay any (rates from Settings → Planning and each bill's late fee). |
| Deferred promo interest at risk | Shown only when a 0% promo still has money owed at the end. It's the most that could be charged if that balance isn't paid before the promo expires. It's a risk, not a certain cost, so it isn't part of the bottom line. |
| **Overall (cash − debt)** | **The bottom line.** Moving cash onto a debt lowers both cash and debt, so judge the plan by this row. |

> The plan can occasionally come out a few dollars *worse* in a short window. For example, paying a 0% promo early leaves more of the 24% balance in place for a while. The page reports this honestly; the promo table shows what it protects you from.

**🧭 Recommendations**: a ranked list of cards with a dollar badge (**saves $X** is money gained or avoided; **risk $X** is money at risk):

| | Kind | Example |
|---|---|---|
| 🚨 | Urgent | A bill that can't be paid on its due date, how short you are, and how to fix it. Also a loan group whose payment doesn't cover its interest. |
| ⚠️ | Warning | A bill that's only on time if you follow the plan; checking getting thin (under $100); a promo the plan can't clear in time. |
| 💡 | Saves money | Pay interest-bearing debts on payday; point a loan group at its highest-rate loan; let idle cash work between paychecks. |
| 📈 | Tip | An extra $50/month on a loan group; plan ahead for a promo that expires after this period. |
| ✅ | Good | A promo that's on track; *"Every bill is covered on time."* |

**🗓️ When to pay each bill**: every payment due in the next 45 days, plus any late payment later in the period. Tick **Only show bills that need attention** to hide the routine ones.

| Column | Meaning |
|---|---|
| Due / Bill | Due date, name, kind (bill, variable bill, card payment, mortgage, HELOC payment, loan group) and the account it comes from. `~` marks an estimated amount. |
| Status | **On time**, **Paid** (already paid this period), **Short** (not enough money on the due date), or **On time with plan** (short if paid on the due date, fine if you follow the optimized plan). |
| Pay early? | What paying on the paycheck before the due date would save, e.g. *"Saves $4.37 on Nov 6 (12d early)"*. Otherwise **No benefit**. |
| What to do | Plain advice, including which paycheck covers the bill. For a **Short** bill it lists ways to fix it. |

How "pay early?" is worked out:

- **Regular bills** (rent, utilities, subscriptions): paying early never saves money; it only shrinks your cushion. Pay on the due date.
- **Credit cards, HELOCs and loan groups**: interest builds daily, so paying on payday instead of the due date saves about *amount × APR ÷ 365 × days early*. This assumes you carry a balance. A card paid in full each month already pays no interest. Savings under 50¢ are shown as "pennies".
- The early payment is only recommended if the paying account stays above $0 until the due date. If it wouldn't, the advice says so and tells you to pay on the due date.
- **Mortgage**: interest is calculated monthly, so paying earlier in the month doesn't help. Only extra principal does (see Accounts → Mortgage).

Fixes offered for a **Short** bill:

- move the gap from another account (e.g. savings);
- charge it to a card with enough available credit (regular bills only);
- draw the gap from a HELOC;
- or wait for the next paycheck, with how many days late that would be.

Late payments can bring late fees, and loans or cards 30+ days late can hurt your credit.

**📦 Loan group cards** (one per group): how the next group payment is split across its loans (balance, APR, monthly interest, share of the payment). Next to that, a comparison of three choices: payoff time and total interest.

- **Keep the current split**: your group's allocation settings.
- **Send extra to the highest rate first**: each loan gets its interest covered and everything else goes to the highest-APR loan. If this saves money, the card tells you the **Fixed** amount to set on the Bill Groups page for that loan. Your servicer also has to apply payments that way, so ask them.
- **Pay $50 more each month**: with the current split.

If the group payment doesn't even cover the monthly interest, the card says the balance will grow.

**🏷️ 0% promo deadlines**: each promo's balance, expiry date, monthly amount needed to clear it in time, and the deferred interest at stake if it isn't. Status is **On track** (the plan clears it), **Short $X**, or **After this window** (expires later and isn't fully scheduled yet: plan ahead).

**🔁 What the optimized plan does**: summary tiles for each kind of move (total, count, and why), then every move with its date and amount. If there are none: *"paying each bill on its due date is already the best plan for this period."*

**🔧 Optimizer checks** (collapsed): the optimizer's raw technical messages (❌ problems, ⚠ warnings, ⓘ notes) for anyone who wants the detail.

---

## 13. Debt Payoff Estimator

**Route:** `/debt-payoff` · Compares three ways to pay off your debts.

Drag **Extra Monthly Payment** ($0 – $2,000, in $25 steps; default $200) — results update half a second after you stop.

**Debts included:** credit cards with a balance (not in a group), HELOCs with a balance, and each loan group as one debt (balance-weighted APR, group payment as its minimum). Mortgages are excluded. Debts already marked paid this period are left out.

**Every strategy uses the same monthly budget** = sum of all minimums + the extra amount. When a debt is paid off, its minimum rolls into the next target.

| Strategy | Extra money goes to |
|---|---|
| 💤 Minimum Only | Nowhere — minimums only (the extra amount is not used). |
| 🏔️ Avalanche | The highest-APR debt first — usually the least interest. |
| ⛄ Snowball | The smallest balance first — quickest wins. |

Each card shows months to payoff, total interest, total paid, savings vs. minimum-only, and the payoff order. If a strategy **never pays off** at that budget (minimums barely cover interest), it says so and shows the balance remaining at the 10-year limit.

The **Remaining Debt Over Time** chart plots all three strategies by month.

---

## 14. What-If Scenarios

**Route:** `/scenarios` · Test a change before you make it. Nothing you do here is saved.

### Building a scenario (left panel)

- **Quick Presets** (each replaces the current changes):
  - **Job Loss** – sets the chosen income to $0.
  - **10% Raise** – raises the chosen income by 10%.
  - **New $200 Bill** – adds a $200 monthly bill due on the 15th.
  - **Cut Bills 20%** – reduces every regular bill by 20%.
- **Projection Period** – 30 days to 1 year.
- **Add Bill** – name, amount, due day (monthly).
- **Remove Payments** – drop a bill, card, mortgage, HELOC, or loan group (cards/HELOCs/mortgages are treated as paid off).
- **Adjust Income** – set a source's amount (0 = no income).
- **Remove Income** – drop an income source.

The **Modifications** list shows every change; click × to undo one. **Run Scenario** calculates; **Reset** clears everything.

### Results (right panel)

- **Verdict**: a one-line answer with a colored border.
  - **Red**: *"2 bills couldn't be paid on time in this scenario"*, or *"Checking would be overdrawn"*.
  - **Green**: *"You'd be $X better off"*.
  - **Amber**: *"Every bill still gets paid, but you'd be $X worse off"*.
- **What changes**: plain-language bullets on how the scenario differs from your current plan. They cover being better or worse off, more or fewer late payments, how far your lowest checking balance moves (and when), and interest charged and earned.
- **Comparison table**, current plan vs. scenario: late or missed payments, lowest checking balance, cash and debt at the end, interest charged, late & overdraft fees, and **Overall (cash − debt)**. Green means better and red means worse.
- **Payments that would be late or missed**: the specific bills and dates the scenario breaks.
- A **chart** of both projections day by day.

> The what-if comparison uses the plain (non-optimized) simulation for both sides so the difference reflects only your changes. Its baseline can therefore differ slightly from the Timeline, which includes optimizer moves.

---

## 15. Reports

**Route:** `/reports` · Built from your transactions. Choose 3, 6, or 12 months.

- **Averages** – monthly income, spending, and what's left over (full months only, starting from your first month with transactions).
- **Income vs. spending** – a bar per month. Transfers between your own accounts aren't counted; the current month is partial.
- **Where the money went** – a chart and table of spending by category for the month you pick, compared with your average for each category (▲ / ▼).
- **Category trends** – each category month by month.
- **Net worth** – from the daily snapshots, once there are at least two.

---

## 16. Alerts

The **🔔** at the top right of every page counts what needs attention (red when something is urgent). Click it for the list; click an alert to go to the page that deals with it.

| Alert | When |
|---|---|
| 🚨 *Bill* is overdue | Its due date passed with no payment recorded. |
| 🚨 Not enough to pay *bill* | It can't be covered on its due date. |
| ℹ️ *Bill* due today / tomorrow / *day* | It's due within the number of days you choose (Settings → Alerts; default 3). |
| ⚠️ / 🚨 Checking dips below your cushion / goes negative | Projected low point, if *Warn when checking is projected to dip below the cushion* is on. |
| ⚠️ *Category* is over budget · ℹ️ on pace to go over | From this month's budgets. |
| ℹ️ *N* bill payments to review | Likely matches waiting for you (§8). |

**Snooze** hides an alert for a day; **Dismiss** hides it until the situation changes (a new due date, a different amount, …). The list refreshes every 5 minutes and when you come back to the tab.

**Browser notifications** (Settings → Alerts) pop up urgent and warning alerts once each, while the app is open in a tab. Your browser asks for permission the first time.

**Daily email digest** (Settings → Alerts) – a morning email with the status, Safe to spend, alerts, and this pay period's bills. It needs an email account's SMTP settings; it's sent after 7am by the running API server, so the app has to be running.

---

## 17. Settings

**Route:** `/settings`

### 🎨 Appearance

Pick **Light**, **Dark**, or **Match device** (follows your phone or computer's light / dark setting, and switches when it does). The choice is saved on each device, so your phone and computer can differ.

### 🧮 Planning

| Setting | What it does |
|---|---|
| Cushion to keep in checking | Safe to spend never dips into it; alerts warn when checking is projected to fall below it. Default $200. |
| Everyday spending comes from | The checking account groceries, gas, etc. are paid from (default: your main checking). |
| Everyday spending | **I'll enter a weekly amount**, or **Learn it from my transactions** (average of the last 8 weeks in "everyday" categories; until there are 3 weeks of history the weekly amount is used). |
| Weekly everyday spending | Your weekly amount (shown per day and per month too). |
| Card / HELOC late fee, Other bills' late fee, Overdraft fee | The fees projections charge (§2). Each bill can have its own late fee. |

### 🔔 Alerts, matching & email

- **Remind me about bills this many days ahead** (0–30).
- **Warn when checking is projected to dip below the cushion.**
- **Mark bills paid automatically when a transaction clearly matches** (§8). Off = every match waits for you to confirm.
- **Browser notifications for urgent alerts.**
- **Daily email digest** – *Send to*, the SMTP server, port, username, and password (for Gmail: `smtp.gmail.com`, port 587, your address, and an *app password*). The password is stored but never shown again. **Send a test digest now** saves and sends one immediately; **Preview digest** shows today's text.

### 💾 Data & backup

- **⬇ Export to Excel** – accounts, bills, income, promos, and loan groups in a spreadsheet that can be imported back.
- **⬇ Blank template** / **⬆ Import from Excel** – fill in the template (example rows marked `EXAMPLE` are skipped) and import it. Importing only adds new items; anything with the same name is skipped.
- **⬇ Transactions (CSV)** – every transaction with its category and matched bill.
- **⬇ Download backup** – a complete copy of the database (everything, including transactions, budgets, goals, and settings). Keep one somewhere safe.
- **⬆ Restore from backup** – replaces **all** current data with a backup file. A copy of the current data is saved to `~/.budget_app/backups/` first.

### 🔒 Your account

Everyone signs in with their own username and password, on every device (this computer included), and stays signed in for 30 days on each. Everyone with an account sees and edits the **same** budget.

- **Change password** needs your current password and signs you out on your other devices.
- **Sign out** (here, or at the bottom of the menu) signs out this browser.

### 👥 Users (admins only)

- **Invite someone** – click **Create invite link** and send the link to the person. It works once, for 1, 7 or 30 days; tick *Make them an admin* if they should be able to manage accounts too. Opening the link shows a form where they choose a username and password. The link is shown only once — if it gets lost, **Revoke** it under *Unused links* and make another.
- **Reset password** – for someone who forgot theirs: makes a one-time link (good for 2 days) where they choose a new password. It signs them out everywhere.
- **Make admin / Remove admin**, **Delete** – there's always at least one admin, and you can't delete yourself. Deleting an account doesn't touch the budget.

Admins can also back up and restore the database (*Data & backup*). A backup includes the user accounts, so restoring an older one brings back the accounts from that time.

### 🔗 SimpleFIN Bridge (automatic balance sync)

[SimpleFIN Bridge](https://bridge.simplefin.org) is a read-only service that connects to your bank and lets this app fetch balances and transactions.

1. Create a connection at bridge.simplefin.org and copy the **Setup Token**.
2. Paste it into **Setup Token** and click **Connect**. (Tokens are single-use.)
3. In **Account Mapping**, pick the local bank and account for each SimpleFIN account and click **Map**. The type (bank / credit / mortgage / heloc) is filled in automatically.
4. Click **🔄 Sync Balances Now** whenever you want fresh balances. The result lists each account's change.

Mapped accounts show 🔄 across the app and get a **Txns** button on the Accounts page. **✕** unmaps an account; **Disconnect** removes the connection and all mappings. Only mapped accounts are updated. To store transactions (for budgets, reports, and bill matching), use **Download from SimpleFIN** on the Transactions page (§8).

### Database

- **Save to Database** – writes everything to disk. Normally unnecessary (every change is saved automatically).
- **Load from Database** – reloads from disk, discarding anything not yet saved.

### API Connection

Shows whether the web UI can reach the API server, plus counts of banks, bills, and income sources. **Check Status** re-tests.

### About

The API endpoint and a link to the **GraphQL Playground**, an interactive console for the API (useful for developers).

---

## 18. Using it on your phone, and installing it

**From your phone or another computer on your network:**

1. The first time you open the app on the computer that runs it, create your account — it's the admin. (Until it exists, the app only answers this computer; anyone else on your Wi-Fi sees a message saying it isn't set up yet.)
2. Find that computer's network address (on Windows: `ipconfig`, look for *IPv4 Address*, e.g. `192.168.1.20`).
3. On your phone, open `http://192.168.1.20:3000` and sign in.
4. To add someone else, create an invite link in *Settings → Users* (§17). Invite links use the address you're on, so create them from the network address (not `localhost`) if the link is for another device.

**Installing it as an app:** in Chrome or Edge, use *Install app* (in the address bar or menu); on iPhone, *Share → Add to Home Screen*. It opens in its own window with its own icon. Full install with offline start needs the app to be served from `localhost` or over HTTPS; from a plain `http://` network address, adding it to the home screen still works as a shortcut.

> The app has no HTTPS of its own. On your home network sign-in keeps others out, but don't expose it to the internet without putting it behind something that adds HTTPS.

---

## 19. Recommended routine

**A quick look, any day:** open the Dashboard. The banner tells you whether every bill is covered; **Safe to spend** is what you can spend beyond your usual everyday spending. Check the 🔔 if it shows a number.

**Each payday (or weekly):**
1. **Get transactions in** – Transactions → Download from SimpleFIN (or import your bank's CSV). Bill payments in them are recorded automatically; confirm any listed under *Bill payments found*.
2. **Update balances** – Settings → Sync Balances Now, or Accounts → Update.
3. **Mark paid** anything in the Dashboard checklist you've paid that wasn't recognized (leave *Take the money out* off if your balances already reflect it).
4. **Categorize** anything uncategorized (Transactions → ⚠ Uncategorized).
5. **Set aside** money for your goals.

**Monthly:**
1. **Record actual amounts** for Variable bills when statements arrive (Bills → **$**).
2. **Review Budgets** and adjust them; check **Reports** for trends.
3. **Open the Optimizer** and work through the recommendations: fix anything **Short**, pay card/loan payments on payday where it saves money, check promo deadlines.
4. Add any **repeating charges** suggested on the Bills page.
5. **Download a backup** (Settings → Data & backup).
6. Occasionally revisit **Debt Payoff** and **What-If** for bigger decisions.

---

## 20. Troubleshooting & FAQ

**The web page loads but shows errors / no data.**
The API server isn't running or isn't reachable. Check Settings → API Connection, and make sure the "Budget API Server" window is open (or run `python api_server.py`).

**`start.bat` fails with "python313.dll" or similar.**
The virtual environment was built with a Python version that has since been uninstalled. Delete the `.venv` folder and recreate it: `py -3.13 -m venv .venv` (or use `uv venv`), then run `start.bat` again.

**A projection shows a payment as Deferred.**
On that day, no checking account had enough money for it. Look at the Timeline calendar for that day, then add income, move money, or change the payment's source.

**Why is my credit card "minimum payment" higher than my statement says?**
It includes enough to pay off each 0% promo before it expires (see §2). Pay at least your statement minimum in real life; the app's figure is what keeps you clear of deferred interest.

**I marked something paid by mistake.**
Use **Reset** to mark it unpaid, then correct the source account's balance with Accounts → **Update** (Reset doesn't refund the payment).

**Can I import my data from a spreadsheet?**
Yes: *Settings → Data & backup* → **Blank template**, fill it in, then **Import from Excel** (the command-line menu, `python cli.py`, can do the same). Template example rows are marked `EXAMPLE` and skipped. Importing skips items that already exist.

**Safe to spend seems too high.**
Check that everyday spending is set (the Dashboard warns if it isn't), and that bills you've already paid are marked paid — and ones you haven't, aren't. Open *How this is worked out* under the number to see each piece.

**A bill payment was matched to the wrong bill.**
Click **undo** on the transaction's ✓ badge (Transactions page). That removes the payment it recorded; then confirm the right bill or mark it paid by hand.

**A bill shows as overdue but I paid it.**
Mark it paid (Dashboard checklist or Bills → Pay) with the date you paid, and leave *Take the money out* off if your balance already reflects it.

**My phone says the app isn't set up yet.**
No account exists yet. Open the app on the computer that runs it and create the first account there (§18).

**I forgot my password.**
Ask an admin for a reset link (*Settings → Users → Reset password*). If you're the only admin, on the computer that runs the app run `python -m models.auth reset-password <your username>` from the project folder (`python -m models.auth users` lists the usernames).

**I used a password before accounts existed.**
It still works: sign in with the username **admin** and your old password. You can then invite others and, if you like, create yourself a new admin account.

**Restoring a backup went wrong.**
The data that was replaced is in `~/.budget_app/backups/before-restore-<date-time>.db` — restore that file the same way.

**Where are the numbers for projections coming from?**
Everything is computed from what you've entered: balances, income schedules, bills, and account terms. Keep balances current for accurate forecasts.
