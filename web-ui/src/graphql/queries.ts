import gql from 'graphql-tag'

// ── Queries ──────────────────────────────────────────────────────────

export const GET_SNAPSHOT = gql`
  query GetSnapshot {
    snapshot {
      timestamp
      totalAssets
      totalLiabilities
      netWorth
      banks {
        name
        bankType
        totalBalance
        totalCreditLimit
        totalAvailableCredit
        bankAccounts {
          id
          accountName
          accountType
          balance
          interestRate
          interestAccrualDate
        }
        creditAccounts {
          id
          accountName
          balance
          regularBalance
          creditLimit
          availableCredit
          interestRate
          paymentDueDate
          statementDate
          status
        }
        mortgageAccounts {
          id
          accountName
          originalPrincipal
          currentPrincipal
          interestRate
          loanTermMonths
          paymentDueDate
          totalMonthlyPayment
          monthlyPrincipal
          monthlyInterest
          escrowMonthly
          preferredSourceBank
          preferredSourceAccount
          status
        }
        helocAccounts {
          id
          accountName
          creditLimit
          balance
          availableCredit
          interestRate
          drawPeriodMonths
          totalTermMonths
          startDate
          drawEndDate
          maturityDate
          currentPhase
          minimumPayment
          monthlyInterest
          paymentDueDate
          preferredSourceBank
          preferredSourceAccount
        }
      }
      upcomingBills30Days {
        id
        billName
        amount
        dueDate
        billType
        frequency
        minAmount
        maxAmount
        nextDueDate
        preferredSourceBank
        preferredSourceAccount
        isPaidThisPeriod
        effectiveAmount
        isAccountLinked
        linkedBankName
        linkedAccountName
        linkedAccountType
      }
      upcomingIncome30Days {
        id
        sourceName
        amount
        frequency
        payDates
        nextPayDate
        distribution
      }
    }
  }
`

export const GET_ALL_BANKS = gql`
  query GetAllBanks {
    allBanks {
      name
      bankType
      totalBalance
      totalCreditLimit
      totalAvailableCredit
      bankAccounts {
        id
        accountName
        accountType
        balance
        interestRate
        interestAccrualDate
      }
      creditAccounts {
        id
        accountName
        balance
        regularBalance
        creditLimit
        availableCredit
        interestRate
        paymentDueDate
        statementDate
        status
        minimumPayment
        promoOffers {
          promoName
          monthsInterestFree
          purchaseLimit
          startDate
          endDate
          amountUsed
          promoBalance
          isActive
          daysRemaining
          interestCharged
        }
      }
      mortgageAccounts {
        id
        accountName
        originalPrincipal
        currentPrincipal
        interestRate
        loanTermMonths
        paymentDueDate
        totalMonthlyPayment
        monthlyPrincipal
        monthlyInterest
        escrowMonthly
        preferredSourceBank
        preferredSourceAccount
        status
      }
      helocAccounts {
        id
        accountName
        creditLimit
        balance
        availableCredit
        interestRate
        drawPeriodMonths
        totalTermMonths
        startDate
        drawEndDate
        maturityDate
        currentPhase
        minimumPayment
        monthlyInterest
        paymentDueDate
        preferredSourceBank
        preferredSourceAccount
      }
    }
  }
`

export const GET_ALL_BILLS = gql`
  query GetAllBills {
    allBills {
      id
      billName
      amount
      dueDate
      dueMonth
      billType
      frequency
      minAmount
      maxAmount
      startDate
      nextDueDate
      preferredSourceBank
      preferredSourceAccount
      isPaidThisPeriod
      estimatedAmount
      actualAmount
      hasActualAmount
      carryoverBalance
      effectiveAmount
      isAccountLinked
      linkedBankName
      linkedAccountName
      linkedAccountType
    }
  }
`

export const GET_ALL_INCOME = gql`
  query GetAllIncome {
    allIncome {
      id
      sourceName
      amount
      frequency
      payDates
      startDate
      nextPayDate
      distribution
    }
  }
`

