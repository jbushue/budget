<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Plan</h2>
        <p class="view-sub">One plan for paying your bills and using your money. The dashboard, timeline, alerts and daily email all follow it.</p>
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center">
        <PeriodSelect />
        <button class="btn btn-outline" @click="refetchAll()"><Icon name="refresh" :size="15" /> Refresh</button>
      </div>
    </div>

    <!-- What the plan aims for -->
    <div class="card goal-card">
      <div class="goal-bar">
        <span class="goal-label">Aim for</span>
        <div class="segmented" role="radiogroup" aria-label="Plan goal">
          <button v-for="g in GOALS" :key="g.key" role="radio" :aria-checked="goal === g.key"
                  :class="{ active: goal === g.key }" :disabled="g.key === 'payoff_credit_account' && !targets.length"
                  :title="g.key === 'payoff_credit_account' && !targets.length ? 'No card has a balance' : g.hint"
                  @click="setGoal(g.key)">
            <Icon :name="g.icon" :size="15" /> {{ g.label }}
          </button>
        </div>
        <!-- Saved only when you pick a card (not when the list loads) -->
        <select v-if="goal === 'payoff_credit_account'" v-model="target" style="width:auto" aria-label="Card to pay off"
                @change="setGoal('payoff_credit_account')">
          <option v-for="t in targets" :key="t" :value="t">{{ t }}</option>
        </select>
        <button class="btn btn-ghost btn-sm" style="margin-left:auto" @click="compareOpen = !compareOpen">
          <Icon name="chart" :size="15" /> {{ compareOpen ? 'Hide comparison' : 'Compare goals' }}
        </button>
      </div>
      <p class="goal-note">{{ savingGoal ? 'Switching the plan...' : `${goalHint}. The whole app follows this plan.` }}</p>
      <div v-if="compareOpen" class="compare">
        <div class="compare-title">How each goal plays out over {{ periodLabel }}</div>
      <div v-if="cmpLoading && !cmpResult" class="loading">Running the optimizer once per goal...</div>
      <div v-else-if="cmpError" class="callout danger">{{ cmpError.message }}</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Goal</th>
              <th style="text-align:right">Late</th>
              <th style="text-align:right">Lowest checking</th>
              <th style="text-align:right">Cash at the end</th>
              <th style="text-align:right">Debt at the end</th>
              <th style="text-align:right">Interest paid</th>
              <th style="text-align:right">Fees</th>
              <th style="text-align:right">Extra to card</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sgy in strategies" :key="sgy.goal" :class="{ 'row-current': sgy.goal === goal }">
              <td style="font-weight:550">{{ sgy.label }}</td>
              <td style="text-align:right" :class="{ negative: sgy.late > 0 }">{{ sgy.late }}</td>
              <td style="text-align:right">{{ currency(sgy.lowestChecking ?? 0) }}</td>
              <td style="text-align:right" :class="{ best: sgy.finalCash === bestCash }">{{ currency(sgy.finalCash) }}</td>
              <td style="text-align:right" :class="{ best: sgy.endingDebt === leastDebt }">{{ currency(sgy.endingDebt) }}</td>
              <td style="text-align:right" :class="{ best: sgy.interestPaid === leastInterest }">{{ currency(sgy.interestPaid) }}</td>
              <td style="text-align:right">{{ currency(sgy.fees) }}</td>
              <td style="text-align:right">{{ sgy.extraTotal ? currency(sgy.extraTotal) : '—' }}</td>
              <td style="text-align:right">
                <button v-if="sgy.goal !== goal" class="btn btn-outline btn-sm" @click="setGoal(sgy.goal)">Use</button>
                <span v-else class="badge badge-info">In use</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="muted" style="font-size:0.8rem;margin:0.6rem 0 0">
          “Pay off a card” sends spare cash to {{ target || 'the chosen card' }} after each paycheck.
          <template v-if="!targets.length">It's unavailable because no card has a balance.</template>
        </p>
      </div>
      </div>
    </div>

    <div class="tabs plan-tabs" role="tablist">
      <button v-for="t in TABS" :key="t.key" class="tab" :class="{ active: tab === t.key }" role="tab"
              :aria-selected="tab === t.key" @click="setTab(t.key)">
        <Icon :name="t.icon" :size="14" /> {{ t.label }}
        <span v-if="t.key === 'bills' && lateCount" class="tab-count">{{ lateCount }}</span>
        <span v-if="t.key === 'debt' && offTrackPromos" class="tab-count">{{ offTrackPromos }}</span>
      </button>
    </div>

    <div v-if="loading && !ins" class="loading">Working out your plan...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="ins">
      <!-- Overview -->
      <template v-if="tab === 'overview'">
        <div class="card" :style="`margin-bottom:1.5rem;border-left:4px solid ${headlineColor}`">
          <div style="font-size:1.05rem;font-weight:600;margin-bottom:0.5rem">{{ ins.headline }}</div>
          <ul style="margin:0;padding-left:1.1rem;font-size:0.85rem;color:var(--text-muted)">
            <li v-for="(c, i) in ins.changes" :key="i">{{ c }}</li>
          </ul>
        </div>

        <div class="grid grid-2" style="margin-bottom:1.5rem;align-items:start">
          <div class="card">
            <div class="card-header"><span class="card-title">What to do</span></div>
            <InsightList :items="ins.insights" />
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">What the plan does</span></div>
        <div v-if="ins.optimizerMoves.length === 0" class="empty-state" style="padding:1rem">
          <p>No transfers needed: paying each bill on its due date is already the best plan for this period.</p>
        </div>
        <template v-else>
          <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin-bottom:1rem">
            <div v-for="grp in moveGroups" :key="grp.type" class="stat-card" style="padding:0.75rem;text-align:left;border:1px solid var(--border);border-radius:var(--radius)">
              <div class="move-title"><Icon :name="eventIcon(grp.type)" :size="16" /> {{ grp.title }}</div>
              <div style="font-size:1.15rem;font-weight:700;margin:0.2rem 0">{{ currency(grp.total) }}</div>
              <div style="font-size:0.75rem;color:var(--text-muted)">{{ grp.count }} time(s). {{ grp.why }}</div>
            </div>
          </div>
          <details class="more">
          <summary>Every move, by date ({{ ins.optimizerMoves.length }})</summary>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Date</th><th>Move</th><th>Details</th><th style="text-align:right">Amount</th></tr>
              </thead>
              <tbody>
                <tr v-for="(m, i) in ins.optimizerMoves" :key="i" :style="{ borderLeft: `3px solid ${eventColor(m.type)}` }">
                  <td style="font-size:0.85rem;white-space:nowrap">{{ fmtDateShort(m.date) }}</td>
                  <td><span class="badge" :class="eventBadgeClass(m.type)"><Icon :name="eventIcon(m.type)" :size="13" /> {{ m.title }}</span></td>
                  <td style="font-size:0.85rem">{{ m.description }}</td>
                  <td style="text-align:right;font-weight:600">{{ currency(m.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          </details>
        </template>
          </div>
        </div>

        <div class="card" style="margin-bottom:1.5rem">
          <div class="card-header">
            <span class="card-title">Paying on due dates vs. the plan · {{ periodLabel }}</span>
          </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th></th>
                <th style="text-align:right">On due date</th>
                <th style="text-align:right">The plan</th>
                <th style="text-align:right">Difference</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in comparisonRows" :key="row.label">
                <td>
                  <div style="font-weight:500">{{ billName(row.label) }}</div>
                  <div v-if="row.hint" style="font-size:0.72rem;color:var(--text-muted)">{{ row.hint }}</div>
                </td>
                <td style="text-align:right">{{ row.fmt(row.base) }}<div v-if="row.baseNote" class="cell-note">{{ row.baseNote }}</div></td>
                <td style="text-align:right">{{ row.fmt(row.opt) }}<div v-if="row.optNote" class="cell-note">{{ row.optNote }}</div></td>
                <td style="text-align:right;font-weight:600" :class="diffClass(row)">{{ diffText(row) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
          <details class="more">
            <summary>How the plan is made</summary>
            <p>
              <strong>On due date</strong>: every bill comes out of its usual account on the day it's due, nothing else moves.
              <strong>The plan</strong>: the same bills, plus moves: spare cash paid onto your costliest debt before it's
              charged interest, parked in a HELOC or moved to savings, promo payoffs, and money moved to cover a bill that
              would otherwise be missed. Every move is tested day by day over the next year and only kept if it leaves you
              better off, with no extra late payments or fees and checking never below your cushion.
            </p>
          </details>
        </div>

      <!-- Technical warnings from the optimizer -->
      <div v-if="plan && plan.violations.length" class="card" style="border-left:4px solid var(--warning)">
        <div class="card-header" style="cursor:pointer;user-select:none;display:flex;align-items:center;justify-content:space-between" @click="violationsOpen = !violationsOpen">
          <span class="card-title">Plan checks ({{ plan.violations.length }})</span>
          <span style="font-size:0.75rem;color:var(--text-muted)">{{ violationsOpen ? '▲ Collapse' : '▼ Expand' }}</span>
        </div>
        <ul v-show="violationsOpen" style="list-style:none;margin:0;padding:0">
          <li v-for="(v, i) in plan.violations" :key="i" style="padding:0.4rem 0;border-bottom:1px solid var(--border);font-size:0.85rem">
            <span v-if="v.startsWith('WARNING')" style="color:var(--warning)">&#9888;</span>
            <span v-else-if="v.startsWith('INFO')" style="color:var(--primary)">&#9432;</span>
            <span v-else style="color:var(--danger)">&#10060;</span>
            {{ v }}
          </li>
        </ul>
      </div>
      </template>

      <!-- Bills -->
      <template v-else-if="tab === 'bills'">
        <div class="card" style="margin-bottom:1.5rem">
          <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
            <span class="card-title">When to pay each bill</span>
            <label style="font-size:0.8rem;display:flex;align-items:center;gap:0.35rem;cursor:pointer">
              <input v-model="attentionOnly" type="checkbox" style="width:auto" /> Only bills that need attention
            </label>
          </div>
          <p style="font-size:0.8rem;color:var(--text-muted);margin:0 0 0.75rem">
            Next {{ Math.min(45, ins.days) }} days, plus any late payment in the window. Paying early only saves money on
            interest-bearing debt (credit cards, HELOCs, loan groups). For regular bills it just shrinks your cushion.
          </p>
        <div v-if="timingRows.length === 0" class="empty-state" style="padding:1rem">
          <p>{{ attentionOnly ? 'Nothing needs attention: every bill is covered on time.' : 'No payments due in this period.' }}</p>
        </div>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Due</th>
                <th>Bill</th>
                <th style="text-align:right">Amount</th>
                <th>Status</th>
                <th>Pay early?</th>
                <th>What to do</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in timingRows" :key="i" :style="r.status === 'late' ? 'background:var(--danger-light)' : ''">
                <td style="white-space:nowrap;font-size:0.85rem">{{ fmtDateShort(r.dueDate) }}</td>
                <td style="font-size:0.85rem">
                  <div style="font-weight:500">{{ billName(r.name) }}</div>
                  <div style="font-size:0.72rem;color:var(--text-muted)">
                    {{ KIND_LABELS[r.kind] }}<template v-if="r.sourceAccount"> · from {{ r.sourceAccount }}</template>
                  </div>
                </td>
                <td style="text-align:right;font-weight:600;white-space:nowrap">
                  {{ currency(r.amount) }}<span v-if="r.estimated" title="Estimated amount (floating bill)"> ~</span>
                </td>
                <td><span class="badge" :class="statusBadge(r).cls">{{ statusBadge(r).label }}</span></td>
                <td style="font-size:0.8rem;white-space:nowrap">
                  <span v-if="r.earlySavings > 0" class="positive" style="font-weight:600">
                    Saves {{ currency(r.earlySavings) }}
                    <div style="font-weight:400;color:var(--text-muted)">on {{ fmtDateShort(r.payEarlyDate) }} ({{ r.daysEarly }}d early)</div>
                  </span>
                  <span v-else-if="r.status === 'already_paid'" style="color:var(--text-muted)">-</span>
                  <span v-else style="color:var(--text-muted)">No benefit</span>
                </td>
                <td style="font-size:0.8rem;max-width:420px">
                  {{ r.advice }}
                  <ul v-if="r.fixes.length" style="margin:0.35rem 0 0;padding-left:1rem">
                    <li v-for="(f, j) in r.fixes" :key="j">{{ f }}</li>
                  </ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        </div>

        <div class="card" style="margin-bottom:1.5rem">
          <div class="card-header"><span class="card-title">Better due dates</span></div>
          <DueDateMoves @changed="refetchAll()" />
        </div>
      </template>

      <!-- Debt -->
      <template v-else-if="tab === 'debt'">
        <div v-if="ins.promos.length" class="card" style="margin-bottom:1.5rem">
          <div class="card-header"><span class="card-title">0% promo deadlines</span></div>
          <p class="muted" style="font-size:0.8rem;margin:0 0 0.75rem">
            Each card payment gives every promo its share first, so it's paid off before it expires. Status is checked
            against the whole year-long plan.
          </p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Promo</th>
                <th style="text-align:right">Balance</th>
                <th>Expires</th>
                <th style="text-align:right">Needed / mo</th>
                <th style="text-align:right">Deferred interest at stake</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in ins.promos" :key="p.card + p.promoName">
                <td>{{ p.promoName }} <span style="color:var(--text-muted);font-size:0.8rem">· {{ p.card }}</span></td>
                <td style="text-align:right">{{ currency(p.balance) }}</td>
                <td style="white-space:nowrap">{{ fmtDate(p.expires) }} <span style="color:var(--text-muted);font-size:0.75rem">({{ p.daysLeft }}d)</span></td>
                <td style="text-align:right">{{ currency(p.monthlyNeeded) }}</td>
                <td style="text-align:right" class="negative">{{ currency(p.interestAtRisk) }}</td>
                <td>
                  <span v-if="p.onTrack === true" class="badge badge-success">On track</span>
                  <span v-else-if="p.onTrack === false" class="badge badge-danger">Short {{ currency(p.shortfall) }}</span>
                  <span v-else class="badge badge-info">After this window</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        </div>

        <div class="card" style="margin-bottom:1.5rem">
          <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
            <span class="card-title">Pay down debt faster</span>
            <span class="muted" style="font-size:0.78rem">A fixed extra amount each month, on top of your bills</span>
          </div>
          <DebtBoost />
        </div>

      <div v-for="g in ins.groups" :key="g.groupName" class="card" style="margin-bottom:1.5rem">
        <div class="card-header">
          <span class="card-title">{{ g.groupName }}: how the {{ currency(g.payment) }} payment is split</span>
        </div>
        <div class="grid grid-2">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Loan</th>
                  <th style="text-align:right">Balance</th>
                  <th style="text-align:right">APR</th>
                  <th style="text-align:right">Interest / mo</th>
                  <th style="text-align:right">Gets next payment</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in g.members" :key="m.accountName">
                  <td>
                    {{ m.accountName }}
                    <span v-if="m.accountName === g.highestRateMember && g.reallocationSavings > 0" class="badge badge-warning" style="margin-left:0.25rem">highest rate</span>
                  </td>
                  <td style="text-align:right">{{ currency(m.balance) }}</td>
                  <td style="text-align:right">{{ pct(m.apr, 2) }}</td>
                  <td style="text-align:right">{{ currency(m.monthlyInterest) }}</td>
                  <td style="text-align:right;font-weight:600">{{ currency(m.nextPaymentShare) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>If you...</th>
                  <th style="text-align:right">Paid off in</th>
                  <th style="text-align:right">Total interest</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Keep the current split</td>
                  <td style="text-align:right">{{ monthsText(g.current) }}</td>
                  <td style="text-align:right">{{ interestText(g.current) }}</td>
                </tr>
                <tr v-if="g.members.length > 1">
                  <td>Send extra to the highest rate first</td>
                  <td style="text-align:right">{{ monthsText(g.highestRateFirst) }}</td>
                  <td style="text-align:right" :class="g.reallocationSavings > 0 ? 'positive' : ''">{{ interestText(g.highestRateFirst) }}</td>
                </tr>
                <tr>
                  <td>Pay {{ currency(g.withExtra.extraMonthly ?? 0) }} more each month</td>
                  <td style="text-align:right">{{ monthsText(g.withExtra) }}</td>
                  <td style="text-align:right" :class="g.withExtra.paysOff ? 'positive' : ''">{{ interestText(g.withExtra) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!g.current.paysOff" style="font-size:0.8rem;color:var(--danger);margin:0.5rem 0 0">
              The payment doesn't cover the {{ currency(g.monthlyInterest) }} of monthly interest, so the balance grows.
            </p>
            <p v-else-if="g.reallocationSavings > 0 && g.suggestedFixedAmount" style="font-size:0.8rem;color:var(--text-muted);margin:0.5rem 0 0">
              To aim at {{ g.highestRateMember }}: on the Bill Groups page set it to <strong>Fixed {{ currency(g.suggestedFixedAmount) }}</strong>,
              leaving the others enough to cover their interest. Your servicer must also apply payments that way.
            </p>
          </div>
        </div>
      </div>

        <div class="card" style="margin-bottom:1.5rem">
          <div class="card-header"><span class="card-title">When will I be debt-free?</span></div>
          <DebtPayoffEstimate />
        </div>
      </template>

      <!-- Can I afford it? -->
      <template v-else>
        <div class="card" style="margin-bottom:1.5rem">
          <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
            <span class="card-title">When can I buy it?</span>
            <span class="muted" style="font-size:0.78rem">Read from the plan, the same way as Safe to spend on the dashboard</span>
          </div>
          <PurchasePlanner />
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import Icon from '../components/Icon.vue'
import { ref, computed, watch } from 'vue'
import { useApolloClient, useMutation, useQuery } from '@vue/apollo-composable'
import { useRoute, useRouter } from 'vue-router'
import { GET_PAYMENT_INSIGHTS, GET_PAYMENT_PLAN, GET_SETTINGS, UPDATE_SETTINGS } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { COMPARE_STRATEGIES, GET_STRATEGY_TARGETS } from '../graphql/tools'
import { currency, fmtDate, fmtDateShort, pct, billName } from '../utils/format'
import InsightList from '../components/InsightList.vue'
import DebtBoost from '../components/DebtBoost.vue'
import DueDateMoves from '../components/DueDateMoves.vue'
import PurchasePlanner from '../components/PurchasePlanner.vue'
import DebtPayoffEstimate from '../components/DebtPayoffEstimate.vue'
import PeriodSelect from '../components/PeriodSelect.vue'
import { PERIODS, evictPlan, planDays } from '../utils/plan'
import type { AppSettings, BillTiming, GroupPayoff, MutationPayload, OutcomeSummary, PaymentInsights, PaymentPlan } from '../types'

interface Strategy {
  goal: string; label: string; finalCash: number; endingDebt: number; lowestChecking: number | null; late: number
  interestPaid: number; interestEarned: number; fees: number; problems: number; extraTotal: number
}

// How far ahead to show (shared with Timeline and What-if; it's the same plan either way)
const days = planDays
const periodLabel = computed(() => PERIODS.find(p => p.days === days.value)?.label ?? `${days.value} days`)

const TABS = [
  { key: 'overview', label: 'Overview', icon: 'zap' },
  { key: 'bills', label: 'Bills', icon: 'bills' },
  { key: 'debt', label: 'Debt', icon: 'card' },
  { key: 'afford', label: 'Can I afford it?', icon: 'banknote' },
]
// Old links (?tool=...) land on the tab that has that tool now
const TOOL_TABS: Record<string, string> = { debt: 'debt', dates: 'bills', buy: 'afford' }
const route = useRoute()
const router = useRouter()
const tab = ref(localStorage.getItem('budget-plan-tab') || 'overview')
watch(() => [route.query.tab, route.query.tool], ([t, tool]) => {
  const key = typeof t === 'string' ? t : (typeof tool === 'string' ? TOOL_TABS[tool] : undefined)
  if (key && TABS.some(x => x.key === key)) tab.value = key
}, { immediate: true })
function setTab(key: string) {
  tab.value = key
  localStorage.setItem('budget-plan-tab', key)
  router.replace({ query: { ...route.query, tab: key, tool: undefined } })
}
const violationsOpen = ref(false)
const attentionOnly = ref(false)

// ── Goal: the plan the whole app follows (saved in Settings) ──────────
const GOALS = [
  { key: 'maximize_discretionary', label: 'Most cash', icon: 'banknote', hint: 'Keep as much cash on hand as possible' },
  { key: 'minimize_interest', label: 'Least interest', icon: 'trendingDown', hint: 'Pay interest-bearing debt as early as it makes sense' },
  { key: 'payoff_credit_account', label: 'Pay off a card', icon: 'card', hint: 'Send spare cash to one card after each paycheck' },
]
const goal = ref<string>('maximize_discretionary')
const target = ref<string>('')
const compareOpen = ref(false)
const savingGoal = ref(false)

const { result: settingsResult } = useQuery<{ settings: string | AppSettings }>(GET_SETTINGS)
watch(settingsResult, r => {
  if (!r?.settings) return
  const s = (typeof r.settings === 'string' ? JSON.parse(r.settings) : r.settings) as AppSettings
  goal.value = s.optimizer_goal || 'maximize_discretionary'
  if (s.optimizer_target) target.value = s.optimizer_target
}, { immediate: true })

const { result: targetsResult } = useQuery<{ strategyTargets: string[] }>(GET_STRATEGY_TARGETS)
const targets = computed(() => targetsResult.value?.strategyTargets ?? [])
watch(targets, list => {
  if (!list.includes(target.value)) target.value = list[0] ?? ''
}, { immediate: true })

const { mutate: saveSettings } = useMutation<{ updateSettings: MutationPayload }>(UPDATE_SETTINGS)
const { resolveClient } = useApolloClient()

/** Switch the plan the whole app follows (dashboard, bills, timeline, alerts, digest). */
async function setGoal(key: string, card?: string) {
  const prev = { goal: goal.value, target: target.value }
  goal.value = key
  if (card) target.value = card
  savingGoal.value = true
  const ok = await runMutation(() => saveSettings({ variables: { changes: JSON.stringify({
    optimizer_goal: key, optimizer_target: key === 'payoff_credit_account' ? target.value : '',
  }) } }), 'updateSettings', { failMessage: 'Could not switch the plan' })
  savingGoal.value = false
  if (!ok) { goal.value = prev.goal; target.value = prev.target; return }
  // Everything that shows the plan has to be recomputed
  evictPlan(resolveClient().cache)
  refetchAll()
}
const goalHint = computed(() => GOALS.find(g => g.key === goal.value)?.hint ?? '')

// No goal given: the server answers for the plan the app follows (the one saved above)
const insightVars = computed(() => ({ days: days.value }))

const { result, loading, error, refetch } = useQuery<{ paymentInsights: PaymentInsights }>(
  GET_PAYMENT_INSIGHTS, () => ({ variables: insightVars.value })
)

const { result: cmpResult, loading: cmpLoading, error: cmpError } = useQuery<{ compareStrategies: Strategy[] }>(
  COMPARE_STRATEGIES,
  () => ({ variables: { days: days.value, targetAccount: target.value || null }, enabled: compareOpen.value }),
)
const strategies = computed(() => cmpResult.value?.compareStrategies ?? [])
const bestCash = computed(() => Math.max(...strategies.value.map(x => x.finalCash)))
const leastInterest = computed(() => Math.min(...strategies.value.map(x => x.interestPaid)))
const leastDebt = computed(() => Math.min(...strategies.value.map(x => x.endingDebt)))
const { result: planResult, refetch: refetchPlan } = useQuery<{ paymentPlan: PaymentPlan }>(
  GET_PAYMENT_PLAN, () => ({ variables: { days: days.value } })
)

function refetchAll() {
  refetch()
  refetchPlan()
}
const lateCount = computed(() => ins.value?.optimized.latePayments.length ?? 0)
const offTrackPromos = computed(() => (ins.value?.promos ?? []).filter(p => p.onTrack === false).length)

const ins = computed(() => result.value?.paymentInsights)
const plan = computed(() => planResult.value?.paymentPlan)

const headlineColor = computed(() => {
  const sev = new Set(ins.value?.insights.map(i => i.severity))
  if (sev.has('urgent')) return 'var(--danger)'
  if (sev.has('warning')) return 'var(--warning)'
  return 'var(--success)'
})

// ── Comparison table ──────────────────────────────────────────────────

interface CompRow {
  label: string
  hint?: string
  base: number
  opt: number
  /** +1 when a higher value is better, -1 when lower is better */
  better: 1 | -1
  fmt: (v: number) => string
  baseNote?: string
  optNote?: string
}

const lowNote = (s: OutcomeSummary) =>
  s.lowestCheckingDate ? `${s.lowestCheckingAccount ? `${s.lowestCheckingAccount} on ` : ''}${fmtDateShort(s.lowestCheckingDate)}` : undefined

const comparisonRows = computed<CompRow[]>(() => {
  const i = ins.value
  if (!i) return []
  const b = i.onDueDate, o = i.optimized
  const rows: CompRow[] = [
    { label: 'Late or missed payments', hint: 'Bills there isn\'t enough money for on the due date',
      base: b.latePayments.length, opt: o.latePayments.length, better: -1, fmt: v => String(v) },
    { label: 'Lowest checking balance', hint: 'Your tightest point (all checking accounts together)',
      base: b.lowestChecking ?? 0, opt: o.lowestChecking ?? 0, better: 1, fmt: currency,
      baseNote: lowNote(b), optNote: lowNote(o) },
    { label: 'Cash at the end', base: b.endingCash, opt: o.endingCash, better: 1, fmt: currency },
    { label: 'Debt at the end', hint: 'Cards, loans, HELOC and mortgage', base: b.endingDebt, opt: o.endingDebt, better: -1, fmt: currency },
    { label: 'Interest charged', hint: 'On cards and HELOCs', base: b.interestCharged, opt: o.interestCharged, better: -1, fmt: currency },
    { label: 'Interest earned', hint: 'On savings / checking', base: b.interestEarned, opt: o.interestEarned, better: 1, fmt: currency },
  ]
  if (b.fees || o.fees) {
    rows.push({ label: 'Late & overdraft fees', hint: 'Using the fees in Settings → Planning (and each bill’s own late fee)',
      base: b.fees, opt: o.fees, better: -1, fmt: currency })
  }
  if (b.pendingDeferredInterest || o.pendingDeferredInterest) {
    rows.push({ label: 'Deferred promo interest at risk', hint: 'If promo money still owed at the end isn\'t paid before the promo expires',
      base: b.pendingDeferredInterest, opt: o.pendingDeferredInterest, better: -1, fmt: currency })
  }
  if (b.unpaidBills || o.unpaidBills) {
    rows.push({ label: 'Unpaid bills', hint: 'Bills that can’t be paid in the window — they’re still owed',
      base: b.unpaidBills, opt: o.unpaidBills, better: -1, fmt: currency })
  }
  rows.push({ label: 'Overall', hint: 'The bottom line: cash − debt − unpaid bills (and promo interest about to hit)',
    base: b.outcome ?? b.netPosition, opt: o.outcome ?? o.netPosition, better: 1, fmt: currency })
  return rows
})

function diffText(row: CompRow): string {
  const d = row.opt - row.base
  if (Math.abs(d) < 0.005) return 'same'
  const s = row.fmt(Math.abs(d))
  return `${d > 0 ? '+' : '−'}${s}`
}

function diffClass(row: CompRow): string {
  const d = (row.opt - row.base) * row.better
  if (Math.abs(d) < 0.005) return 'neutral'
  return d > 0 ? 'positive' : 'negative'
}

// ── Bill timing ───────────────────────────────────────────────────────

const KIND_LABELS: Record<BillTiming['kind'], string> = {
  bill: 'Bill', floating: 'Variable bill', credit: 'Card payment', mortgage: 'Loan payment',
  heloc: 'HELOC payment', group: 'Loan group',
}

const timingRows = computed(() => {
  const rows = ins.value?.billTiming ?? []
  if (!attentionOnly.value) return rows
  return rows.filter(r => r.status === 'late' || r.earlySavings > 0
    || (r.cushionIfEarly != null && r.cushionIfEarly < 0 && r.earlySavings > 0))
})

function statusBadge(r: BillTiming): { label: string; cls: string } {
  if (r.status === 'already_paid') return { label: 'Paid', cls: 'badge-success' }
  if (r.status === 'late' && r.planStatus === 'paid') return { label: 'On time with plan', cls: 'badge-warning' }
  if (r.status === 'late') return { label: 'Short', cls: 'badge-danger' }
  return { label: 'On time', cls: 'badge-success' }
}

// ── Groups ────────────────────────────────────────────────────────────

function monthsText(p: GroupPayoff): string {
  if (!p.paysOff || p.months == null) return 'Never'
  const y = Math.floor(p.months / 12), m = p.months % 12
  return y ? `${y}y ${m}m` : `${m} mo`
}

function interestText(p: GroupPayoff): string {
  return p.paysOff && p.interest != null ? currency(p.interest) : '-'
}

// ── Optimizer moves ───────────────────────────────────────────────────

const moveGroups = computed(() => {
  const by = new Map<string, { type: string; title: string; why: string; total: number; count: number }>()
  for (const m of ins.value?.optimizerMoves ?? []) {
    const g = by.get(m.type) ?? { type: m.type, title: m.title, why: m.why, total: 0, count: 0 }
    g.total += m.amount
    g.count++
    by.set(m.type, g)
  }
  return [...by.values()]
})

function eventIcon(type: string): string {
  const map: Record<string, string> = {
    SAVINGS_SWEEP: 'arrowDown', SAVINGS_RECALL: 'arrowUp',
    HELOC_PARK: 'parking', HELOC_RECALL: 'arrowUp',
    EXTRA_CREDIT_PAYMENT: 'card', PROMO_PAYOFF: 'tag',
  }
  return map[type] || 'pin'
}

function eventColor(type: string): string {
  const map: Record<string, string> = {
    SAVINGS_SWEEP: 'var(--success)',
    SAVINGS_RECALL: 'var(--warning)',
    HELOC_PARK: 'var(--primary)',
    HELOC_RECALL: 'var(--warning)',
    EXTRA_CREDIT_PAYMENT: 'var(--danger)',
    PROMO_PAYOFF: 'var(--danger)',
  }
  return map[type] || 'var(--text-muted)'
}

function eventBadgeClass(type: string): string {
  const map: Record<string, string> = {
    SAVINGS_SWEEP: 'badge-success',
    SAVINGS_RECALL: 'badge-warning',
    HELOC_PARK: 'badge-info',
    HELOC_RECALL: 'badge-warning',
    EXTRA_CREDIT_PAYMENT: 'badge-danger',
    PROMO_PAYOFF: 'badge-danger',
  }
  return map[type] || 'badge-info'
}
</script>

<style scoped>
.goal-card { margin-bottom: 1rem; }
.goal-bar { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.goal-label { font-size: 0.82rem; font-weight: 600; color: var(--text-muted); }
.goal-note { font-size: 0.78rem; color: var(--text-muted); margin: 0.5rem 0 0; }
.compare { border-top: 1px solid var(--border); margin-top: 0.85rem; padding-top: 0.85rem; }
.compare-title { font-weight: 600; font-size: 0.88rem; margin-bottom: 0.5rem; }
.plan-tabs { margin-bottom: 1.25rem; }
.tab-count { display: inline-grid; place-items: center; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px;
  background: var(--danger); color: #fff; font-size: 0.68rem; font-weight: 700; margin-left: 0.15rem; }
.more { margin-top: 0.75rem; font-size: 0.8rem; color: var(--text-muted); }
.more > summary { cursor: pointer; font-weight: 550; }
.more p { margin: 0.4rem 0 0; line-height: 1.5; }
.row-current td { background: var(--primary-light); }
td.best { color: var(--success-text); font-weight: 650; }
.cell-note { font-size: 0.72rem; color: var(--text-muted); }
.move-title { display: flex; align-items: center; gap: 0.4rem; font-weight: 600; font-size: 0.9rem; }
</style>
