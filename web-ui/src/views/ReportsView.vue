<template>
  <div>
    <div class="view-header">
      <h2>Reports</h2>
      <div class="chip-group" style="margin:0">
        <button v-for="n in [3, 6, 12]" :key="n" class="chip" :class="{ selected: months === n }" @click="months = n">{{ n }} months</button>
      </div>
    </div>

    <div v-if="loading && !report" class="loading">Loading reports...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="report">
      <div v-if="!hasTransactions" class="empty-state">
        <div class="icon">📈</div>
        <p>Spending reports are built from your transactions.
          <RouterLink to="/transactions">Import or download transactions</RouterLink> to see them here.</p>
      </div>

      <template v-else>
        <div class="grid grid-3" style="margin-bottom:1.5rem">
          <div class="stat-card">
            <div class="stat-label">Average monthly income</div>
            <div class="stat-value positive">{{ currency(avg.income) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Average monthly spending</div>
            <div class="stat-value">{{ currency(avg.spending) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Average left over</div>
            <div class="stat-value" :class="avg.net >= 0 ? 'positive' : 'negative'">{{ currency(avg.net) }}</div>
            <div class="sub">{{ avg.income ? Math.round(avg.net / avg.income * 100) : 0 }}% of income</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">Income vs. spending</span></div>
          <div style="height:280px"><Bar :data="incomeChart" :options="barOptions" /></div>
          <p class="sub" style="margin-top:0.5rem">Transfers between your own accounts aren't counted. This month is partial.</p>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">Where the money went</span>
            <select v-model="selectedMonth" style="margin:0;width:auto">
              <option v-for="m in report.months" :key="m.month" :value="m.month">{{ monthLabel(m.month) }}</option>
            </select>
          </div>
          <div class="split">
            <div style="height:260px;max-width:300px;flex:1"><Doughnut :data="categoryChart" :options="doughnutOptions" /></div>
            <div class="cat-table scroll-x"><table>
              <thead><tr><th>Category</th><th style="text-align:right">{{ monthLabel(selectedMonth, true) }}</th><th style="text-align:right">Average</th><th></th></tr></thead>
              <tbody>
                <tr v-for="row in categoryRows" :key="row.name">
                  <td><span class="dot" :style="{ background: colorOf(row.name) }"></span> {{ row.name }}</td>
                  <td style="text-align:right">{{ currency(row.amount) }}</td>
                  <td style="text-align:right" class="sub">{{ currency(row.avg) }}</td>
                  <td style="text-align:right;font-size:0.78rem" :class="row.amount > row.avg * 1.15 && row.amount - row.avg > 20 ? 'negative' : row.amount < row.avg * 0.85 ? 'positive' : 'sub'">
                    {{ row.avg ? (row.amount >= row.avg ? '▲' : '▼') + Math.abs(Math.round((row.amount / row.avg - 1) * 100)) + '%' : '' }}
                  </td>
                </tr>
              </tbody>
            </table></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">Category trends</span></div>
          <div class="table-wrap no-stack">
            <table>
              <thead>
                <tr><th>Category</th><th v-for="m in report.months" :key="m.month" style="text-align:right">{{ monthLabel(m.month, true) }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="name in trendCategories" :key="name">
                  <td><span class="dot" :style="{ background: colorOf(name) }"></span> {{ name }}</td>
                  <td v-for="m in report.months" :key="m.month" style="text-align:right">{{ amountFor(m, name) ? currency(amountFor(m, name)) : '—' }}</td>
                </tr>
                <tr class="total">
                  <td>Total spending</td>
                  <td v-for="m in report.months" :key="m.month" style="text-align:right">{{ currency(m.spending) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <div class="card">
        <div class="card-header"><span class="card-title">Net worth</span></div>
        <div v-if="netWorth.length < 2" class="sub">Net worth is recorded once a day when the app starts — check back after a few days.</div>
        <template v-else>
          <div class="sub" style="margin-bottom:0.5rem">
            {{ currency(netWorth[netWorth.length - 1].netWorth) }} now ·
            <span :class="nwChange >= 0 ? 'positive' : 'negative'">{{ nwChange >= 0 ? '+' : '−' }}{{ currency(Math.abs(nwChange)) }}</span>
            since {{ fmtDate(netWorth[0].snapshotDate) }}
          </div>
          <div style="height:260px"><Line :data="netWorthChart" :options="lineOptions" /></div>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { Bar, Doughnut, Line } from 'vue-chartjs'
import { themeState } from '../utils/theme'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, ArcElement, PointElement, LineElement,
  Tooltip, Legend, Filler, type ChartOptions, type TooltipItem,
} from 'chart.js'
import { GET_SPENDING_REPORT } from '../graphql/ledger'
import { GET_NET_WORTH_HISTORY } from '../graphql/queries'
import { currency, fmtDate } from '../utils/format'
import type { NetWorthSnapshot, SpendingMonth, SpendingReport } from '../types'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, PointElement, LineElement, Tooltip, Legend, Filler)

const months = ref(6)
const { result, loading, error } = useQuery<{ spendingReport: SpendingReport }>(GET_SPENDING_REPORT,
  () => ({ variables: { months: months.value }, fetchPolicy: 'cache-and-network' }))
const { result: nwResult } = useQuery<{ netWorthHistory: NetWorthSnapshot[] }>(GET_NET_WORTH_HISTORY,
  { variables: { limit: 365 } })

function parse<T>(v: string | T | null | undefined): T {
  return (typeof v === 'string' ? JSON.parse(v) : v ?? {}) as T
}

const report = computed(() => result.value?.spendingReport)
const colors = computed(() => parse<Record<string, string>>(report.value?.colors))
const byCat = (m: SpendingMonth) => parse<Record<string, number>>(m.byCategory)
const hasTransactions = computed(() => (report.value?.months ?? []).some(m => m.income || m.spending))
const colorOf = (name: string) => colors.value[name] || '#94a3b8'
const amountFor = (m: SpendingMonth, name: string) => byCat(m)[name] || 0

const selectedMonth = ref('')
watch(report, r => {
  if (r && !r.months.some(m => m.month === selectedMonth.value)) {
    // Default to the last full month when there is one
    selectedMonth.value = r.months[Math.max(0, r.months.length - 2)]?.month ?? ''
  }
}, { immediate: true })

function monthLabel(key: string, short = false): string {
  if (!key) return ''
  const [y, m] = key.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', short ? { month: 'short' } : { month: 'long', year: 'numeric' })
}

// Averages use full months only (the current month is partial), starting from
// the first month with any transactions
const fullMonths = computed(() => {
  const ms = report.value?.months ?? []
  const first = ms.findIndex(m => m.income || m.spending)
  return first < 0 ? [] : ms.slice(first, -1)
})
const avg = computed(() => {
  const ms = fullMonths.value.length ? fullMonths.value : report.value?.months ?? []
  const n = Math.max(1, ms.length)
  const income = ms.reduce((s, m) => s + m.income, 0) / n
  const spending = ms.reduce((s, m) => s + m.spending, 0) / n
  return { income, spending, net: income - spending }
})

const incomeChart = computed(() => {
  const ms = report.value?.months ?? []
  return {
    labels: ms.map(m => monthLabel(m.month, true)),
    datasets: [
      { label: 'Income', data: ms.map(m => m.income), backgroundColor: '#22c55e' },
      { label: 'Spending', data: ms.map(m => m.spending), backgroundColor: '#f97316' },
    ],
  }
})

const categoryRows = computed(() => {
  const m = report.value?.months.find(x => x.month === selectedMonth.value)
  if (!m) return []
  const full = fullMonths.value.length ? fullMonths.value : report.value?.months ?? []
  return Object.entries(byCat(m)).filter(([, v]) => v > 0).map(([name, amount]) => ({
    name, amount,
    avg: full.reduce((s, x) => s + (byCat(x)[name] || 0), 0) / Math.max(1, full.length),
  }))
})

const categoryChart = computed(() => ({
  labels: categoryRows.value.map(r => r.name),
  datasets: [{
    data: categoryRows.value.map(r => r.amount), backgroundColor: categoryRows.value.map(r => colorOf(r.name)),
    borderColor: themeState.dark ? '#151e2e' : '#ffffff',  // slice gaps match the card
  }],
}))

const trendCategories = computed(() => {
  const totals: Record<string, number> = {}
  for (const m of report.value?.months ?? []) for (const [k, v] of Object.entries(byCat(m))) totals[k] = (totals[k] || 0) + v
  return Object.entries(totals).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).map(([k]) => k)
})

const netWorth = computed(() => [...(nwResult.value?.netWorthHistory ?? [])].sort((a, b) => a.snapshotDate.localeCompare(b.snapshotDate)))
const nwChange = computed(() => netWorth.value.length > 1 ? netWorth.value[netWorth.value.length - 1].netWorth - netWorth.value[0].netWorth : 0)
const netWorthChart = computed(() => ({
  labels: netWorth.value.map(s => fmtDate(s.snapshotDate)),
  datasets: [{ label: 'Net worth', data: netWorth.value.map(s => s.netWorth), borderColor: '#3b82f6',
    backgroundColor: 'rgba(59,130,246,0.12)', fill: true, tension: 0.25, pointRadius: 0 }],
}))

const money = (v: number | string) => currency(Number(v))
const barOptions: ChartOptions<'bar'> = {
  responsive: true, maintainAspectRatio: false,
  scales: { y: { ticks: { callback: money } } },
  plugins: { tooltip: { callbacks: { label: (c: TooltipItem<'bar'>) => `${c.dataset.label}: ${currency(c.parsed.y)}` } } },
}
const doughnutOptions: ChartOptions<'doughnut'> = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
const lineOptions: ChartOptions<'line'> = {
  responsive: true, maintainAspectRatio: false,
  scales: { y: { ticks: { callback: money } } },
  plugins: { legend: { display: false } },
}
</script>

<style scoped>
.sub { font-size: 0.8rem; color: var(--text-muted); }
.split { display: flex; gap: 1.5rem; align-items: flex-start; flex-wrap: wrap; }
.cat-table { flex: 2 1 280px; min-width: 0; }
@media (max-width: 767px) { .split > div:first-child { flex: 1 1 100% !important; max-width: 240px !important; margin: 0 auto; height: 220px !important; } }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.3rem; }
.total td { font-weight: 600; border-top: 2px solid var(--border-strong); }
.card + .card { margin-top: 1.5rem; }
</style>
