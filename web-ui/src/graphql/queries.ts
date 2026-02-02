import { gql } from '@apollo/client';

// ==================== QUERIES ====================

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
        bankAccounts {
          id
          accountName
          accountType
          balance
          interestRate
        }
        creditAccounts {
          id
          accountName
          creditLimit
          balance
          availableCredit
          paymentDueDate
        }
      }
      upcomingBills30Days {
        id
        billName
        amount
        nextDueDate
        frequency
      }
      upcomingIncome30Days {
        id
        sourceName
        amount
        nextPayDate
      }
    }
  }
`;

export const GET_PROJECTION = gql`
  query GetProjection($days: Int) {
    projection(days: $days) {
      startDate
      endDate
      totalFinalBalance
      totalIncome
      totalExpenses
      netChange
      snapshots {
        date
        total
      }
    }
  }
`;

export const GET_PAYMENT_PLAN = gql`
  query GetPaymentPlan($days: Int) {
    paymentPlan(days: $days) {
      discretionaryFunds
      totalInterest
      totalFees
      violations
      strategy
    }
  }
`;

export const GET_ALL_BILLS = gql`
  query GetAllBills {
    allBills {
      id
      billName
      amount
      dueDate
      frequency
      nextDueDate
    }
  }
`;

export const GET_ALL_INCOME = gql`
  query GetAllIncome {
    allIncome {
      id
      sourceName
      amount
      frequency
      payDates
      nextPayDate
    }
  }
`;

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
      }
      creditAccounts {
        id
        accountName
        creditLimit
        balance
        availableCredit
      }
    }
  }
`;

export const GET_BALANCE_ON_DATE = gql`
  query GetBalanceOnDate($date: String!) {
    balanceOnDate(date: $date)
  }
`;

// ==================== MUTATIONS ====================

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
`;

export const CREATE_ACCOUNT = gql`
  mutation CreateAccount(
    $bankName: String!
    $accountName: String!
    $accountType: String!
    $balance: Float
    $interestRate: Float
    $creditLimit: Float
  ) {
    createAccount(
      bankName: $bankName
      accountName: $accountName
      accountType: $accountType
      balance: $balance
      interestRate: $interestRate
      creditLimit: $creditLimit
    ) {
      success
      message
    }
  }
`;

export const CREATE_BILL = gql`
  mutation CreateBill(
    $billName: String!
    $amount: Float!
    $dueDate: Int!
    $frequency: String!
  ) {
    createBill(
      billName: $billName
      amount: $amount
      dueDate: $dueDate
      frequency: $frequency
    ) {
      success
      message
    }
  }
`;

export const CREATE_INCOME = gql`
  mutation CreateIncomeSource(
    $sourceName: String!
    $amount: Float!
    $frequency: String!
    $payDates: [Int]!
    $distribution: JSON
  ) {
    createIncomeSource(
      sourceName: $sourceName
      amount: $amount
      frequency: $frequency
      payDates: $payDates
      distribution: $distribution
    ) {
      success
      message
    }
  }
`;

export const UPDATE_BALANCE = gql`
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
`;

export const SAVE_DATABASE = gql`
  mutation SaveDatabase {
    saveDatabase {
      success
      message
    }
  }
`;

export const LOAD_DATABASE = gql`
  mutation LoadDatabase {
    loadDatabase {
      success
      message
      banksCount
    }
  }
`;

