import gql from 'graphql-tag'

export const GET_SAVINGS_GOALS = gql`
  query SavingsGoals {
    savingsGoals {
      id name targetAmount savedAmount remaining progress targetDate monthsLeft monthlyNeeded
      perPaycheckNeeded onTrack bankName accountName inChecking linkedBill complete
    }
    sinkingFundSuggestions { billName amount frequency nextDue monthly }
  }
`

export const SAVE_SAVINGS_GOAL = gql`
  mutation SaveSavingsGoal(
    $id: Int, $name: String!, $targetAmount: Float!, $targetDate: String, $bankName: String,
    $accountName: String, $savedAmount: Float
  ) {
    saveSavingsGoal(
      id: $id, name: $name, targetAmount: $targetAmount, targetDate: $targetDate, bankName: $bankName,
      accountName: $accountName, savedAmount: $savedAmount
    ) { success message }
  }
`

export const CONTRIBUTE_TO_GOAL = gql`
  mutation ContributeToGoal($id: Int!, $amount: Float!) { contributeToGoal(id: $id, amount: $amount) { success message } }
`

export const DELETE_SAVINGS_GOAL = gql`
  mutation DeleteSavingsGoal($id: Int!) { deleteSavingsGoal(id: $id) { success message } }
`

export const CREATE_SINKING_FUND = gql`
  mutation CreateSinkingFund($billName: String!, $bankName: String, $accountName: String) {
    createSinkingFund(billName: $billName, bankName: $bankName, accountName: $accountName) { success message }
  }
`

export const GET_BILL_MATCH_SUGGESTIONS = gql`
  query BillMatchSuggestions {
    billMatchSuggestions {
      billName dueDate confidence reason amount
      transaction { id date description amount bankName accountName }
    }
  }
`

export const CONFIRM_BILL_MATCH = gql`
  mutation ConfirmBillMatch($transactionId: Int!, $billName: String!) {
    confirmBillMatch(transactionId: $transactionId, billName: $billName) { success message }
  }
`

export const IGNORE_BILL_MATCH = gql`
  mutation IgnoreBillMatch($transactionId: Int!) { ignoreBillMatch(transactionId: $transactionId) { success message } }
`

export const UNMATCH_TRANSACTION = gql`
  mutation UnmatchTransaction($transactionId: Int!) { unmatchTransaction(transactionId: $transactionId) { success message } }
`

export const GET_RECURRING_CHARGES = gql`
  query RecurringCharges {
    recurringCharges {
      key name description frequency amount variable minAmount maxAmount count lastDate nextExpected
      dueDay category monthlyCost
    }
  }
`

export const DISMISS_RECURRING_CHARGE = gql`
  mutation DismissRecurringCharge($key: String!) { dismissRecurringCharge(key: $key) { success message } }
`
