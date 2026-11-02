<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Timeline</h2>
        <p class="view-sub">
          Every bill, paycheck and move ahead, day by day, following your
          <router-link to="/optimizer" class="plan-link">{{ planLabel }} plan</router-link>.
        </p>
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center">
        <PeriodSelect />
        <RowMenu text="Download" icon="download" :items="downloadItems" />
        <button class="btn btn-outline" @click="refetch()"><Icon name="refresh" :size="15" /> Refresh</button>
      </div>
    </div>

    <div v-if="loading && !result" class="loading">Calculating projection...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="proj">
      <!-- Summary cards: money in − money out = change in cash -->
      <div class="grid grid-4" style="margin-bottom:1.5rem">
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(proj.totalIncome) }}</div>
          <div class="stat-label">Money in</div>
          <div class="stat-sub">Paychecks and deposits</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value negative">{{ currency(proj.totalExpenses) }}</div>
          <div class="stat-label">Money out</div>
          <div class="stat-sub">
            Bills, payments, spending and fees ·
            cash {{ proj.netChange >= 0 ? 'up' : 'down' }} {{ currency(Math.abs(proj.netChange)) }}
          </div>
        </div>
        <div class="card stat-card">
          <div class="stat-value" :class="(proj.lowestChecking ?? 0) < (proj.cushion ?? 0) ? 'negative' : 'neutral'">{{ currency(proj.lowestChecking ?? 0) }}</div>
          <div class="stat-label">Lowest checking</div>
          <div class="stat-sub">
            <template v-if="proj.lowestCheckingDate">{{ fmtDateShort(proj.lowestCheckingDate) }} · </template>cushion {{ currency(proj.cushion ?? 0) }}
          </div>
          <div v-if="(proj.lowestSpendable ?? 0) > (proj.lowestChecking ?? 0) + 1" class="stat-sub">
            {{ currency(proj.lowestSpendable ?? 0) }} counting money the plan parks in savings (what Safe to spend uses)
          </div>
        </div>
        <div class="card stat-card">
          <div class="stat-value" :class="proj.netFinalBalance >= 0 ? 'positive' : 'negative'">{{ currency(proj.netFinalBalance) }}</div>
          <div class="stat-label">Net worth at the end</div>
          <div class="stat-sub">
            Cash {{ currency(proj.totalFinalBalance) }}
            <span v-if="totalDebt > 0"> · Debt {{ currency(totalDebt) }}</span>
            <span v-if="(proj.otherAssets ?? 0) > 0"> · Other {{ currency(proj.otherAssets ?? 0) }}</span>
          </div>
        </div>
      </div>

      <!-- Balance chart -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header">
          <span class="card-title">Balance over time</span>
          <label style="font-size:0.8rem;display:flex;align-items:center;gap:0.35rem;cursor:pointer;color:var(--text-muted)">
            <input type="checkbox" v-model="showPerAccount" /> Per-account lines
          </label>
        </div>
        <div style="height:350px">
          <Line :data="chartData" :options="chartOptions" />
        </div>
      </div>

      <!-- Financial Calendar / event list / month by month -->
      <div class="card">
        <div class="card-header" style="flex-wrap:wrap;gap:0.75rem">
          <div class="segmented" role="tablist" aria-label="View">
            <button v-for="v in VIEWS" :key="v.key" role="tab" :aria-selected="calView === v.key" :class="{ active: calView === v.key }" @click="calView = v.key">
              <Icon :name="v.icon" :size="15" /> {{ v.label }}
            </button>
          </div>
          <div v-if="calView === 'list'" class="chip-group" style="margin:0">
            <button v-for="f in FILTERS" :key="f.key" class="chip" :class="{ selected: listFilter === f.key }" @click="listFilter = f.key">{{ f.label }}</button>
          </div>
          <div v-if="calView === 'calendar'" style="display:flex;align-items:center;gap:0.5rem">
            <button class="btn btn-outline btn-sm btn-icon" aria-label="Previous month" @click="prevMonth"><Icon name="chevronLeft" :size="16" /></button>
            <span style="font-weight:700;min-width:140px;text-align:center">{{ calendarMonthLabel }}</span>
            <button class="btn btn-outline btn-sm btn-icon" aria-label="Next month" @click="nextMonth"><Icon name="chevronRight" :size="16" /></button>
          </div>
        </div>

        <!-- Every event, filterable -->
        <div v-if="calView === 'list'">
          <div v-if="!listGroups.length" class="empty-state"><p>Nothing in this period.</p></div>
          <div v-for="g in listGroups" :key="g.date" class="ev-day">
            <div class="ev-date">
              <strong>{{ fmtDayShort(g.date) }}</strong>
              <span>{{ currency(g.endCash) }} in checking &amp; savings after</span>
            </div>
            <div v-for="(e, i) in g.events" :key="i" class="ev-row" :class="eventClass(e)">
              <span class="ev-icon"><Icon :name="eventIcon(e.eventType)" :size="15" /></span>
              <span class="ev-desc">
                {{ billName(e.description) }}
                <small>{{ eventTypeLabel(e.eventType) }}<template v-if="e.sourceAccount"> · {{ e.sourceAccount }}</template><template v-if="e.status === 'deferred'"> · can't be paid yet</template></small>
              </span>
              <span class="ev-amt" :class="e.eventType === 'INCOME' ? 'positive' : ''">{{ e.eventType === 'INCOME' ? '+' : '' }}{{ currency(Math.abs(e.amount)) }}</span>
            </div>
          </div>
        </div>

        <!-- Balances on the last day -->
        <div v-else-if="calView === 'end'">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th style="text-align:right">Projected balance</th>
              </tr>
            </thead>
            <tbody>
              <!-- Bank accounts (assets) -->
              <tr v-if="Object.keys(parsedBalances).length" class="section-header-row">
                <td colspan="2" style="font-weight:700;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;padding-top:0.75rem">
                  Bank Accounts
                </td>
              </tr>
              <tr v-for="(bal, key) in parsedBalances" :key="'bank-' + key">
                <td>{{ formatAccountName(key as string) }}</td>
                <td style="text-align:right;font-weight:600" :class="bal >= 0 ? 'positive' : 'negative'">{{ currency(bal) }}</td>
              </tr>
              <!-- Credit cards (debt) -->
              <template v-if="Object.keys(parsedCreditBalances).length">
                <tr class="section-header-row">
                  <td colspan="2" style="font-weight:700;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;padding-top:0.75rem">
                    Credit Cards
                  </td>
                </tr>
                <tr v-for="(bal, key) in parsedCreditBalances" :key="'credit-' + key">
                  <td>{{ formatAccountName(key as string) }}</td>
                  <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                </tr>
              </template>
              <!-- Mortgages (debt) -->
              <template v-if="Object.keys(parsedMortgageBalances).length">
                <tr class="section-header-row">
                  <td colspan="2" style="font-weight:700;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;padding-top:0.75rem">
                    Mortgages
                  </td>
                </tr>
                <tr v-for="(bal, key) in parsedMortgageBalances" :key="'mort-' + key">
                  <td>{{ formatAccountName(key as string) }}</td>
                  <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                </tr>
              </template>
              <!-- HELOCs (debt) -->
              <template v-if="Object.keys(parsedHelocBalances).length">
                <tr class="section-header-row">
                  <td colspan="2" style="font-weight:700;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;padding-top:0.75rem">
                    HELOCs
                  </td>
                </tr>
                <tr v-for="(bal, key) in parsedHelocBalances" :key="'heloc-' + key">
                  <td>{{ formatAccountName(key as string) }}</td>
                  <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                </tr>
              </template>
              <tr v-if="(proj.otherAssets ?? 0) > 0">
                <td>Homes, cars and other assets</td>
                <td style="text-align:right;font-weight:600" class="positive">{{ currency(proj.otherAssets ?? 0) }}</td>
              </tr>
              <!-- Net total -->
              <tr style="border-top:2px solid var(--border-strong);font-weight:700">
                <td>Net worth</td>
                <td style="text-align:right" :class="proj.netFinalBalance >= 0 ? 'positive' : 'negative'">
                  {{ currency(proj.netFinalBalance) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        </div>

        <!-- Month by month -->
        <div v-else-if="calView === 'months'">
          <div v-if="monthsLoading && !months.length" class="loading">Adding up each month...</div>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Month</th>
                  <th style="text-align:right">Income</th>
                  <th style="text-align:right">Bills &amp; payments</th>
                  <th style="text-align:right">Everyday</th>
                  <th style="text-align:right">Net</th>
                  <th style="text-align:right">Cash at end</th>
                  <th style="text-align:right">Debt at end</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in months" :key="m.month">
                  <td style="font-weight:550">{{ monthLabel(m.month) }}</td>
                  <td style="text-align:right" class="positive">{{ currency(m.income) }}</td>
                  <td style="text-align:right">{{ currency(m.payments) }}</td>
                  <td style="text-align:right">{{ currency(m.spending) }}</td>
                  <td style="text-align:right;font-weight:600" :class="m.net >= 0 ? 'positive' : 'negative'">{{ m.net >= 0 ? '+' : '' }}{{ currency(m.net) }}</td>
                  <td style="text-align:right">{{ currency(m.endCash) }}</td>
                  <td style="text-align:right">{{ currency(m.endDebt) }}</td>
                </tr>
              </tbody>
            </table>
            <p class="muted" style="font-size:0.8rem;margin:0.6rem 0 0">Months at the edges are partial. Fees and interest are included in the net.</p>
          </div>
        </div>

        <template v-else>
        <!-- Day-of-week headers -->
        <div class="cal-grid">
          <div v-for="dow in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']" :key="dow" class="cal-header">{{ dow }}</div>

          <!-- Calendar cells -->
          <div
            v-for="(cell, idx) in calendarCells"
            :key="idx"
            class="cal-cell"
            :class="{
              'cal-empty': !cell.date,
              'cal-today': cell.isToday,
              'cal-has-events': cell.hasEvents,
              'cal-selected': cell.date === selectedDate,
              'cal-outside': cell.outsideMonth,
              'cal-has-income': cell.hasIncome,
              'cal-has-expense': cell.hasExpense,
              'cal-has-deferred': cell.hasDeferred,
              'cal-has-transfer': cell.hasTransfer,
            }"
            @click="cell.date && selectDate(cell.date)"
          >
            <template v-if="cell.date">
              <div class="cal-day-num">{{ cell.dayNum }}</div>
              <div v-if="cell.hasEvents" class="cal-dots">
                <span v-if="cell.hasIncome" class="cal-dot dot-income" title="Income"></span>
                <span v-if="cell.hasExpense" class="cal-dot dot-expense" title="Expense"></span>
                <span v-if="cell.hasTransfer" class="cal-dot dot-transfer" title="Optimization Transfer"></span>
                <span v-if="cell.hasDeferred" class="cal-dot dot-deferred" title="Deferred"></span>
              </div>
              <div v-if="cell.eventCount" class="cal-event-count">
                {{ cell.eventCount }} event{{ cell.eventCount > 1 ? 's' : '' }}
              </div>
            </template>
          </div>
        </div>

        <!-- Selected day detail panel -->
        <div v-if="selectedDayData" class="cal-detail">
          <div class="cal-detail-header">
            <h3>{{ formatDetailDate(selectedDate!) }}</h3>
            <button class="btn btn-outline btn-sm" @click="selectedDate = null">&times; close</button>
          </div>

          <!-- Events for the day -->
          <div v-if="selectedDayData.events.length" style="margin-bottom:1.25rem">
            <h4>Transactions</h4>
            <div class="cal-event-list">
              <div
                v-for="(evt, i) in selectedDayData.events"
                :key="i"
                class="cal-event-item"
                :class="eventClass(evt)"
              >
                <div class="cal-event-icon"><Icon :name="eventIcon(evt.eventType)" :size="16" /></div>
                <div class="cal-event-info">
                  <div class="cal-event-desc">{{ billName(evt.description) }}</div>
                  <div class="cal-event-source" v-if="evt.sourceBank || evt.sourceAccount">
                    <template v-if="isTransferType(evt.eventType)">
                      ↔ {{ evt.description }}
                    </template>
                    <template v-else-if="evt.eventType === 'EXTRA_CREDIT_PAYMENT' || evt.eventType === 'PROMO_PAYOFF'">
                      Paid from: {{ evt.sourceBank }}<template v-if="evt.sourceAccount"> / {{ evt.sourceAccount }}</template>
                    </template>
                    <template v-else-if="isExpenseType(evt.eventType)">
                      Paid from: {{ evt.sourceBank }}<template v-if="evt.sourceAccount"> / {{ evt.sourceAccount }}</template>
                    </template>
                    <template v-else-if="evt.eventType === 'INCOME'">
                      Deposited to accounts
                    </template>
                    <template v-else>
                      {{ evt.sourceBank }}<template v-if="evt.sourceAccount"> / {{ evt.sourceAccount }}</template>
                    </template>
                  </div>
                  <div v-if="evt.status === 'deferred'" class="cal-event-warning">
                    Insufficient funds — payment deferred
                  </div>
                </div>
                <div class="cal-event-amount" :class="evt.amount >= 0 ? 'positive' : 'negative'">
                  {{ currency(evt.amount) }}
                </div>
              </div>
            </div>
          </div>

          <!-- Account balances at end of day -->
          <div>
            <h4>Expected account balances (end of day)</h4>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Account</th>
                    <th style="text-align:right">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(bal, acct) in selectedDayBalances" :key="'b-' + acct">
                    <td>{{ formatAccountName(acct as string) }}</td>
                    <td style="text-align:right;font-weight:600" :class="bal >= 0 ? 'positive' : 'negative'">
                      {{ currency(bal) }}
                    </td>
                  </tr>
                  <template v-if="Object.keys(selectedDayCreditBalances).length">
                    <tr v-for="(bal, acct) in selectedDayCreditBalances" :key="'c-' + acct">
                      <td>{{ formatAccountName(acct as string) }}</td>
                      <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                    </tr>
                  </template>
                  <template v-if="Object.keys(selectedDayMortgageBalances).length">
                    <tr v-for="(bal, acct) in selectedDayMortgageBalances" :key="'m-' + acct">
                      <td>{{ formatAccountName(acct as string) }}</td>
                      <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                    </tr>
                  </template>
                  <template v-if="Object.keys(selectedDayHelocBalances).length">
                    <tr v-for="(bal, acct) in selectedDayHelocBalances" :key="'h-' + acct">
                      <td>{{ formatAccountName(acct as string) }}</td>
                      <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                    </tr>
                  </template>
                  <tr style="border-top:2px solid var(--border-strong);font-weight:700">
                    <td>Net Total</td>
                    <td style="text-align:right" :class="selectedDayNetTotal >= 0 ? 'positive' : 'negative'">
                      {{ currency(selectedDayNetTotal) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- No date selected hint -->
        <div v-else-if="calendarDaysMap.size > 0" class="cal-hint">
          Click on a day with events to see payment details and expected balances.
        </div>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import RowMenu from '../components/RowMenu.vue'
import PeriodSelect from '../components/PeriodSelect.vue'
import { PLAN_LABELS, planDays } from '../utils/plan'
import { GET_MONTHLY_PROJECTION } from '../graphql/tools'
import Icon from '../components/Icon.vue'
import { ref, computed, watch } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend,
} from 'chart.js'
import { GET_PROJECTION } from '../graphql/queries'
import { currency, todayISO, billName, fmtDateShort } from '../utils/format'
import type { Projection, CalendarDay } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler, Legend)

// How far ahead to show (shared with Plan and What-if; it's the same plan either way)
const days = planDays
const showPerAccount = ref(true)

// ── Calendar / list / month-by-month
const VIEWS = [
  { key: 'calendar', label: 'Calendar', icon: 'calendar' },
  { key: 'list', label: 'List', icon: 'menu' },
  { key: 'months', label: 'By month', icon: 'chart' },
  { key: 'end', label: 'End balances', icon: 'accounts' },
]
const FILTERS = [
  { key: 'all', label: 'Everything' },
  { key: 'income', label: 'Income' },
  { key: 'bills', label: 'Bills' },
  { key: 'debt', label: 'Cards & loans' },
  { key: 'moves', label: 'Transfers' },
]
const calView = ref<string>(localStorage.getItem('budget-timeline-view') || 'calendar')
watch(calView, v => localStorage.setItem('budget-timeline-view', v))
const listFilter = ref('all')

function eventKind(t: string): string {
  if (t === 'INCOME' || t === 'ACCOUNT_REFILL') return 'income'
  if (isTransferType(t)) return 'moves'
  if (/CREDIT|MORTGAGE|HELOC|PROMO|BILL_GROUP/.test(t)) return 'debt'
  if (t.startsWith('BILL')) return 'bills'
  return 'other'
}
function eventTypeLabel(t: string): string {
  const labels: Record<string, string> = {
    INCOME: 'Income', BILL_PAYMENT: 'Bill', BILL_DEFERRED: 'Bill', CREDIT_PAYMENT: 'Card payment',
    MORTGAGE_PAYMENT: 'Mortgage', HELOC_PAYMENT: 'HELOC payment', BILL_GROUP_PAYMENT: 'Loan group',
    EXTRA_CREDIT_PAYMENT: 'Extra card payment', PROMO_PAYOFF: 'Promo payoff', SAVINGS_SWEEP: 'To savings',
    SAVINGS_RECALL: 'From savings', HELOC_PARK: 'Parked in HELOC', HELOC_RECALL: 'Back from HELOC',
    INTEREST: 'Interest', FEE: 'Fee', EVERYDAY_SPENDING: 'Everyday spending',
    ACCOUNT_REFILL: 'Refill', ACCOUNT_SPENDING: 'Benefit spending', EXTRA_DEBT_PAYMENT: 'Extra debt payment',
    PURCHASE: 'Purchase',
  }
  return labels[t] ?? t.replace(/_/g, ' ').toLowerCase().replace(/^./, c => c.toUpperCase())
}
const listGroups = computed(() => (proj.value?.calendarDays ?? [])
  .map(d => ({
    date: d.date,
    endCash: d.total,
    events: d.events.filter(e => e.eventType !== 'EVERYDAY_SPENDING' && e.eventType !== 'ACCOUNT_SPENDING'
      && (listFilter.value === 'all' || eventKind(e.eventType) === listFilter.value)),
  }))
  .filter(g => g.events.length))
function fmtDayShort(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}
function monthLabel(key: string) {
  return new Date(key + '-01T00:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

interface MonthRow { month: string; income: number; payments: number; spending: number; interest: number; fees: number; net: number; endCash: number; endDebt: number }
const { result: monthsResult, loading: monthsLoading } = useQuery<{ monthlyProjection: MonthRow[] }>(GET_MONTHLY_PROJECTION,
  () => ({ variables: { days: Math.max(days.value, 60) }, enabled: calView.value === 'months' }))
const months = computed(() => monthsResult.value?.monthlyProjection ?? [])

// ── Downloads
function go(url: string) { window.location.href = url }
const downloadItems = computed(() => [
  { heading: 'This projection', label: 'Every event (CSV)', icon: 'file', action: () => go(`/files/reports/timeline.csv?days=${days.value}`) },
  { label: 'Every event (Excel)', icon: 'file', action: () => go(`/files/reports/timeline.xlsx?days=${days.value}`) },
  { label: 'Month by month (Excel)', icon: 'chart', action: () => go(`/files/reports/monthly.xlsx?days=${Math.max(days.value, 60)}`) },
  { label: 'Daily balances (Excel)', icon: 'accounts', action: () => go(`/files/reports/balances.xlsx?days=${days.value}`) },
  { label: 'Bills & paydays (calendar file)', icon: 'calendar', divider: true, action: () => go('/files/calendar.ics') },
  { label: 'Print or save as PDF', icon: 'printer', action: () => window.print() },
])
const { result, loading, error, refetch } = useQuery<{ projection: Projection }>(GET_PROJECTION, () => ({ variables: { days: days.value } }))

const proj = computed(() => result.value?.projection)
const planLabel = computed(() => PLAN_LABELS[proj.value?.planGoal ?? ''] ?? 'Most cash')

/** Keep only accounts with a positive balance, typed as numbers. */
function positiveEntries(parsed: unknown): Record<string, number> {
  if (!parsed || typeof parsed !== 'object') return {}
  const out: Record<string, number> = {}
  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    const n = Number(v)
    if (n > 0) out[k] = n
  }
  return out
}

const parsedBalances = computed(() => {
  if (!proj.value?.finalBalances) return {}
  const fb = proj.value.finalBalances
  return typeof fb === 'string' ? JSON.parse(fb) : fb
})

const parsedCreditBalances = computed(() => {
  if (!proj.value?.creditFinalBalances) return {}
  const fb = proj.value.creditFinalBalances
  const parsed = typeof fb === 'string' ? JSON.parse(fb) : fb
  // Only show accounts with balance > 0
  return positiveEntries(parsed)
})

const parsedMortgageBalances = computed(() => {
  if (!proj.value?.mortgageFinalBalances) return {}
  const fb = proj.value.mortgageFinalBalances
  const parsed = typeof fb === 'string' ? JSON.parse(fb) : fb
  return positiveEntries(parsed)
})

const parsedHelocBalances = computed(() => {
  if (!proj.value?.helocFinalBalances) return {}
  const fb = proj.value.helocFinalBalances
  const parsed = typeof fb === 'string' ? JSON.parse(fb) : fb
  return positiveEntries(parsed)
})

const totalDebt = computed(() => {
  if (!proj.value) return 0
  return (proj.value.totalCreditBalance || 0) + (proj.value.totalMortgageBalance || 0) + (proj.value.totalHelocBalance || 0)
})

// ── Balance Chart ──────────────────────────────────────────────────
const accountColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16']
const debtColors = ['#ef4444', '#f97316', '#ec4899', '#dc2626', '#ea580c', '#db2777']

const chartData = computed(() => {
  if (!proj.value) return { labels: [], datasets: [] }
  const snaps = proj.value.snapshots
  const step = Math.max(1, Math.floor(snaps.length / 60))
  const sampled = snaps.filter((_, i) => i % step === 0 || i === snaps.length - 1)

  const datasets: any[] = [
    {
      label: 'Net worth',
      data: sampled.map(s => s.netTotal ?? s.total),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.08)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      borderWidth: 2,
    },
    {
      label: 'Cash (Checking/Savings)',
      data: sampled.map(s => s.total),
      borderColor: '#10b981',
      borderDash: [6, 3],
      tension: 0.3,
      pointRadius: 0,
      borderWidth: 1.5,
      fill: false,
    },
  ]

  // Add aggregate debt line if any debt exists
  const hasDebt = sampled.some(s => {
    const credit = typeof s.creditBalances === 'string' ? JSON.parse(s.creditBalances) : (s.creditBalances || {})
    const mortgage = typeof s.mortgageBalances === 'string' ? JSON.parse(s.mortgageBalances) : (s.mortgageBalances || {})
    const heloc = typeof s.helocBalances === 'string' ? JSON.parse(s.helocBalances) : (s.helocBalances || {})
    return Object.values(credit).some(v => (v as number) > 0)
      || Object.values(mortgage).some(v => (v as number) > 0)
      || Object.values(heloc).some(v => (v as number) > 0)
  })

  if (hasDebt) {
    datasets.push({
      label: 'Total Debt',
      data: sampled.map(s => {
        const credit = typeof s.creditBalances === 'string' ? JSON.parse(s.creditBalances) : (s.creditBalances || {})
        const mortgage = typeof s.mortgageBalances === 'string' ? JSON.parse(s.mortgageBalances) : (s.mortgageBalances || {})
        const heloc = typeof s.helocBalances === 'string' ? JSON.parse(s.helocBalances) : (s.helocBalances || {})
        return -(
          Object.values(credit).reduce((a, b) => (a as number) + (b as number), 0) as number
          + (Object.values(mortgage).reduce((a, b) => (a as number) + (b as number), 0) as number)
          + (Object.values(heloc).reduce((a, b) => (a as number) + (b as number), 0) as number)
        )
      }),
      borderColor: '#ef4444',
      borderDash: [6, 3],
      tension: 0.3,
      pointRadius: 0,
      borderWidth: 1.5,
      fill: false,
    })
  }

  // Add per-account lines if enabled
  if (showPerAccount.value && sampled.length > 0) {
    // Bank account lines
    const firstBalances = typeof sampled[0].balances === 'string'
      ? JSON.parse(sampled[0].balances)
      : sampled[0].balances
    const accountKeys = Object.keys(firstBalances || {})

    accountKeys.forEach((key, idx) => {
      datasets.push({
        label: key.replace(':', ' / '),
        data: sampled.map(s => {
          const bals = typeof s.balances === 'string' ? JSON.parse(s.balances) : s.balances
          return bals?.[key] ?? 0
        }),
        borderColor: accountColors[idx % accountColors.length],
        borderDash: [4, 2],
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 1.5,
        fill: false,
      })
    })

    // Credit card lines (shown as negative)
    const firstCredit = typeof sampled[0].creditBalances === 'string'
      ? JSON.parse(sampled[0].creditBalances)
      : (sampled[0].creditBalances || {})
    const creditKeys = Object.keys(firstCredit).filter(k => {
      return sampled.some(s => {
        const cb = typeof s.creditBalances === 'string' ? JSON.parse(s.creditBalances) : (s.creditBalances || {})
        return (cb[k] || 0) > 0
      })
    })

    creditKeys.forEach((key, idx) => {
      datasets.push({
        label: key.replace(':', ' / '),
        data: sampled.map(s => {
          const cb = typeof s.creditBalances === 'string' ? JSON.parse(s.creditBalances) : (s.creditBalances || {})
          return -(cb[key] || 0)
        }),
        borderColor: debtColors[idx % debtColors.length],
        borderDash: [2, 2],
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 1,
        fill: false,
      })
    })

    // HELOC lines (shown as negative)
    const firstHeloc = typeof sampled[0].helocBalances === 'string'
      ? JSON.parse(sampled[0].helocBalances)
      : (sampled[0].helocBalances || {})
    const helocKeys = Object.keys(firstHeloc).filter(k => {
      return sampled.some(s => {
        const hb = typeof s.helocBalances === 'string' ? JSON.parse(s.helocBalances) : (s.helocBalances || {})
        return (hb[k] || 0) > 0
      })
    })

    helocKeys.forEach((key, idx) => {
      datasets.push({
        label: key.replace(':', ' / '),
        data: sampled.map(s => {
          const hb = typeof s.helocBalances === 'string' ? JSON.parse(s.helocBalances) : (s.helocBalances || {})
          return -(hb[key] || 0)
        }),
        borderColor: debtColors[(creditKeys.length + idx) % debtColors.length],
        borderDash: [2, 2],
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 1,
        fill: false,
      })
    })
  }

  return {
    labels: sampled.map(s => s.date),
    datasets,
  }
})

const chartOptions = computed(() => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: showPerAccount.value, position: 'top' as const } },
  scales: {
    x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } },
    y: { ticks: { callback: (v: any) => '$' + Number(v).toLocaleString(), font: { size: 10 } } },
  },
}))

