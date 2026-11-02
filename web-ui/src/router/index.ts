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
  { path: '/subscriptions', name: 'Subscriptions', component: () => import('../views/SubscriptionsView.vue') },
  { path: '/net-worth', name: 'NetWorth', component: () => import('../views/NetWorthView.vue') },
  { path: '/checkup', name: 'Health', component: () => import('../views/HealthView.vue') },
  { path: '/timeline', name: 'Timeline', component: () => import('../views/TimelineView.vue') },
  { path: '/optimizer', name: 'Optimizer', component: () => import('../views/OptimizerView.vue') },
  // Debt payoff lives on the Plan page now
  { path: '/debt-payoff', redirect: '/optimizer?tab=debt' },
  { path: '/scenarios', name: 'Scenarios', component: () => import('../views/ScenarioView.vue') },
  { path: '/reports', name: 'Reports', component: () => import('../views/ReportsView.vue') },
  { path: '/activity', name: 'Activity', component: () => import('../views/ActivityView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/SettingsView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

// Set before the router's own popstate handler runs (it's added when the router is created)
let poppedState = false
window.addEventListener('popstate', () => { poppedState = true })

export const router = createRouter({
  history: createWebHistory(),
  routes,
})


// Pages scroll inside .main-content (not the window), so the router's own
// scrollBehavior never applies. A new page opens at the top; Back/Forward
// returns to where you were; the same page (tabs, filters in the URL) stays put.
const scrollTops = new Map<string, number>()
const pane = () => document.querySelector<HTMLElement>('.main-content')

router.beforeEach((_to, from) => {
  const el = pane()
  if (el) scrollTops.set(from.fullPath, el.scrollTop)
})
router.afterEach((to, from, failure) => {
  const back = poppedState
  poppedState = false
  if (failure || to.path === from.path) return
  const top = back ? scrollTops.get(to.fullPath) ?? 0 : 0
  requestAnimationFrame(() => {
    const el = pane()
    if (!el) return
    el.scrollTop = top
    // Pages fill in as their data arrives: keep trying for a couple of seconds
    let tries = 0
    const retry = () => {
      if (!top || el.scrollTop >= top - 2 || ++tries > 15) return
      el.scrollTop = top
      setTimeout(retry, 150)
    }
    setTimeout(retry, 150)
  })
})
