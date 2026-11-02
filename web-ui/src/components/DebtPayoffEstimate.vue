<template>
  <div>
    <div class="payoff-head">
      <p class="muted payoff-note">
        Until every card and loan is paid off (mortgages aren't included). A month-by-month estimate at your
        current minimums plus the extra below. The plan above is worked out day by day for the next year.
      </p>
      <label class="payoff-slider">
        <span>Extra each month</span>
        <input v-model.number="extraMonthly" type="range" min="0" max="2000" step="25" />
        <strong>{{ currency(extraMonthly) }}</strong>
      </label>
    </div>

    <div v-if="error" class="callout danger">Could not calculate payoff strategies: {{ error.message }}</div>
    <div v-else-if="loading && !comparison" class="loading">Calculating payoff strategies...</div>
    <div v-else-if="debtFree" class="empty-state">
      <div class="icon"><Icon name="party" :size="26" /></div>
      <p>No debts to pay off! You're debt free.</p>
    </div>

    <template v-else-if="comparison">
      <div class="grid grid-3" style="margin-bottom:1rem">
        <div class="stat-card payoff-card" v-for="s in strategies" :key="s.key"
             :style="s.key === 'minimum' ? '' : 'border-top:3px solid ' + s.color">
          <div style="font-weight:700;margin-bottom:0.5rem">{{ s.label }}</div>
          <template v-if="s.data.paysOff === false">
            <div class="stat-value negative">Never</div>
            <div style="margin-top:0.5rem;font-size:0.8rem;color:var(--danger);font-weight:600">
              Never pays off at these payments &mdash; {{ currency(s.data.remainingBalance ?? 0) }} left after {{ s.data.monthsToPayoff }} months
            </div>
          </template>
          <template v-else>
            <div class="stat-value" :style="`color:${s.color}`">{{ yearsMonths(s.data.monthsToPayoff) }}</div>
            <div class="stat-label">to debt-free</div>
          </template>
          <div style="margin-top:0.75rem;font-size:0.85rem">
            <div>Interest: <strong class="negative">{{ currency(s.data.totalInterestPaid) }}</strong></div>
            <div>Total paid: <strong>{{ currency(s.data.totalPaid) }}</strong></div>
          </div>
          <div v-if="s.key !== 'minimum' && s.data.totalInterestPaid < comparison.minimum.totalInterestPaid"
               style="margin-top:0.5rem;font-size:0.8rem;color:var(--success);font-weight:600">
            Saves {{ currency(comparison.minimum.totalInterestPaid - s.data.totalInterestPaid) }} in interest
          </div>
          <details v-if="s.data.payoffOrder && s.data.payoffOrder.length" class="payoff-order">
            <summary>Payoff order</summary>
            <ol>
              <li v-for="(name, i) in s.data.payoffOrder" :key="i">
                <span v-if="name.startsWith('Group:')" style="color:var(--primary)">{{ name.replace('Group:', '') }}</span>
                <span v-else>{{ name.replace(':', ' / ') }}</span>
              </li>
            </ol>
          </details>
        </div>
      </div>
      <div style="height:300px">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import Icon from './Icon.vue'
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
  Legend,
} from 'chart.js'
import { GET_DEBT_PAYOFF_COMPARISON } from '../graphql/queries'
import { currency } from '../utils/format'
import type { DebtPayoffComparison } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const extraMonthly = ref(200)
const debouncedExtra = ref(200)
const { result, loading, error } = useQuery<{ debtPayoffComparison: DebtPayoffComparison | null }>(GET_DEBT_PAYOFF_COMPARISON, () => ({
  variables: { extraMonthly: debouncedExtra.value },
  fetchPolicy: 'cache-and-network' as const,
}))

// Debounce slider → only update query variable after user stops moving
let debounceTimer: ReturnType<typeof setTimeout>
watch(extraMonthly, (val) => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debouncedExtra.value = val
  }, 500)
})

const comparison = computed(() => result.value?.debtPayoffComparison ?? null)
// The backend returns null only when there are no debts (errors come through `error`)
const debtFree = computed(() => !!result.value && result.value.debtPayoffComparison === null)

const strategies = computed(() => {
  if (!comparison.value) return []
  return [
    { key: 'minimum', label: 'Minimum only', color: 'var(--text-muted)', data: comparison.value.minimum },
    { key: 'avalanche', label: 'Highest interest first', color: 'var(--primary)', data: comparison.value.avalanche },
    { key: 'snowball', label: 'Smallest balance first', color: 'var(--success)', data: comparison.value.snowball },
  ]
})

function yearsMonths(months: number): string {
  if (months < 12) return `${months} months`
  const y = Math.floor(months / 12)
  const m = months % 12
  return m ? `${y}y ${m}m` : `${y} years`
}

interface BreakdownPoint { month: number; total_remaining: number }

/** monthlyBreakdown may be an array, a JSON string, or a double-encoded JSON string. */
function parseBreakdown(bd: unknown): BreakdownPoint[] {
  let v: unknown = bd
  for (let i = 0; i < 2 && typeof v === 'string'; i++) {
    try { v = JSON.parse(v) } catch { return [] }
  }
  return Array.isArray(v) ? (v as BreakdownPoint[]) : []
}

// Points are monthly for the first year, then sparser — plot on a linear month axis
// so spacing reflects actual time.
const toPoints = (bd: BreakdownPoint[]) =>
  bd.filter(d => d && typeof d.month === 'number').map(d => ({ x: d.month, y: d.total_remaining }))

const chartData = computed(() => {
  if (!comparison.value) return { datasets: [] }

  const minBd = parseBreakdown(comparison.value.minimum.monthlyBreakdown)
  const avBd = parseBreakdown(comparison.value.avalanche.monthlyBreakdown)
  const snBd = parseBreakdown(comparison.value.snowball.monthlyBreakdown)

  return {
    datasets: [
      {
        label: 'Minimum Only',
        data: toPoints(minBd),
        borderColor: '#94a3b8',
        borderDash: [6, 3],
        tension: 0.3,
        pointRadius: 0,
      },
      {
        label: 'Avalanche',
        data: toPoints(avBd),
        borderColor: '#3b82f6',
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: 'Snowball',
        data: toPoints(snBd),
        borderColor: '#10b981',
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true, position: 'top' as const },
    tooltip: {
      callbacks: {
        title: (items: any[]) => (items.length ? `Month ${items[0].parsed.x}` : ''),
        label: (item: any) => `${item.dataset.label}: ${currency(item.parsed.y)}`,
      },
    },
  },
  scales: {
    x: {
      type: 'linear' as const,
      min: 0,
      title: { display: true, text: 'Month', font: { size: 10 } },
      ticks: { maxTicksLimit: 15, precision: 0, font: { size: 10 } },
    },
    y: {
      ticks: { callback: (v: any) => '$' + Number(v).toLocaleString(), font: { size: 10 } },
      beginAtZero: true,
    },
  },
}
</script>


<style scoped>
.payoff-head { display: flex; flex-wrap: wrap; gap: 0.75rem 1.5rem; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
.payoff-note { font-size: 0.8rem; margin: 0; flex: 1 1 320px; }
.payoff-slider { display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; flex: 0 1 360px; }
.payoff-slider input { flex: 1; }
.payoff-slider strong { min-width: 64px; text-align: right; }
.payoff-card { border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; text-align: left; }
.payoff-order { margin-top: 0.6rem; font-size: 0.75rem; color: var(--text-muted); }
.payoff-order summary { cursor: pointer; font-weight: 600; }
.payoff-order ol { margin: 0.25rem 0 0; padding-left: 1.25rem; }
</style>