// ── Calendar State ────────────────────────────────────────────────
const calendarMonth = ref(new Date().getMonth())
const calendarYear = ref(new Date().getFullYear())
const selectedDate = ref<string | null>(null)

function prevMonth() {
  if (calendarMonth.value === 0) {
    calendarMonth.value = 11
    calendarYear.value--
  } else {
    calendarMonth.value--
  }
}

function nextMonth() {
  if (calendarMonth.value === 11) {
    calendarMonth.value = 0
    calendarYear.value++
  } else {
    calendarMonth.value++
  }
}

const calendarMonthLabel = computed(() => {
  const d = new Date(calendarYear.value, calendarMonth.value)
  return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
})

// Build a Map of date -> CalendarDay from projection data
const calendarDaysMap = computed(() => {
  const map = new Map<string, CalendarDay>()
  if (!proj.value?.calendarDays) return map
  for (const day of proj.value.calendarDays) {
    map.set(day.date, day)
  }
  return map
})

// Also build a snapshot map for days without events (to show balances)
const snapshotMap = computed(() => {
  const map = new Map<string, { balances: Record<string, number>, creditBalances: Record<string, number>, mortgageBalances: Record<string, number>, helocBalances: Record<string, number>, total: number, netTotal: number }>()
  if (!proj.value?.snapshots) return map
  for (const snap of proj.value.snapshots) {
    map.set(snap.date, {
      balances: typeof snap.balances === 'string' ? JSON.parse(snap.balances) : snap.balances,
      creditBalances: typeof snap.creditBalances === 'string' ? JSON.parse(snap.creditBalances) : (snap.creditBalances || {}),
      mortgageBalances: typeof snap.mortgageBalances === 'string' ? JSON.parse(snap.mortgageBalances) : (snap.mortgageBalances || {}),
      helocBalances: typeof snap.helocBalances === 'string' ? JSON.parse(snap.helocBalances) : (snap.helocBalances || {}),
      total: snap.total,
      netTotal: snap.netTotal ?? snap.total,
    })
  }
  return map
})