export const GET_UPCOMING_BILLS = gql`
  query GetUpcomingBills($days: Int) {
    upcomingBills(days: $days) {
      id
      billName
      amount
      dueDate
      billType
      frequency
      minAmount
      maxAmount
      nextDueDate
      preferredSourceBank
      preferredSourceAccount
    }
  }
`

export const GET_UPCOMING_INCOME = gql`
  query GetUpcomingIncome($days: Int) {
    upcomingIncome(days: $days) {
      id
      sourceName
      amount
      frequency
      payDates
      nextPayDate
      distribution
    }
  }
`

export const GET_PROJECTION = gql`
  query GetProjection($days: Int) {
    projection(days: $days) {
      startDate
      endDate
      snapshots {
        date
        balances
        creditBalances
        mortgageBalances
        helocBalances
        total
        netTotal
      }
      calendarDays {
        date
        events {
          eventType
          description
          amount
          sourceBank
          sourceAccount
          status
        }
        balances
        creditBalances
        mortgageBalances
        helocBalances
        total
        netTotal
      }
      finalBalances
      creditFinalBalances
      mortgageFinalBalances
      helocFinalBalances
      totalFinalBalance
      totalCreditBalance
      totalMortgageBalance
      totalHelocBalance
      netFinalBalance
      totalIncome
      totalExpenses
      netChange
    }
  }
`

export const GET_PAYMENT_PLAN = gql`
  query GetPaymentPlan($days: Int) {
    paymentPlan(days: $days) {
      strategy
      discretionaryFunds
      totalInterest
      interestCharged
      interestEarned
      totalFees
      violations
    }
  }
`

const OUTCOME_FIELDS = `
  endingCash
  endingDebt
  netPosition
  netChange
  lowestChecking
  lowestCheckingDate
  lowestCheckingAccount
  interestCharged
  interestEarned
  paymentsOnTime
  pendingDeferredInterest
  latePayments { date name amount }
`

export const GET_PAYMENT_INSIGHTS = gql`
  query GetPaymentInsights($days: Int) {
    paymentInsights(days: $days) {
      startDate
      endDate
      days
      headline
      netBenefit
      changes
      onDueDate { ${OUTCOME_FIELDS} }
      optimized { ${OUTCOME_FIELDS} }
      insights { severity category title detail impact date }
      billTiming {
        name kind dueDate amount estimated sourceBank sourceAccount
        status planStatus fundedBy payEarlyDate daysEarly earlySavings
        cushionIfEarly shortfall fixes advice
      }
      groups {
        groupName payment totalBalance monthlyInterest
        members { accountName balance apr allocationMethod nextPaymentShare monthlyInterest }
        current { months interest paysOff }
        highestRateFirst { months interest paysOff }
        withExtra { months interest paysOff extraMonthly }
        reallocationSavings highestRateMember suggestedFixedAmount
      }
      promos {
        card bank promoName balance expires daysLeft monthlyNeeded
        scheduledInWindow onTrack shortfall interestAtRisk aprAfter
      }
      optimizerMoves { date type title why description amount }
    }
  }
`

export const GET_BALANCE_ON_DATE = gql`
  query GetBalanceOnDate($date: String!) {
    balanceOnDate(date: $date)
  }
`

// ── Mutations ────────────────────────────────────────────────────────

export const CREATE_BANK = gql`
  mutation CreateBank($name: String!, $bankType: String) {
    createBank(name: $name, bankType: $bankType) {
      success
      message
      bank {
        name
        bankType
      }
    }
  }
`

export const CREATE_ACCOUNT = gql`
  mutation CreateAccount(
    $bankName: String!
    $accountName: String!
    $accountType: String
    $balance: Float
    $interestRate: Float
    $creditLimit: Float
    $paymentDueDate: Int
    $statementDate: Int
    $interestAccrualDate: Int
  ) {
    createAccount(
      bankName: $bankName
      accountName: $accountName
      accountType: $accountType
      balance: $balance
      interestRate: $interestRate
      creditLimit: $creditLimit
      paymentDueDate: $paymentDueDate
      statementDate: $statementDate
      interestAccrualDate: $interestAccrualDate
    ) {
      success
      message
    }
  }
`

