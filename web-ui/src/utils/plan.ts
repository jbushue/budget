import { ref, watch } from 'vue'
import type { ApolloCache } from '@apollo/client/core'

/**
 * The app follows one year-long plan (models/plan.py on the server). Every
 * forward-looking page shows part of it, so they agree about every day.
 */

export const PLAN_LABELS: Record<string, string> = {
  maximize_discretionary: 'Most cash', minimize_interest: 'Least interest', payoff_credit_account: 'Pay off a card',
}

export const PERIODS = [
  { days: 30, label: '30 days' },
  { days: 60, label: '60 days' },
  { days: 90, label: '90 days' },
  { days: 180, label: '6 months' },
  { days: 365, label: '1 year' },
]

// How far ahead Timeline, Plan and What-if show. Shared, and remembered on this device.
const KEY = 'budget-plan-days'
const savedDays = Number(localStorage.getItem(KEY))
export const planDays = ref<number>(PERIODS.some(p => p.days === savedDays) ? savedDays : 90)
watch(planDays, d => localStorage.setItem(KEY, String(d)))

/** Everything worked out from the plan: drop it so pages ask again after the plan changes. */
export const PLAN_FIELDS = [
  'dashboardSummary', 'projection', 'monthlyProjection', 'paymentInsights', 'paymentPlan', 'compareStrategies',
  'debtBoost', 'dueDateMoves', 'purchasePlanner', 'alerts', 'digestHtml', 'settings',
]

export function evictPlan(cache: ApolloCache) {
  for (const f of PLAN_FIELDS) cache.evict({ fieldName: f })
  cache.gc()
}
