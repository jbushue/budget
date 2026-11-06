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
11. [Subscriptions & Recurring](#11-subscriptions--recurring)
12. [Net Worth & Assets](#12-net-worth--assets)
13. [Financial Health Check](#13-financial-health-check)
14. [Timeline & Projection](#14-timeline--projection)
15. [Plan (Payment Optimizer)](#15-plan-payment-optimizer)
16. [Debt Payoff Estimator (now on the Plan page)](#16-debt-payoff-estimator)
17. [What-If Scenarios](#17-what-if-scenarios)
18. [Reports](#18-reports)
19. [Alerts](#19-alerts)
20. [Settings](#20-settings)
21. [Activity](#21-activity)
22. [Using it on your phone, and installing it](#22-using-it-on-your-phone-and-installing-it)
23. [Recommended routine](#23-recommended-routine)
24. [Troubleshooting & FAQ](#24-troubleshooting--faq)

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

Everything is stored in a single SQLite file: **`~/.budget_app/finance.db`** (on Windows, `C:\Users\<you>\.budget_app\finance.db`). Every change you make in the UI is saved immediately — there is no "Save" step. **Settings → Data & backup → Download backup** saves a copy of it (§20).

### First-time setup checklist

Work through the pages in this order — each step builds on the previous one:

1. **Accounts** → add your bank(s), then checking/savings accounts, credit cards, HELOCs, and your loans (mortgage, auto, student, personal) with their current balances.
2. **Income** → add each paycheck and (optionally) how it is split between accounts.
3. **Bills** → add recurring bills. Credit card, loan, and HELOC payments are created for you automatically.
4. **Loan Groups** → (optional) bundle loans that are paid with a single payment, such as student loans.
5. **Settings → Planning** → set your **cushion** and your **everyday spending** (groceries, gas, eating out — anything that isn't a bill). These drive Safe to spend.
6. **Transactions** → (optional, recommended) download them from SimpleFIN or import a CSV from your bank. Bill payments in them are recognized automatically, and everyday spending can be learned from them.
7. **Dashboard** → check that the status and Safe to spend look right.

### Server options

| Environment variable | Default | Effect |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Address the API listens on. Leave as-is: the web interface reaches the API through its proxy, including from your phone (§22). |
| `BUDGET_CORS_ORIGINS` | none | Comma-separated list of other web addresses allowed to call the API from a browser (e.g. `https://budget.example.com`). Leave unset: the web interface and its proxy are on the same address as the API, so cross-site access is off by default. |
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
| Money market | Asset | Treated like savings. |
| CD | Asset | Earns interest but is locked, so it never pays bills. |
| Cash, Prepaid card, PayPal / Venmo / Cash App | Asset | Spending money outside your bank. Prepaid cards and payment apps can pay bills; cash can't. |
| EBT / SNAP | Asset (restricted) | Food benefits. Never counted in Safe to spend and never used for bills. Can have a monthly benefit deposit and weekly grocery spending (see below). |
| HSA, FSA | Asset (restricted) | Health money: not spending money and never used for bills. An HSA can earn interest. |
| Brokerage, Retirement | Asset | Counted in net worth. The rate is the growth you expect per year, added monthly in projections. |
| Other | Asset | Anything else; counted in net worth only. |
| Credit card | Liability | Has a limit, APR, due day, statement day, and optional 0% promos. |
| HELOC | Liability | Home-equity line with a draw period (interest-only minimums) followed by a repayment period. |
| Mortgage | Liability | Fixed-rate home loan with a principal/interest/escrow breakdown. Its monthly payment is calculated for you. |
| Auto loan | Liability | Fixed-rate car loan. The vehicle's value (optional) counts toward net worth and loses a share of its value every year (15% unless you change it). |
| Student loan | Liability | Fixed-rate loan that can be in school, grace or deferment: nothing is due until **payments start**. An unsubsidized loan's interest from now until then is added to what you owe at the first payment; a subsidized loan's isn't. |
| Personal loan, Other loan | Liability | Any other loan with a fixed monthly payment (a 0% installment plan is one with an APR of 0). |

Every kind of loan can take the **payment from your statement** when the lender's amount differs from the calculated one (an income-driven student loan plan, for example). The payoff date and schedule then follow that payment.

### Bills, and bills that are created for you

A **bill** is anything you pay on a schedule. There are two kinds you create:

- **Fixed** — same amount every period (rent, subscriptions).
- **Variable** — changes each period (utilities). You enter an *estimate* plus an expected min/max range and can record the actual amount when the statement arrives. Once you record actual amounts, the estimate for future periods tracks your recent history.

And bills the app creates and maintains automatically, shown with an **`[Auto]`** name:

- **`[Auto] <card> Payment`** for every credit card with a balance — the amount is the card's current **minimum payment**.
- **`[Auto] <loan> Payment`** for every mortgage and loan — the full monthly payment (principal + interest, plus escrow for a mortgage). A student loan's is $0 until its payments start.
- **`[Auto] <HELOC> Payment`** — the HELOC's minimum payment (interest-only during the draw period).
- **`[Auto] <group> Payment`** for every loan group — the group's total payment.

These follow their account: change the card's due day and the bill's due day changes; delete the card and the bill disappears. You can't edit their amounts directly — update the underlying account instead.

### Credit card minimum payments

Card issuers each use their own formula: a percentage of the balance, often plus the month's interest, never less than a floor (and never more than the balance). Installment financing asks a fixed amount.

- **Match it to your statement** (Accounts → the card's **Minimum** figure, or ⋯ → **Match minimum payment**): enter the minimum from your latest statement, and optionally the statement balance and interest charged. The app tries the usual formulas (1%–5% of the balance, with or without interest, with floors from $10 to $50, allowing for statements that round to whole dollars) and shows every one that gives that amount, most common first. Pick one and the card follows it in every projection. If none fits exactly but one is close (within 5% or $3), the closest is picked and used as it is, with how far off each option is shown; otherwise it's treated as a fixed monthly payment. If the balance is small enough that only the floor applies, the app can tell the floor but not the percentage, and says so; check again with a later statement.
- **Edit the formula** in the same dialog: a percentage of the balance (with *+ the month's interest* and an *at least* amount) or a fixed amount. Picking a match fills it in, and you can adjust it before saving. A preview shows what it gives on the statement (or today's balance) next to your statement's minimum.
- **Until you do**, a card uses **1% of the balance plus the month's interest, at least $25**, the most common formula. (A flat 2% is less than the interest on cards above 24% APR, which would never pay the balance down.)

The column says *your formula* or *estimated*. **On top of** the issuer's minimum, each active 0% promo gets enough to be paid off before it expires (promo balance ÷ payments remaining), shown as *+ promo payoff*. That keeps you from being hit by deferred interest.

### 0% promotional offers and deferred interest

A card's minimum payment in the plan includes each 0% promo's share: what's left on the promo divided by the payments remaining before it ends (all of it on the last one), on top of the minimum on the regular balance. That way a promo is paid off by the payment before it expires, even when the card also carries a regular balance.

How each payment is split depends on the card's **Payments go to** setting (in the card's **Promo offers** dialog, or **Edit details**). Set it to match how your card issuer applies payments:

- **Regular balance's minimum first** (the default) — the regular balance gets its own minimum, then the promo balances, then whatever is left goes back to the regular balance.
- **Promos first, regular balance last** — everything goes to the promo balances until they're paid off; the regular balance only gets what's left.

Either way, promo balances are paid **soonest-expiring first**: each one is paid off before the next gets anything. Whenever an even split would pay every promo off in time, so does this. The same split is used everywhere a card is paid: its payment bill, loan group payments, extra payments in the plan, and payments you record. (A payment you aim at one promo, like **Pay down** on a promo, still goes to that promo first.) The promo deadlines on the Plan page (Debt tab) show whether each promo is on track, and you get an alert if the plan can't pay one off in time.

A promo carves out part of the card's existing balance as interest-free until the promo's end date. Interest is only charged on the **regular** balance. If a promo **expires with a balance remaining**, the app charges **deferred (retroactive) interest** as if the promo never existed — `remaining × ((1 + APR/12)^months − 1)` — and the leftover amount becomes regular, interest-bearing debt. Projections apply this on the simulated expiry date, so you can see the hit coming.

### Paid status, due date by due date

Every due date of every bill is tracked on its own: **paid**, **partly paid**, **skipped**, **overdue**, or still to come. A payment always belongs to one due date. Marking a bill paid:

- withdraws the money from the chosen source account (or charges a credit card if you pay with one),
- records the payment against that due date (by default the oldest one still owed, otherwise the next one),
- leaves the due date **partly paid** if you pay less than it owes. The rest is still owed, and the plan pays only the rest.

A new month's bill is simply unpaid; nothing needs resetting. You can **pay ahead**: mark next month's (or any due date up to a year out) paid and the plan leaves it out. **Skip** a due date that isn't owed (waived, or paid some way the app doesn't track).

In projections, every due date already paid or skipped is left out, and partly paid ones only cost what's left. **Overdue** due dates (passed without being fully paid) are paid on the projection's first day, because that money is already owed. Your balances never look bigger than they are. Paying an overdue bill counts for the missed due date, so the next one is still owed.

For monthly (and longer) bills a payment belongs to its month, so changing a bill's due day keeps the month paid. A due date only counts as overdue if the bill existed then. For bills you had before due dates were tracked, the month before the update is the furthest back that counts.

**Record only.** If your balances are already up to date (for example, synced with SimpleFIN), the payment has already left your account — taking it out again would count it twice. The Pay / Mark paid dialog has a checkbox, *Take the money out of the account in this app now*; leave it off to just record the payment. It's off by default when you use SimpleFIN. Bill payments recognized in your transactions (§8) are always recorded this way.

### Everyday spending and the cushion

Bills aren't everything you spend. **Everyday spending** — groceries, gas, eating out, the odd purchase — is set in *Settings → Planning* as a weekly amount, or learned from your transactions (the average of the last 8 weeks of spending in "everyday" categories, once there are at least 3 weeks of history). Every projection takes it out of checking a day at a time.

The **cushion** is money you always want left in checking for surprises. Safe to spend never dips into it, and alerts warn you when checking is projected to fall below it.

### Fees

Projections charge the fees you'd really pay: a **late fee** when a payment can't be made on its due date (set app-wide in *Settings → Planning*, for cards/HELOCs and for other bills, and per bill on the bill form), and an **overdraft fee** each time checking would go below $0. Fees show up in the Plan and What-If comparisons.

### Payment sources

Every bill, group, mortgage, and HELOC can have a **preferred source** (bank + account). When you mark a payment paid without choosing a source, the preferred source is used. In projections, payments come from the preferred source when it has enough money; otherwise from another checking account that does. If no account can cover a payment, the projection marks it **Deferred** and shows a warning.

### Projections

**One plan for the whole app.** The app works out your plan once, day by day for the next **year** (365 days), and keeps it until something changes (a balance, bill, paycheck, setting, or the date). The Dashboard, Timeline, Plan page, What-if, alerts and the daily email all read that same plan, so they agree about every day they show. A 30-day view is just the first 30 days of the same plan, not a different one. Period pickers only change how much you see. The plan never lets checking drop below **your cushion** (there's no hidden minimum). "Lowest checking" always means all your checking accounts added together.

The simulation starts today. Each day, in order: income deposits, optimizer moves that bring money back to checking, bill/loan payments, then other optimizer moves and interest. Interest is applied monthly:

- **Savings/checking:** on the account's *Interest Day* at APY/12 (the end of each month if no Interest Day is set).
- **Credit cards:** on the statement day (or the due day, if the card has no statement day) at APR/12 on the regular (non-promo) balance. A 0% promo that still owes money at the end of its last day is charged its deferred interest that day, not at the next statement.
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
| ⚠️ **Bills are covered — if you follow the plan** | Paying everything on its due date leaves a bill short, but the plan (moving money from savings, timing payments) covers it. **See the plan** shows how. |
| ⚠️ **Bills past due and not marked paid** | A due date has passed with no payment recorded. Mark them paid if you've paid them; until then the plan pays them first, out of today's money. |
| ⚠️ **Checking gets tight** | Everything is paid, but checking drops below your cushion. |
| 🚨 ***Bill* can't be paid on *date*** | Even the optimized plan comes up short. **See the plan** for ways to cover it. |
| 🚨 **Checking goes negative** | Everyday spending would overdraw checking before the next paycheck. |

### 💵 Safe to spend — how much can I spend?

Safe to spend looks **past your next paycheck**: by default 90 days ahead (Settings → Planning → *Look ahead*), following your plan. If a bill or promo payment after payday needs some of the money you have today, because the paychecks before it won't cover it on their own, that money is held back. The card tells you how much is kept and for which bills. Bills the plan can't pay on time are paid late, and count as owed until they are. Money the plan only parks (savings, a HELOC) still counts as yours, and so do the optimizer's early card payments under *Most cash*. Under *Least interest* or *Pay off a card*, those payments are spoken for.

The extra you can spend **on top of** your usual everyday spending without missing a bill or dipping into your cushion:

```
Safe to spend = lowest projected checking balance over the look-ahead
                (after every bill and your everyday spending, less any
                bills owed but not paid yet)
              − your cushion
              − money set aside in checking for goals
```

Overdue bills are paid on the projection's first day, so they're already out of the lowest point. A bill there isn't enough money for on its due date is paid as soon as there is (usually your next payday), with its late fee. Until then it's owed, so its money never counts as yours, in Safe to spend or on the *Checking* chart. It's the *lowest* point that matters, not a total: a dollar spent today lowers every later day's balance too. Below it, **$/day** spreads it over the days until your next paycheck. *How this is worked out* shows each line, including how much of the lowest point is money the plan keeps in savings or pays toward debt early (still yours). If everyday spending isn't set, a warning says so — the number would assume you spend nothing besides bills.

### 🧾 Bills before your next paycheck

A checklist of what's due this pay period (plus anything overdue), each with a status:

| Badge | Means |
|---|---|
| **Paid** | Marked paid for this due date. |
| **Covered** | There will be enough on the due date. |
| **Covered with plan** | Covered if you follow the plan. |
| **Short $X** | There won't be enough; X is how much is missing. |
| **Overdue** | The due date passed with no payment recorded. |

**Mark paid** opens a quick dialog for that due date (amount, date, account, and whether to take the money out in the app — see "Record only" in §2). Your next paychecks are listed underneath.

### 🔗 Bill payments found in your transactions

When imported transactions look like bill payments but aren't certain enough to record automatically, they're listed here: **Yes, it's *bill*** records the payment (no money moves), **Not a bill** stops suggesting it. See §8.

### 🧭 What to do next

The three most important recommendations for the next 30 days, from the same plan as the Plan page (§15). They're ranked: 🚨 urgent (a bill that can't be paid), ⚠️ warnings, then 💡 money-saving moves, then 📈 tips. **Full payment plan →** opens the Plan page.

### 📉 Checking over the next *N* days

A chart of checking for the look-ahead period, following your plan. It uses the same numbers as Safe to spend: money the plan parks in savings or puts toward debt early is counted as yours. The dashed line is your cushion and the lowest point is marked. **Day by day →** opens the Timeline.

### Where things stand

- **Total assets / Total liabilities / Net worth / Health score** – net worth opens the Net worth page (with its history chart), the score opens the Health check.
- **Banks & accounts** – every account grouped by bank. Debts are shown as negative. 🔄 marks accounts kept in sync by SimpleFIN.

Upcoming bills and paychecks are in the pay-period checklist above (and day by day on the Timeline). Recent bill payments are on the Bills page.

The 🔔 bell at the top right of every page lists alerts (§19). **Refresh** reloads everything.

---

## 4. Accounts

**Route:** `/accounts` · Create and maintain banks and accounts, and keep balances current.

### Adding a bank — **+ Bank**

| Field | Notes |
|---|---|
| Bank Name | Required, must be unique. |
| Type | Traditional (default) / Credit Issuer / Mortgage Lender. Informational. |

**Edit** (next to the bank's total) renames the bank or changes its type. Every account, bill, transaction and SimpleFIN link stays connected.

**Delete Bank** removes the bank and *all* of its accounts (and their auto-bills) after confirmation.

### Adding an account — **+ Account**

| Field | Applies to | Notes |
|---|---|---|
| Bank | all | Required. |
| Account Name | all | Required; unique within the bank. |
| Account Type | all | Checking, Savings, … Credit Card, HELOC, Mortgage, Auto loan, Student loan, Personal loan, or Other loan. |
| Starting Balance / Current Balance (owed) | all | For cards, HELOCs, and loans this is the amount **owed**. For a loan it's the current principal; leave it blank (0) for a brand-new loan to use the original amount. |
| APY % / APR % | all | Annual percentage. |
| Interest Day (1-31, optional) | accounts that earn | Day of month interest is credited. Leave blank for the end of each month; an account that earns nothing just has an APY of 0. |
| Money added each month + day | EBT, HSA, FSA, cash, apps, investments | A deposit that doesn't come from checking: SNAP benefits, HSA or 401(k) contributions. |
| Spent per week | EBT, HSA, FSA, cash, apps, prepaid | How much you spend from it each week (groceries on EBT, for example). |
| This replaces part of my everyday spending | same | Checked: while the account has money, it pays that part of your everyday spending, so it doesn't also come out of checking. When it runs out, checking covers it until the next deposit. |
| Credit Limit | credit card, HELOC | Required and must be greater than 0. |
| Payment Due Day (1-31) | credit card, HELOC | Sets the due day of the card's `[Auto]` payment bill. |
| Statement Day (1-31, optional) | credit card | Day interest is charged each month. |
| Draw Period (years) | HELOC | Default 15. During the draw period you can borrow and minimums are interest-only. |
| Total Term (years) | HELOC | Default 30. Includes the draw period; the remainder is the repayment period (principal + interest). |
| HELOC Start Date | HELOC | Optional; defaults to today. |
| Original Loan Amount | loans | Required. The amount originally borrowed. |
| Loan Term | loans | Years for a mortgage (default 30); months for other loans (auto 60, student 120, personal 36). |
| Loan Start Date (optional) | loans | When the loan began; for your records (defaults to today). |
| Payment Due Day (1-31) | loans | Default 1. Sets the due day of the loan's `[Auto]` payment bill. |
| Payment from your statement (optional) | loans | The lender's monthly payment, when it isn't the calculated one. Blank = calculated. |
| Monthly Escrow (optional) | mortgage | Property tax, homeowners insurance, PMI, HOA, and other amounts collected with each payment. |
| Home Market Value (optional) | mortgage | Used to calculate equity (value − principal). |
| Vehicle value + Loses (% a year) | auto loan | Optional. Counts toward net worth, losing that much each year (15% by default). Skip it if the car is already an asset on the Net worth page. |
| Payments start + Subsidized | student loan | Optional. Nothing is due before that date; unless it's subsidized, the interest until then is added to the balance at the first payment. |
| Pay From (optional) | loans | Preferred bank and account for the payment. Choose both or leave both on Auto. |

For a loan, the form shows the **monthly payment** as you type: the standard fixed-rate payment on the original amount over the full term (principal & interest), plus escrow for a mortgage — or the payment from your statement, if you entered one. This is the amount of the loan's `[Auto]` payment bill.

If anything is wrong (duplicate name, missing limit, invalid day…), you'll see an alert explaining why and nothing is created.

### Editing an account — **Edit**

Every account row has an **Edit** button that opens all of the account's settings: the same fields as when it was created, plus its **Name** and **Bank** (to rename it or move it to another bank), and for cards the **Status** (active, frozen, closed). Checking and savings accounts can be switched between the two types.

Renaming or moving an account takes everything with it: its `[Auto]` payment bill (with its paid status, history and pay-from account), bills and loan groups that pay from it, income splits, transactions and bill matches, savings goals, balance history and its SimpleFIN link. Change the **balance** with **Update** instead, so the change is logged in the history. A mortgage's or HELOC's **Pay From** account is used for its payment bill right away.

### Bank Accounts table

Columns: **Account** (🔄 SimpleFIN tag if synced), **Type**, **APY**, **Interest Day**, **Balance**.

Actions:

- **Edit** – change the name, bank, type, APY or interest day (see *Editing an account*).
- **Update** – type in the real current balance (e.g. from your banking app). The change is saved and logged.
- **Hist** – balance history: date, previous, new, and change for each update.
- **Txns** – recent transactions pulled from SimpleFIN (synced accounts only, read-only).
- **Del** – delete the account.

### Credit Accounts table

Columns: **Account** (🏷️ N = number of promos), **Status** (active / closed / frozen), **APR**, **Due Day**, **Balance**, **Limit**, **Minimum** (the payment the plan makes; click it to match your statement, see §2), **Utilization** (balance ÷ limit; green ≤ 50%, amber ≤ 80%, red above).

Actions: **Edit** (name, bank, APR, limit, due and statement days, status), **Update** (new balance owed), **Hist**, **Txns**, **Promos**, **→ HELOC**, **Del**.

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

**Edit** changes any of a promo's fields: name, months, purchase limit, balance and dates (changing the months or start date recalculates the end date unless you give one). End dates count calendar months: a 12-month promo from Jan 31 ends Jan 31 next year (or the month's last day). Lowering the card's balance with **Update** below what its promos hold shrinks the promos to match. **Remove** removes the promo and returns its balance to the regular balance.

Each promo's **⋯** menu also has:

- **Add a purchase** — charges a new purchase to the card and puts it on this promo (if the promo is still active and under its purchase limit; otherwise it goes on the regular balance).
- **Pay down** (or the **Pay** button) — pays the promo balance from a checking or savings account. The money comes out of that account and off the promo first. The amount is capped at what's left on the promo.

#### Convert to loan

For a loan that was entered as a credit card (student loans often are, inside a loan group). It becomes a real loan of the kind you pick — student, auto, personal or other — with the same name, bank, balance, APR and due day. **Keep today's payment** works out the months left from the card's current minimum; or set the months yourself. A student loan can also get a payments-start date and be marked subsidized. Its loan group membership, payment bill (and the payments recorded on it), balance history and SimpleFIN link carry over; the credit limit goes away.

#### Convert to HELOC (**→ HELOC**)

Replaces a credit card with a HELOC, keeping its balance, APR, credit limit, and due day. You choose the draw period, total term (must be longer than the draw period), start date, and optionally a new name. The card's payment bill is replaced by the HELOC's.

### Update all balances and Move money

**Update balances** (top of the page, also on the Dashboard) lists every account with its current balance. Type in today's numbers from your banks' apps; only the ones you change are saved, and each change is added to that account's balance history. Cards, loans and home equity lines take what you owe.

**Move money** records a transfer between any two checking or savings accounts — at the same bank or different ones. It won't take an account below zero.

### Loans table (mortgages, auto, student, personal and other loans)

Columns: **Status**, **APR**, **Due Day**, **Principal**, **Monthly Payment** (P&I + escrow; "from your statement" when you entered the lender's payment), **P & I** (this month's principal/interest split), and **Escrow** (monthly taxes, insurance, PMI, HOA) when the bank has a mortgage. Loans other than mortgages show their kind next to the name, and a note when a student loan has nothing due yet or an auto loan has a vehicle value.

Actions: **Edit** (kind of loan, amounts, rate, term, start date, due day, payment from your statement, escrow and home value for a mortgage, vehicle value and yearly loss for an auto loan, payments start and subsidized for a student loan, pay-from account, name and bank), **Update** (set the current principal), **Hist**, **Txns**, **Del**. Loan payments are made from the Bills page.

**Payoff & schedule** (in the row's ⋯ menu) opens the loan tools:

- The balance, monthly payment (loan + escrow), payoff month, interest still to pay and, with a home or vehicle value, equity and loan-to-value.
- **Pay off sooner** — slide or type an extra monthly amount to see how much sooner the loan is paid off and how much interest that saves.
- **Next 12** — the next 12 payments: date, payment, principal, interest, escrow and what's owed after each.
- **By year** — principal and interest paid each remaining year and the balance at year end.
- **Pay extra** — a one-time payment straight to principal, taken from a checking or savings account (or recorded without moving money if you already paid it).

### HELOC Accounts table

Columns: **Phase** (draw / repayment / paid_off), **APR**, **Due Day**, **Balance**, **Limit**, **Available** (draw phase only), **Min Payment** ("interest only" in the draw phase, "P+I" in repayment), **Draw Ends**.

Actions: **Edit** (limit, rate, draw period, total term, start date, due day, pay-from account, name and bank), **Update**, **Hist**, **Txns**, **Del**.

---

## Finding your way around

The sidebar groups the pages:

- **Money** – Accounts, Transactions, Bills, Income, Loan groups
- **Plan** – Plan (formerly the Optimizer), Timeline, What-if
- **Spending** – Budgets, Goals, Subscriptions
- **Insights** – Reports, Net worth, Health check
- **Manage** – Activity, Settings (alerts are under the bell at the top)

Pressing a button keeps your place on the page; opening another page starts at the top, and **Back** returns to where you were. Dialogs close with **Cancel** or a click outside them (a drag that starts inside a dialog, such as selecting text, doesn't close it).

## Search and quick actions

Press **Ctrl+K** (⌘K on a Mac) or **/** anywhere, or click **Search or jump to...** at the top. Type to find:

- any page, account (with its balance), bill, income source or savings goal;
- an action: add a transaction, bill, income or goal, move money, update all balances, download the bills calendar, export to Excel, print the page, or switch light/dark mode;
- **Search transactions for "..."** — opens Transactions filtered by what you typed.

Use ↑ ↓ and Enter, or click. Esc closes it.

## Downloads and printing

**Reports → Download a report** (and the **Download** menu on the Timeline) gives CSV or Excel files for 30 days to a year ahead:

| Report | What's in it |
|---|---|
| Month by month | Projected income, bills and payments, everyday spending, fees, interest, net change, and cash and debt at each month's end |
| Every payment and paycheck | Each projected event by date, with its account |
| Payment plan | When to pay each bill and from which account (the Plan page) |
| Daily balances | Every account's projected end-of-day balance |
| Accounts today | Every account with its balance, limit and rate |

The **bills & paydays calendar** (.ics) adds the next six months of due dates and paydays to Google, Apple or Outlook calendar, with a reminder the day before each bill. Download it again whenever your bills change.

To get a **PDF**, print any page and choose *Save as PDF* — the sidebar, menus and buttons are left out.

## 5. Bills & Payments

**Route:** `/bills` · Everything you pay, month by month, and where you record payments. Two tabs: **By month** (the default) and **All bills**.

### By month

Switch months with **‹ ›** (or **This month**). You can go back a year, and forward as far as the plan looks (the *how far ahead* choice on Timeline / Plan). The month is in the address (`/bills?month=2026-12`), so it survives a refresh.

Every due date in the month is listed: a weekly bill has several rows, and card, mortgage, HELOC and loan group payments are included. Each row shows the due date, the amount it owes (a variable bill shows whether that's the estimate or the actual amount), and its status:

| Badge | Means |
|---|---|
| **Paid** | Paid in full (with the amount and date paid underneath). |
| **Partly paid** | Some was paid; what's left is shown underneath and still owed. |
| **Overdue** | The due date passed without being fully paid. |
| **Due today / Due in N days / Upcoming** | Still to come. |
| **Skipped** | Marked as not owed. |
| **Not tracked** | Before the bill was added (or before due dates were tracked), so never counted as owed. |
| **Nothing due** | A card or loan with no payment that month. |

Cards across the top total the month: **due**, **paid**, **left to pay**, and **overdue**. If money is still owed from earlier months, a note says so, with **Go back a month**.

| Action | What it does |
|---|---|
| **Pay** / **Pay rest** | Opens the payment dialog for that due date. |
| ⋯ **Set this month's amount** | Variable bills: the real amount for this due date only; the others keep the estimate. |
| ⋯ **Undo payment** | Removes what was recorded for that due date. Money the app took out goes back to the account it came from, and a card or loan owes it again. |
| ⋯ **Skip (not owed)** / **Owed after all** | Leave the due date out of everything (or bring it back). |

### All bills — the table

Rows include regular bills, credit card payments (cards with a balance that aren't in a loan group), mortgage and HELOC payments, and loan groups. Overdue items are listed first, then unpaid ones, then by due day.

| Column | Meaning |
|---|---|
| Next due | **Overdue** (from the oldest missed due date), **Due** (with the date a payment goes to), or **Paid** (the next due date is already paid). |
| Name | Bill name; card/mortgage/HELOC rows show "Bank · Account". |
| Type | Fixed, Variable, 💳 Credit, 🏠 Mortgage, 🏦 HELOC, 🎓 Group. |
| Frequency / Due Day | Schedule. |
| Amount | What's still owed on the due date a payment goes to now. Card rows show the minimum payment with the full balance underneath. |
| Details | Card: utilization + APR · Group: member count + total balance · Mortgage: principal + APR · HELOC: balance + phase · Bill: anything left unpaid from earlier due dates, or the actual amount / expected range for Variable bills. |
| Source | Preferred payment source, or "Auto". |

**Filter chips** across the top: All, Fixed, Variable, 💳 Credit, 🎓 Groups, 🏠 Mortgage, 🏦 HELOC, Overdue. The footer totals the visible rows.

**Summary cards:**

- **Est. Monthly Obligations** – every item converted to a monthly amount (weekly × 4.33, bi-weekly × 2.17, quarterly ÷ 3, semi-annual ÷ 6, yearly ÷ 12, one-time excluded).
- **Overdue due dates** – how many due dates have passed without being fully paid.
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
| **Pay** | unpaid bills, cards, mortgages, HELOCs, groups | Opens the payment dialog (below) for the due date a payment goes to now. |
| **Set amount** | unpaid Variable bills | The real amount of the next bill (shows the expected range). Other due dates keep the estimate. |
| **Edit** / **Del** | regular bills | Edit or delete the bill. Editing a variable bill keeps its estimate. `[Auto]` payment bills can't be deleted; they follow their card, mortgage, HELOC or group. |
| **Details →** | groups | Opens Loan Groups. |

### The Pay dialog

| Field | Default |
|---|---|
| Amount Paid | What's still owed on that due date (cards: the minimum payment). The dialog says which due date it pays. |
| Source Bank / Account | The preferred source (cards: the first checking account if none). Credit cards are listed as "(credit card)" — paying with a card **charges** that card. |
| Payment Date | Today. |
| Take the money out of the account in this app now | On, unless you use SimpleFIN. Turn it off when your balances already include this payment ("Record only", §2) — then only the paid status and history change. |

On confirm (with money taken out):

- the money leaves the source account (rejected with a message if funds or credit are insufficient — nothing changes),
- **bills:** that due date is marked paid; paying less than it owes shows "$X will still be owed for this due date",
- **credit cards:** the card balance drops by the amount paid,
- **mortgages:** the payment is split into interest, escrow, then principal,
- **HELOCs:** the balance drops by the amount paid,
- **groups:** the payment is distributed across the group's loans (see §6),
- the payment is recorded and appears under **Recent payments** at the bottom of the Bills page.

**Pay** and **Mark paid** only record a payment once: pressing the button twice, or recording the exact same payment again right after, is refused.

### 🔁 Repeating charges that aren't bills yet

When your transactions show the same payee charging you on a steady schedule (weekly, every two weeks, monthly, quarterly, or yearly) with similar amounts, and it isn't a bill yet, it's listed at the top of the Bills page with how often, the typical amount (and range, if it varies), and when it's next expected. **Add as bill** creates it (fixed, or variable if the amount moves around) so projections and Safe to spend account for it; **Dismiss** hides the suggestion for good.

---

## 6. Loan Groups (Bill Groups)

**Route:** `/bill-groups` · Bundle several loans that you pay with **one** payment — typically federal student loans serviced together.

When a card or loan is in a group, it no longer gets its own payment row; the group appears as a single payment instead, everywhere (Bills, Timeline, Plan).

### Group cards

Each group shows its type icon (🎓 Student Loan, 📦 Bundled Bill, 🏦 Consolidated Loan, 📋 Other), frequency, PAID/DUE status, **Monthly Payment**, **Total Balance** (sum of members), **Sub-Loans** count, **Due Date**, and payment source.

The members table lists each loan's bank, account, APR, balance, allocation method, and **Est. Payment** — how much of the group payment goes to that loan.

### How a group payment is split (allocation)

1. Members with **Fixed amount** get their fixed amount first (scaled down proportionally if the fixed amounts add up to more than the payment).
2. The rest is split among the other members — **Proportional** members by their share of the balance, **Equal** members evenly (members with a $0 balance are skipped).
3. A loan never receives more than it owes; any excess goes to the other members.

### Actions

- **+ New Group** / **Edit**: Group Name (unique; a name already in use is refused), Total Monthly Payment, Due Day, Frequency (Monthly / Bi-weekly / Quarterly), Group Type, Payment Source Bank/Account.
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

### Split between accounts

In the row's ⋯ menu. Controls which accounts a paycheck lands in. Choose **Dollar amounts** or **Percentages**, then add one row per account (checking/savings only):

- **Amount** – a set dollar amount (or a percentage of each paycheck) sent to that account.
- **Blank** – "the rest": everything left over. Only one account may get the rest.

A preview shows how a paycheck would be split. Examples: $500 → Savings, blank → Checking; or 20% → Savings, blank → Checking. Switching between dollars and percentages converts what you've entered. With no split set, or if the account it named has been deleted, the whole paycheck goes to the first checking account.

---

## 8. Transactions

**Route:** `/transactions` · Your real bank and card activity. Transactions power budgets, reports, the learned everyday spending, and automatic bill matching. Adding them never changes account balances.

### Getting transactions in

- **⟳ Download from SimpleFIN** (when SimpleFIN is connected) – fetches the last 90 days for every mapped account. Run it again any time; transactions already downloaded are skipped.
- **⬆ Import CSV** – download a CSV from your bank's website (usually "Download" or "Export" on the account activity page), pick which account it belongs to, and choose the file. The date, description, and amount columns are detected for you — or pick them yourself, including files with separate *money out* / *money in* columns. Check the preview: money spent should show with a "−"; if it doesn't, tick *Purchases show as positive numbers*. Re-importing the same file skips what's already there, but identical rows in one file (two $2.90 bus fares on the same day) are both imported. Amounts like `$-5.00`, `(5.00)`, `5.00-` and `5.00 DR` are read as money out.
- **+ Add** – enter one by hand.

### Categories

Every transaction gets a category automatically: your own rules first, then a built-in list of common merchants (Kroger → Groceries, Shell → Gas & Transport, Netflix → Entertainment, …). Change one with the category dropdown in its row. With **Remember category choices for similar transactions** ticked, a rule is added at the same time, so future transactions from that payee (and existing uncategorized ones) get the same category. ⚠ **Uncategorized** in the filter shows what still needs a category.

Filter by text, category, account, date range, **tag**, **money in / out**, and **amount** (min / max, either direction); the totals above the table (in / out) cover everything that matches, not just the rows shown. **⬇ Export CSV** downloads everything that matches the filters (one row per split part, oldest first) — handy for taxes or a spreadsheet.

### Tags, notes and splits

The **✎** button on a row opens its details:

- **Tags** – free-form labels that cut across categories, e.g. `vacation`, `reimbursable`, `kids`. Type them comma-separated; they're saved lowercase with spaces turned into dashes (up to 10 per transaction). Tags show as chips under the description — click one to filter by it. Reports' Year in review totals spending by tag.
- **Notes** – anything you want to remember about it.
- **Split across categories** – put parts of one purchase in different categories, e.g. $80 of groceries and $40 of household items from one store trip. **+ Add part** starts with the whole amount in the current category; adjust the amounts until it says **✓ Adds up**. Each part counts toward its own category's budget and reports. A split transaction shows **⑂ Split** instead of a category dropdown; **Remove split** puts it back in one category (its largest part), and picking a single category for it also replaces the split. To change the amount of a split transaction, change the parts first.

### Bill payments in your transactions

After every import, outgoing transactions are compared with your bills. A transaction matches a bill when it's within 10 days before to 7 days after a due date and the amount fits:

- **Certain** – the amount fits *and* the description names the bill (or it's the same payee as an earlier confirmed payment). With *Mark bills paid automatically* on (Settings → Alerts), these are recorded right away.
- **Likely** – the exact amount near the due date, but the description doesn't say. These are listed under **🔗 Bill payments found in your transactions** (here and on the Dashboard) for you to confirm or dismiss.

Recording a match marks the bill paid **without moving money** — the payment already happened and your balances already reflect it. Matched transactions show a ✓ badge with the bill name; **undo** removes the match and the payment it recorded.

The **🔁 Repeating charges** list (also on the Bills page, §5) appears at the bottom.

---

## 9. Budgets

**Route:** `/budgets` · Spending by category for a month, against the budgets you set. Use ‹ › or the month picker to look at other months.

- **Plan for a typical month** – your expected monthly income and where it's planned to go: bills, category budgets, and what your goals need each month. What's left is **left to budget** — give it a job (raise a budget, start a goal); if budgets and goals add up to more than you earn, it says you're over-planned. Income and bills are converted to monthly amounts (a biweekly paycheck counts as 26 ÷ 12 a month; a yearly bill as 1/12).
- **Summary cards** – spending in budgeted categories vs. the total budgeted, all spending and income, your **learned everyday spending** (weekly, from the last 8 weeks), and how much is still uncategorized (with a link to fix it).
- **Category lines** – spent vs. budget with a progress bar. **On pace** compares how fast you're spending with how far through the month you are: "$X left — on pace for $Y" (amber) means you'll go over at this rate; red means you're already over. Refunds reduce spending. **Set budget / Change** edits a budget (blank or 0 removes it). Split transactions count each part in its own category.
- **Rollover** (envelope budgeting) – tick *Roll over* on an expense category with a budget and whatever you don't spend carries into next month; overspending comes out of next month instead. The line then shows *budget ± carried* and measures spending against what's **available**. The carry-over counts from your first month with transactions (up to 12 months back).
- **Suggested budgets** – your average spending per category over the last 3 full months, rounded up to $10. Listed only where it differs noticeably from the current budget; **Use** sets one, **Use all** sets them all.
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

## 11. Subscriptions & Recurring

**Route:** `/subscriptions` · Everything that charges you on a schedule, and what it costs per month and per year.

- **From transactions** – a payee that charged about the same amount (within 15%) at a regular interval (weekly, every 2 weeks, monthly, quarterly, or yearly), at least 3 times, and recently enough that it's still active. Charges matched to a bill are grouped under that bill.
- **Bills** – your bills (not card or loan payments) that don't have matching transactions yet.
- **Price increases** – when the latest charge is more than 5% above the usual amount, it's flagged (▲) with what it costs extra per year.

The cards show the monthly and yearly total. **🔁 Repeating charges that aren't bills yet** (also on Bills and Transactions) is at the bottom so you can add them to your projections.

---

## 12. Net Worth & Assets

**Route:** `/net-worth` · Everything you own minus everything you owe.

- **What you own** – checking and savings, plus your **assets**: vehicles, investments, retirement accounts, property, cash and other savings, valuables. A mortgage's market value (Accounts page) counts as property, and an auto loan's vehicle value as a vehicle (losing value each year, in projections too), unless you've added an asset linked to that loan.
- **What you owe** – credit cards, mortgages, auto loans, student loans, other loans, and HELOCs.
- **+ Asset** – a name, type, and current value. Update the value now and then (**Edit**); every change is kept, and **History** shows how it has moved. Optionally link the loan against it (the car loan, the mortgage) to see your **equity** — the loan is still counted once, in debts.
- **Net worth over time** – from the snapshot taken every day (and whenever you change an asset).

Assets are included everywhere net worth appears (Dashboard, Reports).

---

## 13. Financial Health Check

**Route:** `/checkup` · A 0–100 score (with a letter grade) from up to seven checks, each with what it means and what to do about it. Checks without enough data are left out. It's a guide, not a credit score. The Dashboard's **Health Score** card links here.

| Check | Measures | Good |
|---|---|---|
| Savings rate | income left after spending (last 3 full months of transactions; otherwise your planned income, bills, and everyday spending) | 20% or more |
| Emergency fund | checking + savings ÷ a month of bills and everyday spending | 6 months |
| Debt-to-income | monthly debt payments ÷ monthly income | under 15% |
| Credit card utilization | card balances ÷ limits (loan-group members excluded) | under 10% |
| High-interest debt | card balances at 15% APR or more, compared with a month's income | none |
| Budgets kept | budget categories that stayed within budget last month | all of them |
| Net worth trend | change over about 3 months, from the snapshots | rising |

The three weakest areas are listed at the top as tips.

---

## 14. Timeline & Projection

**Route:** `/timeline` · Your plan, day by day, for every account.

Choose how far ahead to look (30, 60, 90, 180 days, or 1 year; the choice is shared with the Plan and What-if pages) and **Refresh**. It's the same year-long plan every page uses (§2 *Projections*), including the plan's money moves (§15). The subtitle says which plan it follows; click it to change the plan.

### Stat cards

| Card | Meaning |
|---|---|
| Money in | Paychecks, plus deposits that don't come from your accounts (benefits, contributions). |
| Money out | Everything else that left your cash: bills, card and loan payments, everyday spending and fees. **Money in − money out = the change in your cash**, shown underneath. Moves between your own accounts cancel out. |
| Lowest checking | Your tightest point (all checking accounts together), its date, and your cushion. When the plan parks money in savings, a second line shows the low point counting that money, which is what Safe to spend uses. |
| Net worth at the end | Cash − card, mortgage and HELOC balances + homes, cars and other assets, the same way as the Net worth page. |

### Balance Over Time chart

**Net worth** (filled), **Cash (Checking/Savings)** (dashed), and **Total Debt** (shown below zero). Tick **Per-account lines** to add a line for each bank account, card, and HELOC.

### Calendar, list, by month, or end balances

The bottom card switches between four views (your choice is remembered):

- **Calendar** — described below.
- **List** — every event in the period grouped by day, with the cash in checking and savings after each day. Filter to **Income**, **Bills**, **Cards & loans** or **Transfers**.
- **By month** — income, bills and payments, everyday spending, the net change, and cash and debt at the end of each month (at least 60 days are shown).
- **End balances** — every account's balance on the last day, grouped by type, with other assets and a Net worth total.

**Download** (top right) saves the events, the month-by-month table or the daily balances as CSV/Excel, the bills & paydays calendar file, or prints the page.

### Financial Calendar

A month grid with ‹ / › navigation. Each day shows colored dots — **green** income, **red** payments, **blue** plan transfers, **amber** deferred payments — and today is outlined. Click a day to see:

- **Transactions** – each event with its source account and amount. A deferred payment shows "⚠️ Insufficient funds — payment deferred": the projection found no account able to cover it that day.
- **Expected Account Balances (End of Day)** – every account after that day's events, plus the net total.

---

## 15. Plan (Payment Optimizer)

**Route:** `/optimizer` · Your plan for paying every bill and using your money. In the sidebar it's **Plan** (it used to be called the Optimizer). The Dashboard, Timeline, What-if, alerts and the daily email all follow it.

The picker at the top right sets how far ahead to show (30 days – 1 year, shared with the Timeline and What-if). It doesn't change the plan, only how much of it you see. The page compares two versions of the same period and explains the difference in plain language:

- **On due date**: every bill comes out of its usual account on the day it's due, and nothing else moves.
- **The plan**: the same bills, plus the plan's moves (below).

**The plan is never worse than paying on due dates.** Every move is tested in a full day-by-day simulation of your accounts over the next year, and it's only kept if it leaves you better off. A plan also may not add a late payment or a fee, or take checking below your cushion (Settings → Planning), or below the lowest point paying on due dates would reach. If nothing helps, the plan *is* "pay everything on its due date".

Nothing is changed: it's advice.

### Choosing the goal

**Aim for** picks the plan **the whole app follows**. It's saved on the server (it's also in Settings → Planning as *Plan to follow*), so every device sees the same plan. The Dashboard's Safe to spend card and the Timeline show which plan they follow.

- **Most cash** (the default) — keep as much money on hand as possible; bills are paid on their due dates unless moving money is worth it.
- **Least interest** — pay interest-bearing debt as early as makes sense after each paycheck.
- **Pay off a card** — pick a card with a balance; spare cash goes to it a couple of days after each paycheck.

Every goal keeps the same safety rules (no extra late payments or fees, checking never below your cushion). **Compare goals** shows each goal's plan for the period side by side: late payments, lowest checking, cash and debt at the end, interest paid, fees, and how much extra would go to cards. **Use** switches to that goal.

### What the plan does

- **Pay down costly debt** – money checking won't need for the rest of the period goes onto your highest-rate card (just before its statement day) or HELOC, which costs more than the money earns sitting in checking or savings.
- **Savings sweeps** – parks spare checking money in savings to earn interest, and **recalls** it before bills need it.
- **HELOC parking** – if you have a HELOC in its draw period, temporarily pays it down with spare cash (cutting interest) and draws it back before bills are due.
- **Promo payoffs** – each card payment gives every 0% promo its share first (what's left, split over the payments before it expires). If that isn't enough, the plan pays the promo off before it expires, so deferred interest never hits.
- **Covering a missed payment** – when a bill can't be paid on its due date, moves the money from savings or draws on a HELOC, if that beats paying it late and the late fee.
- **Extra payments toward a chosen card** – with the *Pay off a card* goal.

"Spare" means money a checking account never needs again in the year ahead, after its lowest point and your cushion, so a move can't leave a later bill short.

Interest everywhere is worked out on the **average daily balance**, like banks and card issuers do. Moving money the day before interest is paid doesn't earn (or save) a whole month: what counts is how long the money sits there.

### The tabs

The page has four tabs (the one you pick is remembered and kept in the address, so you can link to it). Old links (`/debt-payoff`, `?tool=...`) open the matching tab. A red count on **Bills** or **Debt** means something there needs attention.

#### Overview

**Headline**: one sentence on where you stand, for example *"All 11 upcoming payments are covered on time. Following the optimized plan leaves you $86.52 better off over 90 days."* or *"1 payment can't be covered as things stand: the first is Roof on Oct 28."* Below it is a bullet list of what the plan changes. The left border is red if something is urgent, amber for warnings, and green otherwise.

**🧭 What to do**: a ranked list of cards with a dollar badge (**saves $X** is money gained or avoided; **risk $X** is money at risk):

| | Kind | Example |
|---|---|---|
| 🚨 | Urgent | A bill that can't be paid on its due date, how short you are, and how to fix it. Also a loan group whose payment doesn't cover its interest. |
| ⚠️ | Warning | A bill that's only on time if you follow the plan; checking getting thin (below your cushion); a promo the plan can't clear in time. |
| 💡 | Saves money | Pay interest-bearing debts on payday; point a loan group at its highest-rate loan; let idle cash work between paychecks. |
| 📈 | Tip | An extra $50/month on a loan group; plan ahead for a promo that expires after this period. |
| ✅ | Good | A promo that's on track; *"Every bill is covered on time."* |

**🔁 What the plan does**: summary tiles for each kind of move (total, count, and why). **Every move, by date** opens the full list. If there are none: *"paying each bill on its due date is already the best plan for this period."*

**⚖️ Paying on due dates vs. the plan**: a side-by-side table. The **Difference** column is green when the plan is better and red when it's worse. **How the plan is made** explains the two columns.

| Row | Meaning |
|---|---|
| Late or missed payments | Bills there isn't enough money for on their due date. |
| Lowest checking balance | Your tightest point in the period, with the account and date. All checking accounts together. The plan often lowers this on purpose: it puts idle cash to work, but never below your cushion. |
| Cash at the end / Debt at the end | Bank balances / cards + loans + HELOC + mortgage at the end of the period. |
| Interest charged / earned | On cards and HELOCs / on savings and checking. |
| Late & overdraft fees | Shown when either plan would pay any (rates from Settings → Planning and each bill's late fee). |
| Deferred promo interest at risk | Shown only when a 0% promo still has money owed at the end. It's the most that could be charged if that balance isn't paid before the promo expires. If the card has another payment due before the promo ends, that payment can still clear it, so it's a risk rather than a cost. If not, the interest is counted in the bottom line. |
| Unpaid bills | Shown when a bill can't be paid by the end of the period. It's still owed, so it counts against the bottom line. Skipping a bill isn't saving money. (A bill that can't be paid on its due date is paid late, once there's money; the plan avoids that whenever it can.) |
| **Overall** | **The bottom line:** cash − debt − unpaid bills (and promo interest no payment is left to prevent). Moving cash onto a debt lowers both cash and debt, so judge the plan by this row. It's never lower for the plan. |

**🔧 Plan checks** (collapsed): the plan's raw technical messages (❌ problems, ⚠ warnings, ⓘ notes) for anyone who wants the detail.

#### Bills

**🗓️ When to pay each bill**: every payment due in the next 45 days, plus any late payment later in the period. Tick **Only bills that need attention** to hide the routine ones.

| Column | Meaning |
|---|---|
| Due / Bill | Due date, name, kind (bill, variable bill, card payment, mortgage, HELOC payment, loan group) and the account it comes from. `~` marks an estimated amount. |
| Status | **On time**, **Paid** (that due date is already paid), **Short** (not enough money on the due date), or **On time with plan** (short if paid on the due date, fine if you follow the optimized plan). |
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

**Better due dates** – for each monthly bill, tries due days just after your paydays and lists the moves that fix a late payment or raise your lowest balance (measured after the first month, once the new date settles in). Ask the company to move it, then click **I moved it** to update the bill.

#### Debt

**🏷️ 0% promo deadlines**: each promo's balance, expiry date, monthly amount needed to clear it in time, and the deferred interest at stake if it isn't. Status is checked against the whole year-long plan: **On track** (the plan clears it), **Short $X**, or **After this window** (expires more than a year out). A promo the plan can't clear also raises an urgent alert.

**Pay down debt faster** – the most you can put toward debt each month, on top of your bills, without checking dropping below your cushion (or the lowest point paying minimums would reach) and with nothing late. It tries amounts and narrows in to the nearest $10. Pick **Highest interest first** (avalanche) or **Smallest balance first** (snowball) and how far ahead (3 months – 2 years). It shows the interest saved, debt at the end, your lowest checking balance, each debt's extra payments and payoff date, and how the other order compares. Type an amount in **Try** to test your own; too much is flagged.

**📦 Loan group cards** (one per group): how the next group payment is split across its loans (balance, APR, monthly interest, share of the payment). Next to that, a comparison of three choices: payoff time and total interest.

- **Keep the current split**: your group's allocation settings.
- **Send extra to the highest rate first**: each loan gets its interest covered and everything else goes to the highest-APR loan. If this saves money, the card tells you the **Fixed** amount to set on the Bill Groups page for that loan. Your servicer also has to apply payments that way, so ask them.
- **Pay $50 more each month**: with the current split.

If the group payment doesn't even cover the monthly interest, the card says the balance will grow.

**When will I be debt-free?** (this used to be the Debt Payoff page) – a long-run estimate, month by month until everything is paid off. Drag **Extra each month** ($0 – $2,000, in $25 steps; default $200); results update half a second after you stop.

- **Debts included:** credit cards with a balance (not in a group), HELOCs with a balance, and each loan group as one debt (balance-weighted APR, group payment as its minimum). Mortgages are excluded. Debts whose next payment is already marked paid are left out.
- **Every strategy uses the same monthly budget** = sum of all minimums + the extra amount. When a debt is paid off, its minimum rolls into the next target.

| Strategy | Extra money goes to |
|---|---|
| Minimum only | Nowhere — minimums only (the extra amount is not used). |
| Highest interest first | The highest-APR debt first (avalanche) — usually the least interest. |
| Smallest balance first | The smallest balance first (snowball) — quickest wins. |

Each card shows the time to debt-free, total interest, total paid, savings vs. minimum only, and (under **Payoff order**) the order debts are cleared. If a strategy **never pays off** at that budget (minimums barely cover interest), it says so and shows the balance remaining. The chart plots the remaining debt for all three by month. Unlike the rest of the page, this is a simple estimate at fixed payments, not the day-by-day plan.

#### Can I afford it?

**When can I buy it?** – read from the plan the same way as Safe to spend: **Safe to spend today** is the Dashboard's figure. A chart shows how much you could spend on each day ahead (the lowest point the plan reaches over the look-ahead from that day, minus your cushion and what's already spoken for), and the earliest day a purchase of the amount you type fits.

---

## 16. Debt Payoff Estimator

Now part of the Plan page: **Plan → Debt → When will I be debt-free?** (§15). The old `/debt-payoff` address opens it.

---

## 17. What-If Scenarios

**Route:** `/scenarios` · Test a change before you make it. Nothing you do here is saved.

Both sides follow your plan: **Your plan now** is the same plan as every other page, and the scenario re-makes the plan for the changed situation (same goal, same rules). How far ahead to compare comes from the picker at the top right, shared with the Timeline and Plan pages.

### Building a scenario (left panel)

- **Quick Presets** (each replaces the current changes):
  - **Job Loss** – sets the chosen income to $0.
  - **10% Raise** – raises the chosen income by 10%.
  - **New $200 Bill** – adds a $200 monthly bill due on the 15th.
  - **Cut Bills 20%** – reduces every regular bill by 20%.
- **Add Bill** – name, amount, due day (1–31, monthly).
- **Remove Payments** – drop a bill, card, mortgage, HELOC, or loan group (cards/HELOCs/mortgages are treated as paid off).
- **Adjust Income** – set a source's amount (0 = no income).
- **Remove Income** – drop an income source.

The **Modifications** list shows every change; click × to undo one. **Run Scenario** calculates; **Reset** clears everything.

### Results (right panel)

- **Verdict**: a one-line answer with a colored border.
  - **Red**: *"2 bills couldn't be paid on time in this scenario"*, or *"Checking would be overdrawn"*.
  - **Green**: *"You'd be $X better off"*.
  - **Amber**: *"Every bill still gets paid, but you'd be $X worse off"*.
- **What changes**: plain-language bullets on how the scenario differs from your plan now. They cover being better or worse off, more or fewer late payments, how far your lowest checking balance moves (and when), and interest charged and earned.
- **Comparison table**, your plan now vs. the scenario: late or missed payments, lowest checking balance, cash and debt at the end, interest charged, late & overdraft fees, and **Overall (cash − debt)**. Green means better and red means worse.
- **Payments that would be late or missed**: the specific bills and dates the scenario breaks.
- A **chart**, *Your plan now vs. with the change*, day by day.

---

## 18. Reports

**Route:** `/reports` · Built from your transactions. Choose 3, 6, or 12 months.

- **Averages** – monthly income, spending, and what's left over (full months only, starting from your first month with transactions).
- **Income vs. spending** – a bar per month. Transfers between your own accounts aren't counted; the current month is partial.
- **Where the money went** – a chart and table of spending by category for the month you pick, compared with your average for each category (▲ / ▼).
- **Category trends** – each category month by month.
- **Net worth** – from the daily snapshots, once there are at least two.
- **🗓 Year in review** – pick a year (‹ ›): income, spending, what you saved and your savings rate, the average month and the biggest one, a month-by-month chart, top categories (with their share), the payees you spent the most with, your biggest purchases, and spending by tag.

---

## 19. Alerts

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

**Daily email digest** (Settings → Alerts) – a designed morning email with the status, Safe to spend, checking and the lowest point ahead, alerts, this pay period's bills, paychecks coming in, benefits (and when they run out), budgets and optimizer tips. A plain-text version is included for email apps that don't show HTML. If you set the app address, it has an **Open your budget** button. It needs an email account's SMTP settings; it's sent after 7am by the running API server, so the app has to be running.

**Phone notifications** (Settings → Alerts) – urgent alerts (and, if you like, warnings and a short morning summary) pushed to your phone through the free [ntfy](https://ntfy.sh) app, once each. They're sent by the running server, so they arrive even when no browser has the app open.

---

## 20. Settings

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
- **Daily email digest** – *Send to*, the SMTP server, port, username, and password (for Gmail: `smtp.gmail.com`, port 587, your address, and an *app password*). The password is stored but never shown again. **Send a test digest now** saves and sends one immediately; **Preview digest** shows today's email as it will look (switch to **Plain text** for the text version).
- **Phone notifications** – install the ntfy app, subscribe to a topic with a hard-to-guess name (anyone who knows the name can read it), and paste its URL, e.g. `https://ntfy.sh/budget-k3j9x2`. A self-hosted ntfy server works too; for a protected topic add its *access token* (stored, never shown again). Choose *warnings and urgent alerts* or *only urgent*, and optionally *a short summary every morning*. *App address* (e.g. `https://budget.example.com`) makes tapping a notification open the right page. **Send a test notification** saves and sends one.

### 💾 Data & backup

- **⬇ Export to Excel** – accounts, bills, income, promos, and loan groups in a spreadsheet that can be imported back.
- **⬇ Blank template** / **⬆ Import from Excel** – fill in the template (example rows marked `EXAMPLE` are skipped) and import it. Importing only adds new items; anything with the same name is skipped.
- **⬇ Transactions (CSV)** – every transaction with its category and matched bill.
- **⬇ Download backup** – a complete copy of the database (everything, including transactions, budgets, goals, and settings). Keep one somewhere safe.
- **⬆ Restore from backup** – replaces **all** current data with a backup file. A copy of the current data is saved to the server's backups folder first.
- **Automatic backups on the server** (admins) – a copy of the database is made every day after the hour you choose, and the newest ones are kept (14 by default). **Back up now** makes one immediately. The list shows automatic, manual and *before a restore* copies, each with **Download**, **Restore** and **Delete**.

### 🔒 Your account

Everyone signs in with their own username and password, on every device (this computer included), and stays signed in for 30 days on each. Everyone with an account sees and edits the **same** budget.

- **Change password** needs your current password and signs you out on your other devices.
- **Sign out** (here, or at the bottom of the menu) signs out this browser.
- **Signed-in devices** lists every browser or phone signed in to your account — what it is, its network address, when it was last active. **Sign out** ends one; **Sign out all other devices** ends all but this one (handy after losing a phone).

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

**Sync automatically** (every 1–24 hours, or off) has the server fetch balances on its own — and, with *also download new transactions*, new transactions too, matching bill payments as they arrive. The last automatic sync's result is shown underneath.

Mapped accounts show 🔄 across the app and get a **Txns** button on the Accounts page. **✕** unmaps an account; **Disconnect** removes the connection and all mappings. Only mapped accounts are updated. To store transactions (for budgets, reports, and bill matching), use **Download from SimpleFIN** on the Transactions page (§8).

### ⏱ Background jobs (admins)

While the server runs it checks every couple of minutes for work, and this card shows each job's last result:

| Job | What it does |
|---|---|
| Daily upkeep | Records today's net worth for Reports |
| Automatic backup | The daily backup above |
| SimpleFIN sync | If *Sync automatically* is on |
| Email digest, Phone notifications, Morning summary | If set up under Alerts |

A job that fails shows ⚠ with the reason; it's tried again later and never stops the others.

### Database

- **Save to Database** – writes everything to disk. Normally unnecessary (every change is saved automatically).
- **Load from Database** – reloads from disk, discarding anything not yet saved.

### API Connection

Shows whether the web UI can reach the API server, plus counts of banks, bills, and income sources. **Check Status** re-tests.

### About

The API endpoint and a link to the **GraphQL Playground**, an interactive console for the API (useful for developers).

---

## 21. Activity

**Route:** `/activity`

Every change anyone makes to the budget, newest first, grouped by day: who did it, when, and what (e.g. *casey · Create bill — Internet · $70.00*). Sign-ins, invites, password changes, backups and restores are listed too. Pick a person at the top to see only their changes; **Show older** loads more. Passwords, tokens and other secrets are never recorded. Entries are kept for a year.

---

## 22. Using it on your phone, and installing it

**From your phone or another computer on your network:**

1. Sign in as **admin**. The first time the API server starts it creates that account with a random password, printed in the server's output and saved in `~/.budget_app/initial-admin-password.txt` until you change it. Change it in *Settings → Your account* (a reminder shows until you do), or from a shell on the server:

   ```bash
   curl -X POST http://localhost:4000/auth/password -H 'Content-Type: application/json' \
        -d '{"username": "admin", "current_password": "<generated>", "new_password": "<yours>"}'
   ```
2. Find that computer's network address (on Windows: `ipconfig`, look for *IPv4 Address*, e.g. `192.168.1.20`).
3. On your phone, open `http://192.168.1.20:3000` and sign in.
4. To add someone else, create an invite link in *Settings → Users* (§20). Invite links use the address you're on, so create them from the network address (not `localhost`) if the link is for another device.

**Installing it as an app:** in Chrome or Edge, use *Install app* (in the address bar or menu); on iPhone, *Share → Add to Home Screen*. It opens in its own window with its own icon. Full install with offline start needs the app to be served from `localhost` or over HTTPS; from a plain `http://` network address, adding it to the home screen still works as a shortcut.

> The app has no HTTPS of its own. On your home network sign-in keeps others out, but don't expose it to the internet without putting it behind something that adds HTTPS.

---

## 23. Recommended routine

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
3. **Open the Plan page** and work through *What to do*: fix anything **Short**, pay card/loan payments on payday where it saves money, check promo deadlines.
4. Add any **repeating charges** suggested on the Bills page.
5. **Download a backup** (Settings → Data & backup).
6. Occasionally revisit **Plan → Debt** and **What-if** for bigger decisions.

---

## 24. Troubleshooting & FAQ

**The web page loads but shows errors / no data.**
The API server isn't running or isn't reachable. Check Settings → API Connection, and make sure the "Budget API Server" window is open (or run `python api_server.py`).

**`start.bat` fails with "python313.dll" or similar.**
The virtual environment was built with a Python version that has since been uninstalled. Delete the `.venv` folder and recreate it: `py -3.13 -m venv .venv` (or use `uv venv`), then run `start.bat` again.

**A projection shows a payment as Deferred.**
On that day, no checking account had enough money for it. Look at the Timeline calendar for that day, then add income, move money, or change the payment's source.

**Why is my credit card "minimum payment" higher than my statement says?**
It includes enough to pay off each 0% promo before it expires (see §2). Pay at least your statement minimum in real life; the app's figure is what keeps you clear of deferred interest. If the card has no promo and the figure is still off, use **Match minimum payment** so the app uses your issuer's formula.

**I marked something paid by mistake.**
On Bills → **By month**, find the due date and choose ⋯ → **Undo payment**. If the app took the money out, it's put back.

**Can I import my data from a spreadsheet?**
Yes: *Settings → Data & backup* → **Blank template**, fill it in, then **Import from Excel** (the command-line menu, `python cli.py`, can do the same). Template example rows are marked `EXAMPLE` and skipped. Importing skips items that already exist.

**Safe to spend seems too high.**
Check that everyday spending is set (the Dashboard warns if it isn't), and that bills you've already paid are marked paid — and ones you haven't, aren't. Open *How this is worked out* under the number to see each piece.

**A bill payment was matched to the wrong bill.**
Click **undo** on the transaction's ✓ badge (Transactions page). That removes the payment it recorded; then confirm the right bill or mark it paid by hand.

**A bill shows as overdue but I paid it.**
Mark it paid (Dashboard checklist or Bills → Pay) with the date you paid, and leave *Take the money out* off if your balance already reflects it.

**What's the admin password?**
The one printed when the API server first started, also in `~/.budget_app/initial-admin-password.txt` until you change it (§22). If it's gone, run `python -m models.auth reset-password admin` on the server.

**My phone says the app isn't set up yet.**
No account exists yet — this happens only if the API was started some other way than `python api_server.py`. Open the app on the computer that runs it and create the first account there, or restart the server with `python api_server.py`.

**I forgot my password.**
Ask an admin for a reset link (*Settings → Users → Reset password*). If you're the only admin, on the computer that runs the app run `python -m models.auth reset-password <your username>` from the project folder (`python -m models.auth users` lists the usernames).

**I used a password before accounts existed.**
It still works: sign in with the username **admin** and your old password. You can then invite others and, if you like, create yourself a new admin account.

**Restoring a backup went wrong.**
The data that was replaced is in `~/.budget_app/backups/before-restore-<date-time>.db` — restore that file the same way.

**Where are the numbers for projections coming from?**
Everything is computed from what you've entered: balances, income schedules, bills, and account terms. Keep balances current for accurate forecasts.