export const CREATE_BILL = gql`
  mutation CreateBill(
    $billName: String!
    $amount: Float!
    $dueDate: Int!
    $frequency: String
    $dueMonth: Int
    $preferredSourceBank: String
    $preferredSourceAccount: String
    $billType: String
    $minAmount: Float
    $maxAmount: Float
    $startDate: String
  ) {
    createBill(
      billName: $billName
      amount: $amount
      dueDate: $dueDate
      frequency: $frequency
      dueMonth: $dueMonth
      preferredSourceBank: $preferredSourceBank
      preferredSourceAccount: $preferredSourceAccount
      billType: $billType
      minAmount: $minAmount
      maxAmount: $maxAmount
      startDate: $startDate
    ) {
      success
      message
    }
  }
`

export const CREATE_INCOME_SOURCE = gql`
  mutation CreateIncomeSource(
    $sourceName: String!
    $amount: Float!
    $frequency: String
    $payDates: [Int]
    $distribution: JSONString
    $startDate: String
  ) {
    createIncomeSource(
      sourceName: $sourceName
      amount: $amount
      frequency: $frequency
      payDates: $payDates
      distribution: $distribution
      startDate: $startDate
    ) {
      success
      message
    }
  }
`

export const UPDATE_ACCOUNT_BALANCE = gql`
  mutation UpdateAccountBalance(
    $bankName: String!
    $accountName: String!
    $newBalance: Float!
  ) {
    updateAccountBalance(
      bankName: $bankName
      accountName: $accountName
      newBalance: $newBalance
    ) {
      success
      message
      newBalance
    }
  }
`

export const SAVE_DATABASE = gql`
  mutation SaveDatabase {
    saveDatabase {
      success
      message
    }
  }
`

export const LOAD_DATABASE = gql`
  mutation LoadDatabase {
    loadDatabase {
      success
      message
      banksCount
    }
  }
`

export const DELETE_BANK = gql`
  mutation DeleteBank($name: String!) {
    deleteBank(name: $name) { success message }
  }
`

export const DELETE_ACCOUNT = gql`
  mutation DeleteAccount($bankName: String!, $accountName: String!, $accountType: String) {
    deleteAccount(bankName: $bankName, accountName: $accountName, accountType: $accountType) { success message }
  }
`

export const DELETE_BILL = gql`
  mutation DeleteBill($billName: String!) {
    deleteBill(billName: $billName) { success message }
  }
`

export const DELETE_INCOME = gql`
  mutation DeleteIncome($sourceName: String!) {
    deleteIncome(sourceName: $sourceName) { success message }
  }
`

export const UPDATE_CREDIT_BALANCE = gql`
  mutation UpdateCreditBalance($bankName: String!, $accountName: String!, $newBalance: Float!) {
    updateCreditBalance(bankName: $bankName, accountName: $accountName, newBalance: $newBalance) { success message }
  }
`

export const UPDATE_BILL = gql`
  mutation UpdateBill($billName: String!, $amount: Float, $dueDate: Int, $preferredSourceBank: String, $preferredSourceAccount: String, $frequency: String, $dueMonth: Int, $startDate: String, $minAmount: Float, $maxAmount: Float) {
    updateBill(billName: $billName, amount: $amount, dueDate: $dueDate, preferredSourceBank: $preferredSourceBank, preferredSourceAccount: $preferredSourceAccount, frequency: $frequency, dueMonth: $dueMonth, startDate: $startDate, minAmount: $minAmount, maxAmount: $maxAmount) { success message }
  }
`

export const UPDATE_INCOME = gql`
  mutation UpdateIncome($sourceName: String!, $amount: Float, $frequency: String, $payDates: [Int], $distribution: JSONString, $startDate: String) {
    updateIncome(sourceName: $sourceName, amount: $amount, frequency: $frequency, payDates: $payDates, distribution: $distribution, startDate: $startDate) { success message }
  }
`

