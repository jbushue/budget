// ── Enums ────────────────────────────────────────────────────────────

export type AccountType = 'checking' | 'savings' | 'money_market' | 'cd' | 'cash' | 'prepaid' | 'wallet'
  | 'ebt' | 'hsa' | 'fsa' | 'investment' | 'retirement' | 'other'
export type AccountGroup = 'cash' | 'savings' | 'benefits' | 'invested' | 'other'
export type BillTypeEnum = 'fixed' | 'floating' | 'credit_payment' | 'mortgage_payment' | 'heloc_payment'
export type BillFrequency = 'once' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'semi_annual' | 'yearly'
export type IncomeFrequency = 'once' | 'weekly' | 'biweekly' | 'monthly' | 'semimonthly' | 'bimonthly' | 'quarterly' | 'yearly'
export type CreditStatus = 'active' | 'closed' | 'frozen'

// ── Models ───────────────────────────────────────────────────────────

export interface BankAccount {
  id: string
  accountName: string
  accountType: AccountType
  balance: number
  interestRate: number
  interestAccrualDate: number | null
  kindLabel?: string
  kindGroup?: AccountGroup
  paysBills?: boolean
  refillAmount?: number
  refillDay?: number | null
  weeklySpending?: number
  offsetsEveryday?: boolean
}

export interface AccountKindInfo {
  value: AccountType; label: string; group: AccountGroup; pays_bills: boolean; earns: boolean
  purpose?: string; hint: string
}

export interface OtherMoney {
  bank: string; account: string; type: AccountType; label: string; group: AccountGroup; balance: number
  purpose: string; refill_amount: number; next_refill: string | null; weekly_spending: number; runs_out: string | null
}

export interface PromoOffer {
  promoName: string
  monthsInterestFree: number
  purchaseLimit: number | null
  startDate: string | null
  endDate: string | null
  amountUsed: number
  promoBalance: number
  isActive: boolean
  daysRemaining: number
  interestCharged: boolean
}

export interface CreditAccount {
  id: string
  accountName: string
  balance: number
  regularBalance: number
  creditLimit: number
  availableCredit: number
  interestRate: number
  paymentDueDate: number | null
  statementDate: number | null
  status: CreditStatus
  minimumPayment?: number | null
  /** How the minimum is worked out (null: the default rule) */
  minRule?: Record<string, number | boolean> | string | null
  minRuleLabel?: string | null
  promoOffers: PromoOffer[]
}

export interface MortgageAccount {
  id: string
  accountName: string
  originalPrincipal: number
  currentPrincipal: number
  interestRate: number
  loanTermMonths: number
  paymentDueDate: number
  totalMonthlyPayment: number
  monthlyPrincipal: number
  monthlyInterest: number
  escrowMonthly: number
  preferredSourceBank: string | null
  preferredSourceAccount: string | null
  status: string
  startDate: string | null
  marketValue: number | null
  equity: number | null
  escrowPropertyTax: number
  escrowInsurance: number
  escrowPmi: number
  escrowHoa: number
  escrowOther: number
}

export interface HELOCAccount {
  id: string
  accountName: string
  creditLimit: number
  balance: number
  availableCredit: number
  interestRate: number
  drawPeriodMonths: number
  totalTermMonths: number
  startDate: string | null
  drawEndDate: string
  maturityDate: string
  currentPhase: 'draw' | 'repayment' | 'paid_off'
  minimumPayment: number
  monthlyInterest: number
  paymentDueDate: number
  preferredSourceBank: string | null
  preferredSourceAccount: string | null
}

export interface Bank {
  name: string
  bankType: string
  bankAccounts: BankAccount[]
  creditAccounts: CreditAccount[]
  mortgageAccounts: MortgageAccount[]
  helocAccounts: HELOCAccount[]
  totalBalance: number
  totalCreditLimit: number
  totalAvailableCredit: number
}

export interface BillItem {
  id: string
  billName: string
  amount: number
  dueDate: number
  dueMonth: number | null
  billType: BillTypeEnum
  frequency: BillFrequency
  minAmount: number | null
  maxAmount: number | null
  startDate?: string | null
  lateFee?: number | null
  nextDueDate: string
  preferredSourceBank: string | null
  preferredSourceAccount: string | null
  isPaidThisPeriod: boolean
  estimatedAmount: number | null
  actualAmount: number | null
  hasActualAmount: boolean
  amountHistory?: number[]
  carryoverBalance: number
  effectiveAmount: number
  isAccountLinked: boolean
  linkedBankName: string | null
  linkedAccountName: string | null
  linkedAccountType: string | null
  /** The due date a payment goes to now (oldest still owed, else the next) */
  nextUnpaidDue?: string | null
  overdueCount?: number
}

