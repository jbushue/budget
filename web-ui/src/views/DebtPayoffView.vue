<template>
  <div>
    <div class="view-header">
      <h2>📉 Debt Payoff Estimator</h2>
    </div>

    <div class="card" style="margin-bottom:1.5rem">
      <div class="form-group" style="max-width:300px">
        <label>Extra Monthly Payment</label>
        <div style="display:flex;gap:0.5rem;align-items:center">
          <input v-model.number="extraMonthly" type="range" min="0" max="2000" step="25" style="flex:1" />
          <span style="font-weight:600;min-width:70px;text-align:right">{{ currency(extraMonthly) }}</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="card" style="color:var(--danger)">
      Could not calculate payoff strategies: {{ error.message }}
    </div>
    <div v-else-if="loading && !comparison" class="loading">Calculating payoff strategies...</div>
    <div v-else-if="debtFree" class="empty-state">
      <div class="icon">🎉</div>
      <p>No debts to pay off! You're debt free.</p>
    </div>

    <template v-else-if="comparison">
      <!-- Strategy comparison cards -->
      <div class="grid grid-3" style="margin-bottom:1.5rem">
        <div class="card stat-card" v-for="s in strategies" :key="s.key"
             :style="s.key === 'minimum' ? '' : 'border-top:3px solid ' + s.color">
          <div style="font-weight:700;margin-bottom:0.5rem">{{ s.label }}</div>
          <template v-if="s.data.paysOff === false">
            <div class="stat-value negative">Never</div>
            <div style="margin-top:0.5rem;font-size:0.8rem;color:var(--danger);font-weight:600">
              ⚠️ Never pays off at current payments &mdash; {{ currency(s.data.remainingBalance ?? 0) }} remaining after {{ s.data.monthsToPayoff }} months
            </div>
          </template>
          <template v-else>
            <div class="stat-value" :style="`color:${s.color}`">{{ s.data.monthsToPayoff }} mo</div>
            <div class="stat-label">{{ yearsMonths(s.data.monthsToPayoff) }}</div>
          </template>
          <div style="margin-top:0.75rem;font-size:0.85rem">
            <div>Total Interest: <strong class="negative">{{ currency(s.data.totalInterestPaid) }}</strong></div>
            <div>Total Paid: <strong>{{ currency(s.data.totalPaid) }}</strong></div>
          </div>
          <div v-if="s.key !== 'minimum' && s.data.totalInterestPaid < comparison.minimum.totalInterestPaid"
               style="margin-top:0.5rem;font-size:0.8rem;color:var(--success);font-weight:600">
            Saves {{ currency(comparison.minimum.totalInterestPaid - s.data.totalInterestPaid) }} in interest!
          </div>
          <div v-if="s.data.payoffOrder && s.data.payoffOrder.length" style="margin-top:0.75rem;font-size:0.75rem;color:var(--text-muted)">
            <div style="font-weight:600;margin-bottom:0.25rem">Payoff Order:</div>
            <ol style="margin:0;padding-left:1.25rem">
              <li v-for="(name, i) in s.data.payoffOrder" :key="i">
                <span v-if="name.startsWith('Group:')" style="color:var(--primary)">📦 {{ name.replace('Group:', '') }}</span>
                <span v-else>{{ name.replace(':', ' / ') }}</span>
              </li>
            </ol>
          </div>
        </div>
      </div>

      <!-- Payoff chart -->
      <div class="card">
        <div class="card-header"><span class="card-title">Remaining Debt Over Time</span></div>
        <div style="height:350px">
          <Line :data="chartData" :options="chartOptions" />
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
    { key: 'minimum', label: '💤 Minimum Only', color: 'var(--text-muted)', data: comparison.value.minimum },
    { key: 'avalanche', label: '🏔️ Avalanche', color: 'var(--primary)', data: comparison.value.avalanche },
    { key: 'snowball', label: '⛄ Snowball', color: 'var(--success)', data: comparison.value.snowball },
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