// Build calendar grid cells
interface CalendarCell {
  date: string | null
  dayNum: number
  isToday: boolean
  hasEvents: boolean
  hasIncome: boolean
  hasExpense: boolean
  hasDeferred: boolean
  hasTransfer: boolean
  eventCount: number
  outsideMonth: boolean
}

const calendarCells = computed(() => {
  const year = calendarYear.value
  const month = calendarMonth.value

  // First day of month and how many days
  const firstDay = new Date(year, month, 1)
  const startDow = firstDay.getDay() // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const todayStr = todayISO()
  const cells: CalendarCell[] = []

  // Leading empty cells
  for (let i = 0; i < startDow; i++) {
    cells.push({ date: null, dayNum: 0, isToday: false, hasEvents: false, hasIncome: false, hasExpense: false, hasDeferred: false, hasTransfer: false, eventCount: 0, outsideMonth: true })
  }

  // Day cells
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const dayData = calendarDaysMap.value.get(dateStr)
    const events = dayData?.events || []

    cells.push({
      date: dateStr,
      dayNum: d,
      isToday: dateStr === todayStr,
      hasEvents: events.length > 0,
      hasIncome: events.some(e => e.eventType === 'INCOME'),
      hasExpense: events.some(e => isExpenseType(e.eventType) && e.status !== 'deferred'),
      hasDeferred: events.some(e => e.status === 'deferred'),
      hasTransfer: events.some(e => isTransferType(e.eventType)),
      eventCount: events.length,
      outsideMonth: false,
    })
  }

  // Trailing empty cells to fill last row
  const remaining = (7 - (cells.length % 7)) % 7
  for (let i = 0; i < remaining; i++) {
    cells.push({ date: null, dayNum: 0, isToday: false, hasEvents: false, hasIncome: false, hasExpense: false, hasDeferred: false, hasTransfer: false, eventCount: 0, outsideMonth: true })
  }

  return cells
})