export interface BalanceHistoryEntry {
  bankName: string
  accountName: string
  accountType: string
  balance: number
  previousBalance: number | null
  recordedAt: string
  notes: string | null
}

export interface CreditPaymentDue {
  id: string
  bankName: string
  accountName: string
  balance: number
  minimumPayment: number
  paymentDueDate: number | null
  interestRate: number
  creditLimit: number
  availableCredit: number
  status: string
  isPaidThisPeriod: boolean
  lastPaymentAmount: number | null
  lastPaymentDate: string | null
}

export interface IncomeItem {
  id: string
  sourceName: string
  amount: number
  frequency: IncomeFrequency
  payDates: number[]
  startDate?: string | null
  nextPayDate: string
  distribution: Record<string, number | null> | null
  distributionDetail?: string | Record<string, { value: number | null; type: string }> | null
}

export interface BalanceSnapshot {
  date: string
  balances: Record<string, number>
  creditBalances: Record<string, number>
  mortgageBalances: Record<string, number>
  helocBalances: Record<string, number>
  total: number
  netTotal: number
}

export interface CalendarEvent {
  eventType: string
  description: string
  amount: number
  sourceBank: string
  sourceAccount: string
  status: string
}

export interface CalendarDay {
  date: string
  events: CalendarEvent[]
  balances: Record<string, number>
  creditBalances: Record<string, number>
  mortgageBalances: Record<string, number>
  helocBalances: Record<string, number>
  total: number
  netTotal: number
}

export interface Projection {
  startDate: string
  endDate: string
  snapshots: BalanceSnapshot[]
  calendarDays: CalendarDay[]
  finalBalances: Record<string, number>
  creditFinalBalances: Record<string, number>
  mortgageFinalBalances: Record<string, number>
  helocFinalBalances: Record<string, number>
  totalFinalBalance: number
  totalCreditBalance: number
  totalMortgageBalance: number
  totalHelocBalance: number
  netFinalBalance: number
  totalIncome: number
  totalExpenses: number
  netChange: number
  otherAssets?: number
  lowestChecking?: number | null
  lowestCheckingDate?: string | null
  lowestSpendable?: number | null
  lowestSpendableDate?: string | null
  cushion?: number
  planGoal?: string
  planTarget?: string | null
}

export interface PaymentPlan {
  strategy: Record<string, any>
  discretionaryFunds: number
  totalInterest: number
  interestCharged?: number | null
  interestEarned?: number | null
  totalFees: number
  violations: string[]
}

export interface FinancialSnapshot {
  timestamp: string
  banks: Bank[]
  totalAssets: number
  totalLiabilities: number
  netWorth: number
  upcomingBills30Days: BillItem[]
  upcomingIncome30Days: IncomeItem[]
}

// ── SimpleFIN ────────────────────────────────────────────────────────

export interface SimplefinStatus {
  isConnected: boolean
  createdAt: string | null
  lastSyncAt: string | null
  mappedAccountCount: number
}

export interface SimplefinSyncedAccount {
  bankName: string
  accountName: string
  accountType: string
  sfinName: string
  sfinOrg: string
}

export interface SimplefinAccount {
  id: string
  name: string
  orgName: string
  orgDomain: string | null
  currency: string
  balance: number
  availableBalance: number | null
  balanceDate: string | null
  mappedBankName: string | null
  mappedAccountName: string | null
  mappedAccountType: string | null
}

export interface SimplefinTransaction {
  id: string
  posted: string
  amount: number
  description: string
  payee: string | null
  memo: string | null
}

// ── Enhancement Types ──────────────────────────────────────────────

export type AllocationMethod = 'proportional' | 'fixed' | 'equal'

export interface BillGroupMember {
  bankName: string
  accountName: string
  allocationMethod: AllocationMethod
  fixedAmount: number
  balance: number
  interestRate: number
}

export interface BillGroup {
  groupName: string
  totalPayment: number
  dueDate: number
  frequency: BillFrequency
  groupType: string
  preferredSourceBank: string | null
  preferredSourceAccount: string | null
  isPaidThisPeriod: boolean
  members: BillGroupMember[]
  totalBalance: number
  memberCount: number
}

export interface SafeToSpend {
  safeToSpend: number
  totalChecking: number
  committedBills: number
  upcomingIncome: number
  nextIncomeDate: string
  horizonDate: string
}

