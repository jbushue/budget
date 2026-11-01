// The sidebar's pages, grouped. Also used by the command palette.
export const NAV = [
  { label: '', items: [
    { path: '/', icon: 'dashboard', label: 'Dashboard' },
  ] },
  { label: 'Money', items: [
    { path: '/accounts', icon: 'accounts', label: 'Accounts' },
    { path: '/transactions', icon: 'transactions', label: 'Transactions' },
    { path: '/bills', icon: 'bills', label: 'Bills' },
    { path: '/income', icon: 'income', label: 'Income' },
    { path: '/bill-groups', icon: 'loans', label: 'Loan groups' },
  ] },
  { label: 'Plan', items: [
    { path: '/budgets', icon: 'budgets', label: 'Budgets' },
    { path: '/goals', icon: 'goals', label: 'Goals' },
    { path: '/subscriptions', icon: 'repeat', label: 'Subscriptions' },
    { path: '/timeline', icon: 'calendar', label: 'Timeline' },
  ] },
  { label: 'Optimize', items: [
    { path: '/optimizer', icon: 'zap', label: 'Optimizer' },
    { path: '/debt-payoff', icon: 'trendingDown', label: 'Debt payoff' },
    { path: '/scenarios', icon: 'sparkles', label: 'What-If' },
  ] },
  { label: 'Insights', items: [
    { path: '/reports', icon: 'chart', label: 'Reports' },
    { path: '/net-worth', icon: 'gem', label: 'Net worth' },
    { path: '/checkup', icon: 'health', label: 'Health check' },
  ] },
  { label: 'Manage', items: [
    { path: '/activity', icon: 'history', label: 'Activity' },
    { path: '/settings', icon: 'settings', label: 'Settings' },
  ] },
]