function selectDate(dateStr: string) {
  selectedDate.value = selectedDate.value === dateStr ? null : dateStr
}

const selectedDayData = computed(() => {
  if (!selectedDate.value) return null
  // If we have calendar day data from projection (with events)
  const calDay = calendarDaysMap.value.get(selectedDate.value)
  if (calDay) return calDay
  // If we have snapshot data (no events on this day, but we can show balances)
  const snap = snapshotMap.value.get(selectedDate.value)
  if (snap) return {
    date: selectedDate.value,
    events: [] as any[],
    balances: snap.balances,
    creditBalances: snap.creditBalances,
    mortgageBalances: snap.mortgageBalances,
    helocBalances: snap.helocBalances,
    total: snap.total,
    netTotal: snap.netTotal,
  }
  return null
})

const selectedDayBalances = computed(() => {
  if (!selectedDayData.value?.balances) return {}
  const b = selectedDayData.value.balances
  return typeof b === 'string' ? JSON.parse(b) : b
})

const selectedDayCreditBalances = computed(() => {
  if (!selectedDayData.value) return {}
  const b = (selectedDayData.value as any).creditBalances
  if (!b) return {}
  const parsed = typeof b === 'string' ? JSON.parse(b) : b
  return positiveEntries(parsed)
})

const selectedDayMortgageBalances = computed(() => {
  if (!selectedDayData.value) return {}
  const b = (selectedDayData.value as any).mortgageBalances
  if (!b) return {}
  const parsed = typeof b === 'string' ? JSON.parse(b) : b
  return positiveEntries(parsed)
})