export const MARK_BILL_PAID = gql`
  mutation MarkBillPaid($billName: String!, $amountPaid: Float, $sourceBank: String, $sourceAccount: String, $paymentDate: String) {
    markBillPaid(billName: $billName, amountPaid: $amountPaid, sourceBank: $sourceBank, sourceAccount: $sourceAccount, paymentDate: $paymentDate) { success message }
  }
`

export const RESET_BILL_PERIOD = gql`
  mutation ResetBillPeriod($billName: String!) {
    resetBillPeriod(billName: $billName) { success message }
  }
`

export const SET_FLOATING_BILL_AMOUNT = gql`
  mutation SetFloatingBillAmount($billName: String!, $actualAmount: Float!) {
    setFloatingBillAmount(billName: $billName, actualAmount: $actualAmount) { success message }
  }
`

export const RECORD_BALANCE_UPDATE = gql`
  mutation RecordBalanceUpdate($bankName: String!, $accountName: String!, $newBalance: Float!, $accountType: String, $notes: String) {
    recordBalanceUpdate(bankName: $bankName, accountName: $accountName, newBalance: $newBalance, accountType: $accountType, notes: $notes) { success message }
  }
`

export const GET_BALANCE_HISTORY = gql`
  query GetBalanceHistory($bankName: String!, $accountName: String!, $limit: Int) {
    balanceHistory(bankName: $bankName, accountName: $accountName, limit: $limit) {
      bankName
      accountName
      accountType
      balance
      previousBalance
      recordedAt
      notes
    }
  }
`

export const GET_CREDIT_PAYMENTS_DUE = gql`
  query GetCreditPaymentsDue {
    creditPaymentsDue {
      id
      bankName
      accountName
      balance
      minimumPayment
      paymentDueDate
      interestRate
      creditLimit
      availableCredit
      status
      isPaidThisPeriod
      lastPaymentAmount
      lastPaymentDate
    }
  }
`

export const MARK_CREDIT_PAYMENT_PAID = gql`
  mutation MarkCreditPaymentPaid($bankName: String!, $accountName: String!, $amountPaid: Float!, $sourceBank: String, $sourceAccount: String, $paymentDate: String) {
    markCreditPaymentPaid(bankName: $bankName, accountName: $accountName, amountPaid: $amountPaid, sourceBank: $sourceBank, sourceAccount: $sourceAccount, paymentDate: $paymentDate) { success message }
  }
`

export const RESET_CREDIT_PAYMENT_PERIOD = gql`
  mutation ResetCreditPaymentPeriod($bankName: String!, $accountName: String!) {
    resetCreditPaymentPeriod(bankName: $bankName, accountName: $accountName) { success message }
  }
`

// ── SimpleFIN ─────────────────────────────────────────────────────────

export const GET_SIMPLEFIN_STATUS = gql`
  query GetSimplefinStatus {
    simplefinStatus {
      isConnected
      createdAt
      lastSyncAt
      mappedAccountCount
    }
  }
`

export const GET_SIMPLEFIN_SYNCED_ACCOUNTS = gql`
  query GetSimplefinSyncedAccounts {
    simplefinSyncedAccounts {
      bankName
      accountName
      accountType
      sfinName
      sfinOrg
    }
  }
`

export const GET_SIMPLEFIN_ACCOUNTS = gql`
  query GetSimplefinAccounts {
    simplefinAccounts {
      id
      name
      orgName
      orgDomain
      currency
      balance
      availableBalance
      balanceDate
      mappedBankName
      mappedAccountName
      mappedAccountType
    }
  }
`

export const SETUP_SIMPLEFIN = gql`
  mutation SetupSimplefin($setupToken: String!) {
    setupSimplefin(setupToken: $setupToken) { success message }
  }
`

