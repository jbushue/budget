import gql from 'graphql-tag'

const TXN_FIELDS = `id date description payee amount bankName accountName category source matchedBill notes`

export const GET_LEDGER_TRANSACTIONS = gql`
  query LedgerTransactions(
    $text: String, $category: String, $account: String, $dateFrom: String, $dateTo: String,
    $uncategorized: Boolean, $limit: Int, $offset: Int
  ) {
    ledgerTransactions(
      text: $text, category: $category, account: $account, dateFrom: $dateFrom, dateTo: $dateTo,
      uncategorized: $uncategorized, limit: $limit, offset: $offset
    ) { total totalIn totalOut items { ${TXN_FIELDS} } }
  }
`

export const GET_CATEGORIES = gql`
  query Categories { categories { name kind isEveryday monthlyBudget color } }
`

export const GET_CATEGORY_RULES = gql`
  query CategoryRules { categoryRules { id pattern category priority } }
`

export const GET_BUDGET_STATUS = gql`
  query BudgetStatus($month: String) {
    budgetStatus(month: $month) {
      month daysElapsed daysInMonth totalBudget totalSpent totalBudgetedSpent uncategorizedSpent income
      lines { category color isEveryday budget spent remaining percent projected status }
    }
    learnedEverydayWeekly
  }
`

export const GET_SPENDING_REPORT = gql`
  query SpendingReport($months: Int) {
    spendingReport(months: $months) { colors months { month income spending net byCategory } }
  }
`

export const ADD_LEDGER_TRANSACTION = gql`
  mutation AddLedgerTransaction(
    $date: String!, $description: String!, $amount: Float!, $bankName: String, $accountName: String,
    $category: String, $notes: String
  ) {
    addLedgerTransaction(
      date: $date, description: $description, amount: $amount, bankName: $bankName,
      accountName: $accountName, category: $category, notes: $notes
    ) { success message transaction { ${TXN_FIELDS} } }
  }
`

export const UPDATE_LEDGER_TRANSACTION = gql`
  mutation UpdateLedgerTransaction(
    $id: Int!, $category: String, $notes: String, $description: String, $amount: Float, $date: String,
    $createRule: Boolean
  ) {
    updateLedgerTransaction(
      id: $id, category: $category, notes: $notes, description: $description, amount: $amount, date: $date,
      createRule: $createRule
    ) { success message transaction { ${TXN_FIELDS} } }
  }
`

export const DELETE_LEDGER_TRANSACTION = gql`
  mutation DeleteLedgerTransaction($id: Int!) { deleteLedgerTransaction(id: $id) { success message } }
`

export const IMPORT_CSV_TRANSACTIONS = gql`
  mutation ImportCsvTransactions(
    $content: String!, $bankName: String!, $accountName: String!, $mapping: JSONString,
    $invert: Boolean, $dateFormat: String, $preview: Boolean
  ) {
    importCsvTransactions(
      content: $content, bankName: $bankName, accountName: $accountName, mapping: $mapping,
      invert: $invert, dateFormat: $dateFormat, preview: $preview
    ) {
      result { success message imported duplicates matchedBills errors }
      previewData { columns mapping rowCount errors rows { date description amount category } }
    }
  }
`

export const IMPORT_SIMPLEFIN_TRANSACTIONS = gql`
  mutation ImportSimplefinTransactions($days: Int) {
    importSimplefinTransactions(days: $days) {
      result { success message imported duplicates matchedBills errors }
    }
  }
`

export const SAVE_CATEGORY = gql`
  mutation SaveCategory(
    $name: String!, $kind: String, $isEveryday: Boolean, $monthlyBudget: Float, $color: String, $renameFrom: String
  ) {
    saveCategory(
      name: $name, kind: $kind, isEveryday: $isEveryday, monthlyBudget: $monthlyBudget, color: $color,
      renameFrom: $renameFrom
    ) { success message }
  }
`

export const DELETE_CATEGORY = gql`
  mutation DeleteCategory($name: String!) { deleteCategory(name: $name) { success message } }
`

export const SET_CATEGORY_BUDGET = gql`
  mutation SetCategoryBudget($name: String!, $monthlyBudget: Float) {
    setCategoryBudget(name: $name, monthlyBudget: $monthlyBudget) { success message }
  }
`

export const ADD_CATEGORY_RULE = gql`
  mutation AddCategoryRule($pattern: String!, $category: String!, $priority: Int) {
    addCategoryRule(pattern: $pattern, category: $category, priority: $priority) { success message }
  }
`

export const DELETE_CATEGORY_RULE = gql`
  mutation DeleteCategoryRule($id: Int!) { deleteCategoryRule(id: $id) { success message } }
`

export const RECATEGORIZE_TRANSACTIONS = gql`
  mutation RecategorizeTransactions($onlyUncategorized: Boolean) {
    recategorizeTransactions(onlyUncategorized: $onlyUncategorized) { success message changed }
  }
`
