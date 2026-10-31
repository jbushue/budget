import gql from 'graphql-tag'

const ASSET_FIELDS = `id name kind kindLabel value notes linkedBank linkedAccount loanBalance loanKind equity updated`

export const GET_NET_WORTH = gql`
  query NetWorth {
    netWorthBreakdown {
      cash totalAssets totalDebt netWorth
      assetsByKind { kind value }
      debts { kind value }
      assets { ${ASSET_FIELDS} }
      homes { name bank value owed }
    }
    assetKinds { kind label }
    netWorthHistory(limit: 365) { snapshotDate netWorth totalAssets totalLiabilities }
  }
`

export const GET_ASSET_HISTORY = gql`
  query AssetHistory($id: Int!) { assetHistory(id: $id) { date value } }
`

export const SAVE_ASSET = gql`
  mutation SaveAsset(
    $id: Int, $name: String!, $kind: String, $value: Float!, $notes: String, $linkedBank: String,
    $linkedAccount: String
  ) {
    saveAsset(
      id: $id, name: $name, kind: $kind, value: $value, notes: $notes, linkedBank: $linkedBank,
      linkedAccount: $linkedAccount
    ) { success message asset { ${ASSET_FIELDS} } }
  }
`

export const DELETE_ASSET = gql`
  mutation DeleteAsset($id: Int!) { deleteAsset(id: $id) { success message } }
`

export const GET_MONTHLY_PLAN = gql`
  query MonthlyPlan { monthlyPlan { income bills debtPayments budgets goalSaving leftToBudget status } }
`

export const GET_HEALTH_CHECK = gql`
  query HealthCheck {
    healthCheck { score grade topTips factors { key label score value detail tip status weight } }
  }
`

export const GET_SUBSCRIPTIONS = gql`
  query Subscriptions {
    subscriptions {
      monthlyTotal yearlyTotal priceIncreases
      items {
        name source frequency amount usualAmount monthlyCost yearlyCost lastDate nextExpected category count
        priceIncrease
      }
    }
  }
`

export const GET_YEAR_REVIEW = gql`
  query YearReview($year: Int) {
    yearReview(year: $year) {
      year hasData income spending saved savingsRate averageMonthlySpending biggestMonth transactionCount
      months { month income spending net }
      topCategories { name amount color share }
      topPayees { name amount }
      largestPurchases { date description amount category }
      byTag { tag amount }
    }
  }
`