export const SYNC_SIMPLEFIN_BALANCES = gql`
  mutation SyncSimplefinBalances {
    syncSimplefinBalances {
      success
      message
      accountsUpdated
      accountsSkipped
      errors
      details
    }
  }
`

export const MAP_SIMPLEFIN_ACCOUNT = gql`
  mutation MapSimplefinAccount(
    $simplefinAccountId: String!
    $simplefinAccountName: String!
    $simplefinOrgName: String!
    $bankName: String!
    $accountName: String!
    $accountType: String!
  ) {
    mapSimplefinAccount(
      simplefinAccountId: $simplefinAccountId
      simplefinAccountName: $simplefinAccountName
      simplefinOrgName: $simplefinOrgName
      bankName: $bankName
      accountName: $accountName
      accountType: $accountType
    ) { success message }
  }
`

export const UNMAP_SIMPLEFIN_ACCOUNT = gql`
  mutation UnmapSimplefinAccount($simplefinAccountId: String!) {
    unmapSimplefinAccount(simplefinAccountId: $simplefinAccountId) { success message }
  }
`

export const REMOVE_SIMPLEFIN_CONNECTION = gql`
  mutation RemoveSimplefinConnection {
    removeSimplefinConnection { success message }
  }
`

// ── Enhancement Queries ─────────────────────────────────────────────

export const GET_SAFE_TO_SPEND = gql`
  query GetSafeToSpend {
    safeToSpend {
      safeToSpend
      totalChecking
      committedBills
      upcomingIncome
      nextIncomeDate
      horizonDate
    }
  }
`

export const GET_NET_WORTH_HISTORY = gql`
  query GetNetWorthHistory($limit: Int) {
    netWorthHistory(limit: $limit) {
      snapshotDate
      totalAssets
      totalLiabilities
      netWorth
    }
  }
`

export const GET_BILL_PAYMENT_HISTORY = gql`
  query GetBillPaymentHistory($billName: String, $limit: Int) {
    billPaymentHistory(billName: $billName, limit: $limit) {
      billName
      amountPaid
      sourceBank
      sourceAccount
      paymentDate
    }
  }
`

export const GET_DEBT_PAYOFF_COMPARISON = gql`
  query GetDebtPayoffComparison($extraMonthly: Float) {
    debtPayoffComparison(extraMonthly: $extraMonthly) {
      minimum {
        strategy
        monthsToPayoff
        totalInterestPaid
        totalPaid
        payoffOrder
        paysOff
        remainingBalance
        monthlyBreakdown
      }
      avalanche {
        strategy
        monthsToPayoff
        totalInterestPaid
        totalPaid
        payoffOrder
        paysOff
        remainingBalance
        monthlyBreakdown
      }
      snowball {
        strategy
        monthsToPayoff
        totalInterestPaid
        totalPaid
        payoffOrder
        paysOff
        remainingBalance
        monthlyBreakdown
      }
    }
  }
`

export const GET_WHAT_IF_SCENARIO = gql`
  query GetWhatIfScenario($modifications: JSONString!, $days: Int) {
    whatIfScenario(modifications: $modifications, days: $days) {
      baselineFinalBalance
      scenarioFinalBalance
      difference
      baselineSnapshots
      scenarioSnapshots
      changes
      baseline { ${OUTCOME_FIELDS} }
      scenario { ${OUTCOME_FIELDS} }
    }
  }
`

export const AUTO_RESET_PERIODS = gql`
  mutation AutoResetPeriods {
    autoResetPeriods { success resetCount message }
  }
`

export const RECORD_NET_WORTH_SNAPSHOT = gql`
  mutation RecordNetWorthSnapshot {
    recordNetWorthSnapshot {
      success
      snapshot {
        snapshotDate
        totalAssets
        totalLiabilities
        netWorth
      }
    }
  }
`

// ── Bill Groups ──────────────────────────────────────────────────────