const selectedDayHelocBalances = computed(() => {
  if (!selectedDayData.value) return {}
  const b = (selectedDayData.value as any).helocBalances
  if (!b) return {}
  const parsed = typeof b === 'string' ? JSON.parse(b) : b
  return positiveEntries(parsed)
})

const selectedDayNetTotal = computed(() => {
  if (!selectedDayData.value) return 0
  return (selectedDayData.value as any).netTotal ?? selectedDayData.value.total ?? 0
})

// ── Helpers ───────────────────────────────────────────────────────
function isExpenseType(type: string): boolean {
  return ['BILL_PAYMENT', 'BILL_DUE', 'BILL_DEFERRED', 'CREDIT_PAYMENT', 'CREDIT_PAYMENT_DUE',
          'CREDIT_PAYMENT_DEFERRED', 'MORTGAGE_PAYMENT', 'MORTGAGE_DEFERRED',
          'BILL_GROUP_PAYMENT', 'BILL_GROUP_DEFERRED',
          'HELOC_PAYMENT', 'HELOC_PAYMENT_DUE', 'HELOC_PAYMENT_DEFERRED',
          'EXTRA_CREDIT_PAYMENT', 'PROMO_PAYOFF'].includes(type)
}

function isTransferType(type: string): boolean {
  return ['SAVINGS_SWEEP', 'SAVINGS_RECALL', 'HELOC_PARK', 'HELOC_RECALL'].includes(type)
}