export interface NetWorthSnapshot {
  snapshotDate: string
  totalAssets: number
  totalLiabilities: number
  netWorth: number
}

export interface BillPaymentHistory {
  billName: string
  amountPaid: number
  sourceBank: string
  sourceAccount: string
  paymentDate: string
  dueDate?: string | null
}

/** paid | partial | skipped | none (nothing owed) | overdue | unpaid | untracked (before tracking began) */
export type OccurrenceStatus = 'paid' | 'partial' | 'skipped' | 'none' | 'overdue' | 'unpaid' | 'untracked'

/** One due date of one bill (the Bills month view). */
export interface BillOccurrence {
  billName: string
  displayName: string
  kind: 'bill' | 'floating' | 'credit' | 'mortgage' | 'heloc' | 'group'
  dueDate: string
  amount: number
  paid: number
  remaining: number
  status: OccurrenceStatus
  paidOn: string | null
  sourceBank: string
  sourceAccount: string
  isFloating: boolean
  hasActualAmount: boolean
  estimatedAmount: number | null
  bankName: string | null
  accountName: string | null
  groupName: string | null
  balanceOwed: number | null
  payments: { date: string; amount: number; sourceBank: string; sourceAccount: string; movedMoney: boolean | null }[]
}

export interface BillMonth {
  month: string
  firstMonth: string
  lastMonth: string
  overdueBefore: number
  totals: { due: number; paid: number; remaining: number; overdue: number }
  occurrences: BillOccurrence[]
}

export interface DebtPayoffStrategy {
  strategy: string
  monthsToPayoff: number
  totalInterestPaid: number
  totalPaid: number
  payoffOrder: string[]
  paysOff?: boolean | null
  remainingBalance?: number | null
  monthlyBreakdown: string | any[]
}

export interface DebtPayoffComparison {
  minimum: DebtPayoffStrategy
  avalanche: DebtPayoffStrategy
  snowball: DebtPayoffStrategy
}

export interface LatePayment {
  date: string
  name: string
  amount: number
}

/** Headline numbers for one simulated plan. */
export interface OutcomeSummary {
  endingCash: number
  endingDebt: number
  netPosition: number
  netChange: number
  lowestChecking: number | null
  lowestCheckingDate: string | null
  lowestCheckingAccount: string | null
  interestCharged: number
  interestEarned: number
  paymentsOnTime: number
  pendingDeferredInterest: number
  fees: number
  everydaySpending: number
  /** Bills that couldn't be paid in the window — still owed */
  unpaidBills: number
  /** Deferred promo interest on promos that expire before the card's next payment */
  imminentPromoInterest: number
  /** The bottom line: cash − debt − unpaid bills − imminent promo interest */
  outcome: number
  latePayments: LatePayment[]
}

export interface WhatIfResult {
  baselineFinalBalance: number
  scenarioFinalBalance: number
  difference: number
  baselineSnapshots: string | any[]
  scenarioSnapshots: string | any[]
  changes: string[]
  baseline: OutcomeSummary
  scenario: OutcomeSummary
}

export type PeriodBillStatus = 'paid' | 'covered' | 'covered_by_plan' | 'short' | 'overdue'

export interface PeriodBill {
  name: string
  /** Name to pass to markBillPaid */
  billName: string
  kind: string
  dueDate: string
  amount: number
  status: PeriodBillStatus
  shortBy: number
  daysOverdue: number
  sourceAccount: string
}

export interface DashboardSummary {
  nearLowest?: number
  heldForLater?: number
  heldFor?: string | null
  planSeries?: string | null
  parkedAtLowest?: number
  lookaheadDays?: number
  planGoal?: string
  planTarget?: string | null
  otherMoney?: string | null
  status: 'ok' | 'warning' | 'danger'
  statusTitle: string
  statusDetail: string
  safeToSpend: number
  safePerDay: number
  lowestBalance: number
  lowestDate: string | null
  checkingNow: number
  cushion: number
  overdueTotal: number
  shortTotal: number
  goalReserves: number
  everydayWeekly: number
  spendingMode: 'manual' | 'learned'
  nextPayday: string | null
  horizon: string
  coveredThrough: string
  headline: string
  billsThisPeriod: PeriodBill[]
  upcomingIncome: { date: string; name: string; amount: number }[]
  insights: Insight[]
}

