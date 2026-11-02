import gql from 'graphql-tag'

// Money moves and calculators that used to be CLI-only (models/gql_tools.py)

export const TRANSFER_MONEY = gql`
  mutation TransferMoney($fromBank: String!, $fromAccount: String!, $toBank: String!, $toAccount: String!, $amount: Float!, $note: String) {
    transferMoney(fromBank: $fromBank, fromAccount: $fromAccount, toBank: $toBank, toAccount: $toAccount, amount: $amount, note: $note) { success message }
  }
`

export const RECORD_PROMO_PURCHASE = gql`
  mutation RecordPromoPurchase($bankName: String!, $accountName: String!, $promoName: String!, $amount: Float!, $description: String) {
    recordPromoPurchase(bankName: $bankName, accountName: $accountName, promoName: $promoName, amount: $amount, description: $description) { success message }
  }
`

export const PAY_PROMO_BALANCE = gql`
  mutation PayPromoBalance($bankName: String!, $accountName: String!, $promoName: String!, $amount: Float!, $sourceBank: String!, $sourceAccount: String!) {
    payPromoBalance(bankName: $bankName, accountName: $accountName, promoName: $promoName, amount: $amount, sourceBank: $sourceBank, sourceAccount: $sourceAccount) { success message }
  }
`

export const PAY_EXTRA_PRINCIPAL = gql`
  mutation PayExtraPrincipal($bankName: String!, $accountName: String!, $amount: Float!, $sourceBank: String, $sourceAccount: String) {
    payExtraPrincipal(bankName: $bankName, accountName: $accountName, amount: $amount, sourceBank: $sourceBank, sourceAccount: $sourceAccount) { success message }
  }
`

export const UPDATE_BALANCES = gql`
  mutation UpdateBalances($updates: [BalanceInput!]!) {
    updateBalances(updates: $updates) { success message }
  }
`

export const RESET_BILL_TO_ESTIMATE = gql`
  mutation ResetBillToEstimate($billName: String!, $dueDate: String) {
    resetBillToEstimate(billName: $billName, dueDate: $dueDate) { success message }
  }
`

export const GET_MORTGAGE_DETAILS = gql`
  query GetMortgageDetails($bankName: String!, $accountName: String!, $extraMonthly: Float) {
    mortgageDetails(bankName: $bankName, accountName: $accountName, extraMonthly: $extraMonthly) {
      balance rate monthlyPayment principalAndInterest escrow nextInterest nextPrincipal
      remainingMonths payoffDate interestRemaining equity ltv marketValue
      extraMonthly monthsSaved interestSaved newPayoffDate
      schedule { month date payment principal interest escrow principalRemaining }
      years { year principal interest escrow endBalance }
    }
  }
`

export const COMPARE_STRATEGIES = gql`
  query CompareStrategies($days: Int, $targetAccount: String) {
    compareStrategies(days: $days, targetAccount: $targetAccount) {
      goal label finalCash endingDebt outcome lowestChecking late interestPaid interestEarned fees problems extraTotal
      extraPayments { date account amount }
    }
  }
`

export const GET_STRATEGY_TARGETS = gql`
  query GetStrategyTargets { strategyTargets }
`

export const GET_MONTHLY_PROJECTION = gql`
  query GetMonthlyProjection($days: Int) {
    monthlyProjection(days: $days) { month income payments spending interest fees net endCash endDebt }
  }
`

export const GET_DATABASE_INFO = gql`
  query GetDatabaseInfo {
    databaseInfo { path sizeBytes tables { table label rows } }
  }
`

export const GET_REPORT_KINDS = gql`
  query GetReportKinds { reportKinds { key description } }
`

export const GET_ACCOUNT_KINDS = gql`
  query GetAccountKinds { accountKinds }
`

export const GET_DEBT_BOOST = gql`
  query GetDebtBoost($days: Int, $strategy: String, $monthly: Float) {
    debtBoost(days: $days, strategy: $strategy, monthly: $monthly)
  }
`

export const GET_DUE_DATE_MOVES = gql`
  query GetDueDateMoves($days: Int) { dueDateMoves(days: $days) }
`

export const GET_PURCHASE_PLANNER = gql`
  query GetPurchasePlanner($amount: Float, $days: Int) { purchasePlanner(amount: $amount, days: $days) }
`