function eventIcon(type: string): string {
  const map: Record<string, string> = {
    INCOME: 'banknote',
    BILL_PAYMENT: 'bills',
    BILL_DUE: 'bills',
    BILL_DEFERRED: 'alert',
    CREDIT_PAYMENT: 'card',
    CREDIT_PAYMENT_DUE: 'card',
    CREDIT_PAYMENT_DEFERRED: 'alert',
    MORTGAGE_PAYMENT: 'home',
    MORTGAGE_DEFERRED: 'alert',
    INTEREST: 'trendingUp',
    BILL_GROUP_PAYMENT: 'loans',
    BILL_GROUP_DEFERRED: 'alert',
    BILL_GROUP_ALREADY_PAID: 'checkCircle',
    HELOC_PAYMENT: 'accounts',
    HELOC_PAYMENT_DUE: 'accounts',
    HELOC_PAYMENT_DEFERRED: 'alert',
    SAVINGS_SWEEP: 'arrowDown',
    SAVINGS_RECALL: 'arrowUp',
    HELOC_PARK: 'parking',
    HELOC_RECALL: 'arrowUp',
    EXTRA_CREDIT_PAYMENT: 'card',
    PROMO_PAYOFF: 'tag',
  }
  return map[type] || 'pin'
}

function eventClass(evt: { eventType: string; status: string }) {
  if (evt.status === 'deferred') return 'event-deferred'
  if (evt.eventType === 'INCOME') return 'event-income'
  if (evt.eventType === 'INTEREST') return 'event-interest'
  if (isTransferType(evt.eventType)) return 'event-transfer'
  return 'event-expense'
}

function formatDetailDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
}

function formatAccountName(key: string): string {
  // Keys are like "BankName:AccountName" — make them readable
  return key.replace(':', ' / ')
}

// Reset selected date when month changes
watch([calendarMonth, calendarYear], () => {
  selectedDate.value = null
})
</script>

<style scoped>
.stat-sub { font-size: 0.72rem; color: var(--text-muted); margin-top: 0.25rem; }
.plan-link { font-weight: 600; text-decoration: none; }
/* ── Event list ─────────────────────────────────────────────────── */
.ev-day + .ev-day { margin-top: 0.9rem; }
.ev-date { display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap;
  font-size: 0.82rem; padding: 0 0.25rem 0.35rem; border-bottom: 1px solid var(--border); margin-bottom: 0.25rem; }
.ev-date span { color: var(--text-light); font-size: 0.75rem; font-variant-numeric: tabular-nums; }
.ev-row { display: flex; align-items: center; gap: 0.65rem; padding: 0.4rem 0.25rem; border-radius: 6px; }
.ev-row:hover { background: var(--surface-hover); }
.ev-icon { width: 28px; height: 28px; flex: 0 0 28px; border-radius: 8px; display: grid; place-items: center; background: var(--surface-alt); color: var(--text-muted); }
.ev-row.event-income .ev-icon { background: var(--success-light); color: var(--success-text); }
.ev-row.event-transfer .ev-icon { background: var(--primary-light); color: var(--primary); }
.ev-row.event-deferred .ev-icon { background: var(--danger-light); color: var(--danger-text); }
.ev-desc { flex: 1; min-width: 0; display: flex; flex-direction: column; font-size: 0.88rem; font-weight: 500; line-height: 1.3; }
.ev-desc small { color: var(--text-muted); font-weight: 400; font-size: 0.75rem; }
.ev-amt { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
/* ── Calendar Grid ──────────────────────────────────────────────── */
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.cal-header {
  text-align: center;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  padding: 0.6rem 0.25rem;
  background: var(--surface-alt);
  border-bottom: 2px solid var(--border);
}

.cal-cell {
  min-height: 80px;
  padding: 0.35rem 0.45rem;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.12s, box-shadow 0.12s;
  position: relative;
  background: var(--surface);
}

.cal-cell:nth-child(7n) {
  border-right: none;
}

.cal-cell:hover:not(.cal-empty) {
  background: var(--primary-light);
}

.cal-cell.cal-empty {
  background: var(--surface-alt);
  cursor: default;
}

.cal-cell.cal-today {
  background: rgba(59, 130, 246, 0.06);
  box-shadow: inset 0 0 0 2px var(--primary);
}

.cal-cell.cal-selected {
  background: var(--primary-light);
  box-shadow: inset 0 0 0 2px var(--primary);
}

.cal-cell.cal-outside {
  opacity: 0.3;
}

.cal-day-num {
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--text);
  margin-bottom: 0.2rem;
}