const BILL_GROUP_FIELDS = `
  groupName
  totalPayment
  dueDate
  frequency
  groupType
  preferredSourceBank
  preferredSourceAccount
  isPaidThisPeriod
  members {
    bankName
    accountName
    allocationMethod
    fixedAmount
    balance
    interestRate
  }
  totalBalance
  memberCount
`

export const GET_ALL_BILL_GROUPS = gql`
  query GetAllBillGroups {
    allBillGroups {
      ${BILL_GROUP_FIELDS}
    }
  }
`

export const GET_BILL_GROUP = gql`
  query GetBillGroup($groupName: String!) {
    billGroup(groupName: $groupName) {
      ${BILL_GROUP_FIELDS}
    }
  }
`

export const CREATE_BILL_GROUP = gql`
  mutation CreateBillGroup(
    $groupName: String!
    $totalPayment: Float!
    $dueDate: Int!
    $frequency: String
    $groupType: String
    $preferredSourceBank: String
    $preferredSourceAccount: String
  ) {
    createBillGroup(
      groupName: $groupName
      totalPayment: $totalPayment
      dueDate: $dueDate
      frequency: $frequency
      groupType: $groupType
      preferredSourceBank: $preferredSourceBank
      preferredSourceAccount: $preferredSourceAccount
    ) {
      success
      message
      billGroup { ${BILL_GROUP_FIELDS} }
    }
  }
`

export const UPDATE_BILL_GROUP = gql`
  mutation UpdateBillGroup(
    $groupName: String!
    $totalPayment: Float
    $dueDate: Int
    $frequency: String
    $groupType: String
    $preferredSourceBank: String
    $preferredSourceAccount: String
  ) {
    updateBillGroup(
      groupName: $groupName
      totalPayment: $totalPayment
      dueDate: $dueDate
      frequency: $frequency
      groupType: $groupType
      preferredSourceBank: $preferredSourceBank
      preferredSourceAccount: $preferredSourceAccount
    ) {
      success
      message
      billGroup { ${BILL_GROUP_FIELDS} }
    }
  }
`

export const DELETE_BILL_GROUP = gql`
  mutation DeleteBillGroup($groupName: String!) {
    deleteBillGroup(groupName: $groupName) { success message }
  }
`

export const ADD_BILL_GROUP_MEMBER = gql`
  mutation AddBillGroupMember(
    $groupName: String!
    $bankName: String!
    $accountName: String!
    $allocationMethod: String
    $fixedAmount: Float
  ) {
    addBillGroupMember(
      groupName: $groupName
      bankName: $bankName
      accountName: $accountName
      allocationMethod: $allocationMethod
      fixedAmount: $fixedAmount
    ) {
      success
      message
      billGroup { ${BILL_GROUP_FIELDS} }
    }
  }
`

export const REMOVE_BILL_GROUP_MEMBER = gql`
  mutation RemoveBillGroupMember($groupName: String!, $bankName: String!, $accountName: String!) {
    removeBillGroupMember(groupName: $groupName, bankName: $bankName, accountName: $accountName) {
      success
      message
      billGroup { ${BILL_GROUP_FIELDS} }
    }
  }
`

export const MARK_BILL_GROUP_PAID = gql`
  mutation MarkBillGroupPaid($groupName: String!, $amountPaid: Float, $sourceBank: String, $sourceAccount: String, $paymentDate: String) {
    markBillGroupPaid(groupName: $groupName, amountPaid: $amountPaid, sourceBank: $sourceBank, sourceAccount: $sourceAccount, paymentDate: $paymentDate) {
      success
      message
      billGroup { ${BILL_GROUP_FIELDS} }
    }
  }
`

