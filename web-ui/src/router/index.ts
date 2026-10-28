import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/DashboardView.vue') },
  { path: '/accounts', name: 'Accounts', component: () => import('../views/AccountsView.vue') },
  { path: '/bills', name: 'Bills', component: () => import('../views/BillsView.vue') },
  { path: '/bill-groups', name: 'BillGroups', component: () => import('../views/BillGroupsView.vue') },
  { path: '/income', name: 'Income', component: () => import('../views/IncomeView.vue') },
  { path: '/transactions', name: 'Transactions', component: () => import('../views/TransactionsView.vue') },
  { path: '/budgets', name: 'Budgets', component: () => import('../views/BudgetsView.vue') },
  { path: '/goals', name: 'Goals', component: () => import('../views/GoalsView.vue') },
  { path: '/timeline', name: 'Timeline', component: () => import('../views/TimelineView.vue') },
  { path: '/optimizer', name: 'Optimizer', component: () => import('../views/OptimizerView.vue') },
  { path: '/debt-payoff', name: 'DebtPayoff', component: () => import('../views/DebtPayoffView.vue') },
  { path: '/scenarios', name: 'Scenarios', component: () => import('../views/ScenarioView.vue') },
  { path: '/reports', name: 'Reports', component: () => import('../views/ReportsView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/SettingsView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