.cal-today .cal-day-num {
  background: var(--primary);
  color: #fff;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
}

.cal-dots {
  display: flex;
  gap: 3px;
  margin-bottom: 0.15rem;
}

.cal-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-income { background: var(--success); }
.dot-expense { background: var(--danger); }
.dot-transfer { background: var(--primary); }
.dot-deferred { background: var(--warning); }

.cal-event-count {
  font-size: 0.65rem;
  color: var(--text-muted);
  font-weight: 600;
}

/* ── Detail Panel ───────────────────────────────────────────────── */
.cal-detail {
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 2px solid var(--border);
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.cal-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.cal-detail-header h3 {
  font-size: 1.1rem;
  font-weight: 700;
}

.cal-detail h4 {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.6rem;
}

/* ── Event List ─────────────────────────────────────────────────── */
.cal-event-list {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.cal-event-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 0.85rem;
  border-bottom: 1px solid var(--border);
  transition: background 0.1s;
}

.cal-event-item:last-child {
  border-bottom: none;
}

.cal-event-item:nth-child(even) {
  background: var(--surface-alt);
}

.cal-event-item:hover {
  background: var(--primary-light);
}

.cal-event-icon {
  font-size: 1.15rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.cal-event-info {
  flex: 1;
  min-width: 0;
}

.cal-event-desc {
  font-weight: 600;
  font-size: 0.88rem;
}

.cal-event-source {
  font-size: 0.76rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.cal-event-warning {
  font-size: 0.76rem;
  color: var(--warning);
  font-weight: 600;
  margin-top: 0.2rem;
}

.cal-event-amount {
  font-weight: 700;
  font-size: 0.92rem;
  white-space: nowrap;
  flex-shrink: 0;
}

/* Event type row colors */
.event-income { border-left: 3px solid var(--success); }
.event-expense { border-left: 3px solid var(--danger); }
.event-transfer { border-left: 3px solid var(--primary); background: rgba(59,130,246,0.04) !important; }
.event-deferred { border-left: 3px solid var(--warning); background: var(--warning-light) !important; }
.event-interest { border-left: 3px solid var(--primary); }

/* ── Hint ───────────────────────────────────────────────────────── */
.cal-hint {
  text-align: center;
  padding: 1.25rem;
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-top: 1rem;
  border-top: 1px solid var(--border);
}
</style>

