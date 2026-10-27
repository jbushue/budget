<template>
  <div>
    <div class="view-header">
      <h2>Timeline & Projection</h2>
      <div style="display:flex;gap:0.5rem;align-items:center">
        <select v-model.number="days" style="width:auto">
          <option :value="30">30 days</option>
          <option :value="60">60 days</option>
          <option :value="90">90 days</option>
          <option :value="180">6 months</option>
          <option :value="365">1 year</option>
        </select>
        <button class="btn btn-outline btn-sm" @click="refetch()">Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Calculating projection...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="proj">
      <!-- Summary cards -->
      <div class="grid grid-4" style="margin-bottom:1.5rem">
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(proj.totalIncome) }}</div>
          <div class="stat-label">Total Income</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value negative">{{ currency(proj.totalExpenses) }}</div>
          <div class="stat-label">Total Expenses</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value" :class="proj.netChange >= 0 ? 'positive' : 'negative'">{{ currency(proj.netChange) }}</div>
          <div class="stat-label">Net Change</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value" :class="proj.netFinalBalance >= 0 ? 'positive' : 'negative'">{{ currency(proj.netFinalBalance) }}</div>
          <div class="stat-label">Projected Net Worth</div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.25rem">
            Assets {{ currency(proj.totalFinalBalance) }}
            <span v-if="totalDebt > 0"> · Debt {{ currency(totalDebt) }}</span>
          </div>
        </div>
      </div>

      <!-- Balance chart -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header">
          <span class="card-title">Balance Over Time</span>
          <label style="font-size:0.8rem;display:flex;align-items:center;gap:0.35rem;cursor:pointer;color:var(--text-muted)">
            <input type="checkbox" v-model="showPerAccount" /> Per-account lines
          </label>
        </div>
        <div style="height:350px">
          <Line :data="chartData" :options="chartOptions" />
        </div>
      </div>

      <!-- Final balances breakdown -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header"><span class="card-title">Projected Final Balances</span></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th style="text-align:right">Projected Balance</th>
              </tr>
            </thead>
            <tbody>
              <!-- Bank accounts (assets) -->
              <tr v-if="Object.keys(parsedBalances).length" class="section-header-row">
                <td colspan="2" style="font-weight:700;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;padding-top:0.75rem">
                  🏦 Bank Accounts
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
                    💳 Credit Cards
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
                    🏠 Mortgages
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
                    🏦 HELOCs
                  </td>
                </tr>
                <tr v-for="(bal, key) in parsedHelocBalances" :key="'heloc-' + key">
                  <td>{{ formatAccountName(key as string) }}</td>
                  <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                </tr>
              </template>
              <!-- Net total -->
              <tr style="border-top:2px solid var(--border-strong);font-weight:700">
                <td>Net Worth</td>
                <td style="text-align:right" :class="proj.netFinalBalance >= 0 ? 'positive' : 'negative'">
                  {{ currency(proj.netFinalBalance) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Financial Calendar -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">📅 Financial Calendar</span>
          <div style="display:flex;align-items:center;gap:0.5rem">
            <button class="btn btn-outline btn-sm" @click="prevMonth">&larr;</button>
            <span style="font-weight:700;min-width:140px;text-align:center">{{ calendarMonthLabel }}</span>
            <button class="btn btn-outline btn-sm" @click="nextMonth">&rarr;</button>
          </div>
        </div>

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
            <button class="btn btn-outline btn-sm" @click="selectedDate = null">&times; Close</button>
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
                <div class="cal-event-icon">{{ eventIcon(evt.eventType) }}</div>
                <div class="cal-event-info">
                  <div class="cal-event-desc">{{ evt.description }}</div>
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
                    ⚠️ Insufficient funds — payment deferred
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
            <h4>Expected Account Balances (End of Day)</h4>
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
                      <td>💳 {{ formatAccountName(acct as string) }}</td>
                      <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                    </tr>
                  </template>
                  <template v-if="Object.keys(selectedDayMortgageBalances).length">
                    <tr v-for="(bal, acct) in selectedDayMortgageBalances" :key="'m-' + acct">
                      <td>🏠 {{ formatAccountName(acct as string) }}</td>
                      <td style="text-align:right;font-weight:600" class="negative">-{{ currency(bal) }}</td>
                    </tr>
                  </template>
                  <template v-if="Object.keys(selectedDayHelocBalances).length">
                    <tr v-for="(bal, acct) in selectedDayHelocBalances" :key="'h-' + acct">
                      <td>🏦 {{ formatAccountName(acct as string) }}</td>
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
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
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
import { currency, todayISO } from '../utils/format'
import type { Projection, CalendarDay } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler, Legend)

const days = ref(90)
const showPerAccount = ref(true)
const { result, loading, error, refetch } = useQuery<{ projection: Projection }>(GET_PROJECTION, () => ({ variables: { days: days.value } }))

const proj = computed(() => result.value?.projection)

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
      label: 'Net Balance',
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
        label: `💳 ${key.replace(':', ' / ')}`,
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
        label: `🏦 ${key.replace(':', ' / ')}`,
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
    INCOME: '💰',
    BILL_PAYMENT: '📋',
    BILL_DUE: '📋',
    BILL_DEFERRED: '⚠️',
    CREDIT_PAYMENT: '💳',
    CREDIT_PAYMENT_DUE: '💳',
    CREDIT_PAYMENT_DEFERRED: '⚠️',
    MORTGAGE_PAYMENT: '🏠',
    MORTGAGE_DEFERRED: '⚠️',
    INTEREST: '📈',
    BILL_GROUP_PAYMENT: '📦',
    BILL_GROUP_DEFERRED: '⚠️',
    BILL_GROUP_ALREADY_PAID: '✅',
    HELOC_PAYMENT: '🏦',
    HELOC_PAYMENT_DUE: '🏦',
    HELOC_PAYMENT_DEFERRED: '⚠️',
    SAVINGS_SWEEP: '💸',
    SAVINGS_RECALL: '📥',
    HELOC_PARK: '🅿️',
    HELOC_RECALL: '⬆️',
    EXTRA_CREDIT_PAYMENT: '💳',
    PROMO_PAYOFF: '🏷️',
  }
  return map[type] || '📌'
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