/** App settings as returned by the `settings` query (secrets omitted). */
export interface AppSettings {
  optimizer_goal: string
  optimizer_target: string
  lookahead_days: number
  cushion: number
  spending_mode: 'manual' | 'learned'
  everyday_weekly: number
  spending_account: string
  card_late_fee: number
  default_late_fee: number
  overdraft_fee: number
  auto_match_bills: boolean
  dismissed_recurring: string[]
  alert_days_before_due: number
  alert_low_balance: boolean
  browser_notifications: boolean
  email_enabled: boolean
  email_to: string
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_use_tls: boolean
  smtp_password_set: boolean
  push_enabled: boolean
  ntfy_url: string
  ntfy_token_set: boolean
  push_min_severity: 'warning' | 'danger'
  push_daily_summary: boolean
  public_url: string
  auto_backup: boolean
  backup_hour: number
  backup_keep: number
  last_backup_date: string
  simplefin_auto_sync_hours: number
  simplefin_auto_import: boolean
  last_simplefin_sync: string
  last_simplefin_result: string
  [key: string]: unknown
}

/** Last result of each background job (models/jobs.py) */
export interface JobStatus {
  ok: boolean
  message: string
  at: string
}

export type InsightSeverity = 'urgent' | 'warning' | 'savings' | 'tip' | 'good'

export interface Insight {
  severity: InsightSeverity
  category: string
  title: string
  detail: string
  /** > 0 money saved/gained, < 0 money at risk */
  impact: number
  date: string | null
}

export interface BillTiming {
  name: string
  kind: 'bill' | 'floating' | 'credit' | 'mortgage' | 'heloc' | 'group'
  dueDate: string
  amount: number
  estimated: boolean
  sourceBank: string
  sourceAccount: string
  status: 'on_time' | 'late' | 'already_paid'
  planStatus: 'on_time' | 'late' | 'already_paid' | 'paid'
  fundedBy: string | null
  payEarlyDate: string | null
  daysEarly: number
  earlySavings: number
  cushionIfEarly: number | null
  shortfall: number
  fixes: string[]
  advice: string
}

export interface GroupPayoff {
  months: number | null
  interest: number | null
  paysOff: boolean
  extraMonthly?: number | null
}

export interface GroupOutlook {
  groupName: string
  payment: number
  totalBalance: number
  monthlyInterest: number
  members: {
    accountName: string
    balance: number
    apr: number
    allocationMethod: string
    nextPaymentShare: number
    monthlyInterest: number
  }[]
  current: GroupPayoff
  highestRateFirst: GroupPayoff
  withExtra: GroupPayoff
  reallocationSavings: number
  highestRateMember: string
  suggestedFixedAmount: number | null
}

export interface PromoOutlook {
  card: string
  bank: string
  promoName: string
  balance: number
  expires: string
  daysLeft: number
  monthlyNeeded: number
  scheduledInWindow: number
  onTrack: boolean | null
  shortfall: number
  interestAtRisk: number
  aprAfter: number
}

export interface OptimizerMove {
  date: string
  type: string
  title: string
  why: string
  description: string
  amount: number
}

export interface PaymentInsights {
  startDate: string
  endDate: string
  days: number
  headline: string
  netBenefit: number
  changes: string[]
  onDueDate: OutcomeSummary
  optimized: OutcomeSummary
  insights: Insight[]
  billTiming: BillTiming[]
  groups: GroupOutlook[]
  promos: PromoOutlook[]
  optimizerMoves: OptimizerMove[]
}

// ── GraphQL result wrappers ─────────────────────────────────────────

export interface MutationPayload {
  success: boolean
  message?: string | null
}

// ── Ledger (transactions, categories, budgets) ──

export interface LedgerTransaction {
  id: number
  date: string
  description: string
  payee: string
  amount: number            // negative = money out
  bankName: string
  accountName: string
  category: string | null
  source: 'simplefin' | 'csv' | 'manual'
  matchedBill: string | null
  notes: string
  tags: string[]
  splits: TransactionSplit[]   // set when split across categories (category is then null)
}

export interface TransactionSplit {
  category: string
  amount: number
  note: string
}

export interface TagCount {
  tag: string
  count: number
}

export interface SuggestedBudget {
  category: string
  average: number
  suggested: number
  current: number | null
  months: number
}

export interface TransactionPage {
  total: number
  totalIn: number
  totalOut: number
  items: LedgerTransaction[]
}

export interface Category {
  name: string
  kind: 'expense' | 'income' | 'transfer'
  isEveryday: boolean
  monthlyBudget: number | null
  color: string | null
  rollover: boolean
}

export interface CategoryRule {
  id: number
  pattern: string
  category: string
  priority: number
}

