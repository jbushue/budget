# Budget Manager — Web Interface User Guide

Budget Manager models your real finances — bank accounts, credit cards, loans, bills, and income — and projects them forward day by day. It tells you how much you can safely spend, warns you before an account runs dry, and suggests where to move money to pay less interest.

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
8. [Timeline & Projection](#8-timeline--projection)
9. [Payment Optimizer](#9-payment-optimizer)
10. [Debt Payoff Estimator](#10-debt-payoff-estimator)
11. [What-If Scenarios](#11-what-if-scenarios)
12. [Settings](#12-settings)
13. [Recommended monthly routine](#13-recommended-monthly-routine)
14. [Troubleshooting & FAQ](#14-troubleshooting--faq)

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

The web UI forwards all data requests (`/graphql`, `/health`) to the API server, so both must be running.

### Where your data lives

Everything is stored in a single SQLite file: **`~/.budget_app/finance.db`** (on Windows, `C:\Users\<you>\.budget_app\finance.db`). Every change you make in the UI is saved immediately — there is no "Save" step. Back up this file to back up your budget.

### First-time setup checklist

Work through the pages in this order — each step builds on the previous one:

1. **Accounts** → add your bank(s), then checking/savings accounts, credit cards, HELOCs, and your mortgage with their current balances.
2. **Income** → add each paycheck and (optionally) how it is split between accounts.
3. **Bills** → add recurring bills. Credit card, mortgage, and HELOC payments are created for you automatically.
4. **Loan Groups** → (optional) bundle loans that are paid with a single payment, such as student loans.
5. **Dashboard** → check that the totals look right.

### Server options

| Environment variable | Default | Effect |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Address the API listens on. Leave as-is unless you know you need LAN access. |
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

In projections, a bill already marked paid is skipped for the *current* period only — every later period is paid normally.

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

**Route:** `/` · The home page; a one-screen summary of where you stand.

### Discretionary Funds (banner)

> *How much can I spend before my next couple of paychecks without coming up short?*

```
Discretionary Funds = all checking balances
                    + income expected before the horizon
                    − unpaid bills due before the horizon
```

- **Horizon** ("📅 Through") = your *second* upcoming pay date (looking up to 75 days ahead). With only one upcoming pay date it is that date + 14 days; with no income at all, today + 28 days.
- **💰 Checking** – current total of all checking accounts.
- **📥 Incoming** – every paycheck (full amount) expected before the horizon.
- **📋 Committed** – every *unpaid* bill due before the horizon, including card minimums, mortgage/HELOC payments, and loan groups (with any carryover). Already-paid bills and $0 card minimums are excluded.

The banner is **green** at $500 or more, **amber** from $100 to $499, and **red** below $100.

### 🧭 What to do next

The three most important recommendations for the next 30 days, from the same analysis as the Payment Optimizer (§9). They're ranked: 🚨 urgent (a bill that can't be paid), ⚠️ warnings, then 💡 money-saving moves, then 📈 tips. The line above them is the plan's one-sentence summary. **See the full payment plan →** opens the Optimizer with the full details. The card is hidden when there's nothing to show.

### KPI cards

| Card | Meaning |
|---|---|
| **Total Assets** | Sum of all checking and savings balances. (Home value is not included.) |
| **Total Liabilities** | Credit card balances + mortgage principal + HELOC balances. |
| **Net Worth** | Assets − liabilities. |
| **Banks** | Number of banks you've added. |

### Panels

- **Banks & Accounts** – every account grouped by bank, with type badges. Debts are shown as negative. 🔄 marks accounts kept in sync by SimpleFIN.
- **Upcoming Bills (30 days)** – everything due in the next 30 days, soonest first: 💳 card payments, 🏠 mortgage, 🏦 HELOC, groups, and regular bills. Paid items show **✓ Paid** with the amount struck through. Amounts include carryover.
- **Upcoming Income (30 days)** – each income source's next pay date and amount.
- **📈 Net Worth Over Time** – assets, liabilities, and net worth from daily snapshots. A snapshot is recorded the first time the Dashboard is opened each day (and at server start). The chart appears once there are at least two days of history.
- **90-Day Balance Projection** – projected total of checking + savings over the next 90 days (from the optimized projection — see §9).
- **💳 Recent Bill Payments** – the latest payments recorded with **Pay** on the Bills page: bill, amount, source account, date.

**Refresh** reloads the summary. Every page fetches fresh data each time you open it.

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

On confirm:

- the money leaves the source account (rejected with a message if funds or credit are insufficient — nothing changes),
- **bills:** the bill is marked paid; paying less than due shows "$X will carry over to next period",
- **credit cards:** the card balance drops by the amount paid,
- **mortgages:** the payment is split into interest, escrow, then principal,
- **HELOCs:** the balance drops by the amount paid,
- **groups:** the payment is distributed across the group's loans (see §6),
- the payment is recorded and appears in **Recent Bill Payments** on the Dashboard.

### 🔄 Auto-Reset

Marks paid items unpaid when their next due date (after the last payment) has arrived. This also runs automatically every time the server starts, so you normally don't need it.

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

## 8. Timeline & Projection

**Route:** `/timeline` · A day-by-day forecast of every account.

Choose the period (30, 60, 90, 180 days, or 1 year) and **Refresh**. The forecast is the **optimized** projection — it includes the money moves recommended by the Optimizer (see §9).

### Stat cards

| Card | Meaning |
|---|---|
| Total Income | All paychecks in the period. |
| Total Expenses | All bill, card, mortgage, HELOC, group, extra, and promo payments. |
| Net Change | Change in your total cash (checking + savings) from today to the end of the period. This can be negative even when income exceeds expenses: when the optimizer parks spare cash in a HELOC (see §9), cash goes down but your HELOC debt goes down by the same amount. |
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

## 9. Payment Optimizer

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

## 10. Debt Payoff Estimator

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

## 11. What-If Scenarios

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
- **Comparison table**, current plan vs. scenario: late or missed payments, lowest checking balance, cash and debt at the end, interest charged, and **Overall (cash − debt)**. Green means better and red means worse.
- **Payments that would be late or missed**: the specific bills and dates the scenario breaks.
- A **chart** of both projections day by day.

> The what-if comparison uses the plain (non-optimized) simulation for both sides so the difference reflects only your changes. Its baseline can therefore differ slightly from the Timeline, which includes optimizer moves.

---

## 12. Settings

**Route:** `/settings`

### 🔗 SimpleFIN Bridge (automatic balance sync)

[SimpleFIN Bridge](https://bridge.simplefin.org) is a read-only service that connects to your bank and lets this app fetch balances and transactions.

1. Create a connection at bridge.simplefin.org and copy the **Setup Token**.
2. Paste it into **Setup Token** and click **Connect**. (Tokens are single-use.)
3. In **Account Mapping**, pick the local bank and account for each SimpleFIN account and click **Map**. The type (bank / credit / mortgage / heloc) is filled in automatically.
4. Click **🔄 Sync Balances Now** whenever you want fresh balances. The result lists each account's change.

Mapped accounts show 🔄 across the app and get a **Txns** button on the Accounts page. **✕** unmaps an account; **Disconnect** removes the connection and all mappings. Only mapped accounts are updated.

### Database

- **Save to Database** – writes everything to disk. Normally unnecessary (every change is saved automatically).
- **Load from Database** – reloads from disk, discarding anything not yet saved.

### API Connection

Shows whether the web UI can reach the API server, plus counts of banks, bills, and income sources. **Check Status** re-tests.

### About

The API endpoint and a link to the **GraphQL Playground**, an interactive console for the API (useful for developers).

---

## 13. Recommended monthly routine

1. **Sync or update balances** – Settings → Sync Balances Now, or Accounts → Update.
2. **Record actual amounts** for Variable bills when statements arrive (Bills → **$**).
3. **Pay** bills as you pay them in real life (Bills → **Pay**), so the paid status, carryover, and balances stay accurate.
4. **Check the Dashboard**: the banner, **What to do next**, and Upcoming Bills.
5. **Open the Optimizer** and work through the Recommendations, top to bottom. Fix anything marked **Short**, pay card/loan payments on payday where it saves money, and check promo deadlines.
6. Occasionally revisit **Debt Payoff** and **What-If** for bigger decisions.

---

## 14. Troubleshooting & FAQ

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
Yes, through the command-line menu: run `python cli.py`, then **6. Database & File Management** → Import from Excel / Export to Excel / Generate template. Template example rows are marked `EXAMPLE` and skipped. Importing skips items that already exist.

**Where are the numbers for projections coming from?**
Everything is computed from what you've entered: balances, income schedules, bills, and account terms. Keep balances current for accurate forecasts.