export const CREATE_HELOC_ACCOUNT = gql`
  mutation CreateHELOCAccount(
    $bankName: String!
    $accountName: String!
    $creditLimit: Float!
    $interestRate: Float
    $drawPeriodMonths: Int
    $totalTermMonths: Int
    $startDate: String
    $currentBalance: Float
    $paymentDueDate: Int
    $preferredSourceBank: String
    $preferredSourceAccount: String
  ) {
    createHelocAccount(
      bankName: $bankName
      accountName: $accountName
      creditLimit: $creditLimit
      interestRate: $interestRate
      drawPeriodMonths: $drawPeriodMonths
      totalTermMonths: $totalTermMonths
      startDate: $startDate
      currentBalance: $currentBalance
      paymentDueDate: $paymentDueDate
      preferredSourceBank: $preferredSourceBank
      preferredSourceAccount: $preferredSourceAccount
    ) { success message }
  }
`

export const CREATE_MORTGAGE_ACCOUNT = gql`
  mutation CreateMortgageAccount(
    $bankName: String!
    $accountName: String!
    $originalPrincipal: Float!
    $currentPrincipal: Float
    $interestRate: Float
    $loanTermMonths: Int
    $paymentDueDate: Int
    $startDate: String
    $escrowPropertyTax: Float
    $escrowInsurance: Float
    $escrowPmi: Float
    $escrowHoa: Float
    $escrowOther: Float
    $marketValue: Float
    $preferredSourceBank: String
    $preferredSourceAccount: String
  ) {
    createMortgageAccount(
      bankName: $bankName
      accountName: $accountName
      originalPrincipal: $originalPrincipal
      currentPrincipal: $currentPrincipal
      interestRate: $interestRate
      loanTermMonths: $loanTermMonths
      paymentDueDate: $paymentDueDate
      startDate: $startDate
      escrowPropertyTax: $escrowPropertyTax
      escrowInsurance: $escrowInsurance
      escrowPmi: $escrowPmi
      escrowHoa: $escrowHoa
      escrowOther: $escrowOther
      marketValue: $marketValue
      preferredSourceBank: $preferredSourceBank
      preferredSourceAccount: $preferredSourceAccount
    ) { success message }
  }
`

export const CONVERT_CREDIT_TO_HELOC = gql`
  mutation ConvertCreditToHELOC(
    $bankName: String!
    $accountName: String!
    $drawPeriodMonths: Int!
    $totalTermMonths: Int!
    $startDate: String
    $newAccountName: String
  ) {
    convertCreditToHeloc(
      bankName: $bankName
      accountName: $accountName
      drawPeriodMonths: $drawPeriodMonths
      totalTermMonths: $totalTermMonths
      startDate: $startDate
      newAccountName: $newAccountName
    ) { success message }
  }
`

export const GET_SIMPLEFIN_TRANSACTIONS = gql`
  query GetSimplefinTransactions($bankName: String!, $accountName: String!, $days: Int) {
    simplefinTransactions(bankName: $bankName, accountName: $accountName, days: $days) {
      id
      posted
      amount
      description
      payee
      memo
    }
  }
`

export const ADD_PROMO_OFFER = gql`
  mutation AddPromoOffer(
    $bankName: String!
    $accountName: String!
    $promoName: String!
    $monthsInterestFree: Int!
    $purchaseLimit: Float
    $promoBalance: Float
    $startDate: String
    $endDate: String
  ) {
    addPromoOffer(
      bankName: $bankName
      accountName: $accountName
      promoName: $promoName
      monthsInterestFree: $monthsInterestFree
      purchaseLimit: $purchaseLimit
      promoBalance: $promoBalance
      startDate: $startDate
      endDate: $endDate
    ) { success message }
  }
`

export const UPDATE_PROMO_OFFER = gql`
  mutation UpdatePromoOffer(
    $bankName: String!
    $accountName: String!
    $promoName: String!
    $promoBalance: Float
  ) {
    updatePromoOffer(
      bankName: $bankName
      accountName: $accountName
      promoName: $promoName
      promoBalance: $promoBalance
    ) { success message }
  }
`

export const REMOVE_PROMO_OFFER = gql`
  mutation RemovePromoOffer(
    $bankName: String!
    $accountName: String!
    $promoName: String!
  ) {
    removePromoOffer(
      bankName: $bankName
      accountName: $accountName
      promoName: $promoName
    ) { success message }
  }
`