export interface BudgetLine {
  category: string
  color: string | null
  isEveryday: boolean
  budget: number | null
  spent: number
  remaining: number | null
  percent: number | null
  projected: number
  status: 'ok' | 'warning' | 'over' | 'no_budget'
  rollover: boolean | null
  carried: number | null     // rollover: left from earlier months (negative = overspent)
  available: number | null   // budget + carried
}

export interface BudgetStatus {
  month: string
  daysElapsed: number
  daysInMonth: number
  totalBudget: number
  totalSpent: number
  totalBudgetedSpent: number
  uncategorizedSpent: number
  income: number
  lines: BudgetLine[]
}

export interface SpendingMonth {
  month: string
  income: number
  spending: number
  net: number
  byCategory: string | Record<string, number>
}

export interface SpendingReport {
  colors: string | Record<string, string>
  months: SpendingMonth[]
}

export interface ImportResult extends MutationPayload {
  imported: number | null
  duplicates: number | null
  matchedBills: number | null
  errors: string[] | null
}

export interface CsvPreview {
  columns: string[]
  mapping: string | Record<string, number>
  rowCount: number
  errors: string[]
  rows: { date: string; description: string; amount: number; category: string | null }[]
}

// ── Goals, bill matching, recurring charges ──

export interface SavingsGoal {
  id: number
  name: string
  targetAmount: number
  savedAmount: number
  remaining: number
  progress: number
  targetDate: string | null
  monthsLeft: number | null
  monthlyNeeded: number | null
  perPaycheckNeeded: number | null
  onTrack: boolean | null
  bankName: string
  accountName: string
  inChecking: boolean
  linkedBill: string | null
  complete: boolean
}

export interface SinkingFundSuggestion {
  billName: string
  amount: number
  frequency: string
  nextDue: string
  monthly: number
}

export interface BillMatch {
  billName: string
  dueDate: string
  confidence: 'high' | 'medium'
  reason: string
  amount: number
  transaction: Pick<LedgerTransaction, 'id' | 'date' | 'description' | 'amount' | 'bankName' | 'accountName'>
}

export interface RecurringCharge {
  key: string
  name: string
  description: string
  frequency: string
  amount: number
  variable: boolean
  minAmount: number
  maxAmount: number
  count: number
  lastDate: string
  nextExpected: string
  dueDay: number
  category: string | null
  monthlyCost: number
}

// ── Alerts ──

export interface AlertItem {
  key: string
  severity: 'danger' | 'warning' | 'info'
  title: string
  detail: string
  link: string
  date: string
}

// ── Assets, net worth, planning ──

export interface Asset {
  id: number
  name: string
  kind: string
  kindLabel: string
  value: number
  notes: string
  linkedBank: string
  linkedAccount: string
  loanBalance: number | null
  loanKind: string | null
  equity: number
  updated: string | null
}

export interface KindValue {
  kind: string
  value: number
}

export interface NetWorthBreakdown {
  cash: number
  assetsByKind: KindValue[]
  debts: KindValue[]
  totalAssets: number
  totalDebt: number
  netWorth: number
  assets: Asset[]
  homes: { name: string; bank: string; value: number; owed: number }[]
}

export interface MonthlyPlan {
  income: number
  bills: number
  debtPayments: number
  budgets: number
  goalSaving: number
  leftToBudget: number
  status: 'unassigned' | 'balanced' | 'over'
}

export interface HealthFactor {
  key: string
  label: string
  score: number
  value: string
  detail: string
  tip: string
  status: 'good' | 'fair' | 'poor'
  weight: number
}

export interface HealthCheck {
  score: number | null
  grade: string | null
  factors: HealthFactor[]
  topTips: string[]
}

export interface Subscription {
  name: string
  source: 'bill' | 'payee' | 'scheduled'
  frequency: string
  amount: number
  usualAmount: number
  monthlyCost: number
  yearlyCost: number
  lastDate: string | null
  nextExpected: string | null
  category: string | null
  count: number
  priceIncrease: number
}

export interface Subscriptions {
  items: Subscription[]
  monthlyTotal: number
  yearlyTotal: number
  priceIncreases: string[]
}

export interface YearReview {
  year: number
  hasData: boolean
  income: number
  spending: number
  saved: number
  savingsRate: number | null
  months: { month: string; income: number; spending: number; net: number }[]
  averageMonthlySpending: number
  biggestMonth: string | null
  topCategories: { name: string; amount: number; color: string; share: number }[]
  topPayees: { name: string; amount: number }[]
  largestPurchases: { date: string; description: string; amount: number; category: string | null }[]
  byTag: { tag: string; amount: number }[]
  transactionCount: number
}
