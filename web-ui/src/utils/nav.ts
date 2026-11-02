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
  // One plan: what it does (Plan), day by day (Timeline), and what if something changes
  { label: 'Plan', items: [
    { path: '/optimizer', icon: 'zap', label: 'Plan' },
    { path: '/timeline', icon: 'calendar', label: 'Timeline' },
    { path: '/scenarios', icon: 'sparkles', label: 'What-if' },
  ] },
  { label: 'Spending', items: [
    { path: '/budgets', icon: 'budgets', label: 'Budgets' },
    { path: '/goals', icon: 'goals', label: 'Goals' },
    { path: '/subscriptions', icon: 'repeat', label: 'Subscriptions' },
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
