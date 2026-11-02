<template>
  <div>
    <div class="tool-controls">
      <label class="amt">
        I want to spend
        <input v-model.number="amount" type="number" min="0" step="10" placeholder="0.00" aria-label="Purchase amount" />
      </label>
      <select v-model.number="days" style="width:auto" aria-label="How far ahead">
        <option :value="30">next 30 days</option>
        <option :value="60">next 60 days</option>
        <option :value="90">next 90 days</option>
      </select>
    </div>

    <div v-if="loading && !r" class="loading">Checking every day ahead...</div>
    <div v-else-if="error" class="callout danger">{{ error.message }}</div>
    <template v-else-if="r">
      <div class="answers">
        <div class="answer">
          <span class="a-label">Safe to spend today</span>
          <strong :class="r.today > 0 ? 'positive' : 'negative'">{{ currency(r.today) }}</strong>
          <small>same as the dashboard: above your {{ currency(r.cushion) }} cushion and every bill covered</small>
        </div>
        <div v-if="r.amount > 0" class="answer" :class="r.earliest ? 'good' : 'bad'">
          <span class="a-label">{{ currency(r.amount) }} fits</span>
          <strong>{{ r.earliest ? (r.earliest === r.can_spend[0]?.date ? 'Today' : fmtDateShort(r.earliest)) : 'Not yet' }}</strong>
          <small v-if="r.earliest">lowest checking afterwards {{ currency(r.lowest_after ?? 0) }}</small>
          <small v-else>not in the next {{ r.days }} days without dipping below your cushion or paying a bill late</small>
        </div>
        <div v-if="r.best" class="answer">
          <span class="a-label">Most room</span>
          <strong>{{ currency(r.best.amount) }}</strong>
          <small>on {{ fmtDateShort(r.best.date) }}</small>
        </div>
      </div>
      <div class="chart-box"><Line :data="chartData" :options="chartOptions" /></div>
      <p class="muted" style="font-size:0.78rem;margin:0.5rem 0 0">
        Each day shows the most you could spend that day (once) and still stay above your cushion through
        {{ fmtDateShort(r.can_spend[r.can_spend.length - 1]?.date) }}, after bills and everyday spending.
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler, type ChartData, type ChartOptions, type ChartDataset } from 'chart.js'
import { GET_PURCHASE_PLANNER } from '../graphql/tools'
import { refDebounced } from '../utils/debounce'
import { currency, fmtDateShort } from '../utils/format'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler)

interface Planner { days: number; amount: number; cushion: number; today: number; earliest: string | null
  lowest_after: number | null; best: { date: string; amount: number } | null; can_spend: { date: string; amount: number }[] }

const amount = ref<number | null>(null)
const days = ref(60)
const amountDebounced = refDebounced(amount, 500)

const { result, loading, error } = useQuery<{ purchasePlanner: string }>(GET_PURCHASE_PLANNER, () => ({
  variables: { amount: Number(amountDebounced.value) || 0, days: days.value }, fetchPolicy: 'cache-and-network',
}))
const r = computed<Planner | null>(() => {
  const raw = result.value?.purchasePlanner
  return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : null
})

const chartData = computed<ChartData<'line'>>(() => {
  const pts = r.value?.can_spend ?? []
  const ds: ChartDataset<'line'>[] = [{
    label: 'Could spend', data: pts.map(p => p.amount), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.12)',
    fill: true, tension: 0.25, pointRadius: 0, stepped: false,
  }]
  if ((r.value?.amount ?? 0) > 0) {
    ds.push({ label: 'Your purchase', data: pts.map(() => r.value!.amount), borderColor: '#6366f1', borderDash: [6, 4],
      pointRadius: 0, fill: false })
  }
  return { labels: pts.map(p => fmtDateShort(p.date)), datasets: ds }
})
const chartOptions: ChartOptions<'line'> = {
  responsive: true, maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${currency(c.parsed.y ?? 0)}` } } },
  scales: { x: { ticks: { maxTicksLimit: 8, font: { size: 10 } } }, y: { beginAtZero: true, ticks: { font: { size: 10 }, callback: (v: string | number) => currency(Number(v)) } } },
}
</script>

<style scoped>
.tool-controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin-bottom: 1rem; }
.amt { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; font-weight: 550; text-transform: none; letter-spacing: normal; color: var(--text); margin: 0; }
.amt input { width: 9rem; }
.answers { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.7rem; margin-bottom: 1rem; }
.answer { border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.85rem; display: flex; flex-direction: column; gap: 0.15rem; }
.answer.good { background: var(--success-light); border-color: transparent; }
.answer.bad { background: var(--danger-light); border-color: transparent; }
.a-label { font-size: 0.75rem; font-weight: 600; color: var(--text-muted); }
.answer strong { font-size: 1.25rem; font-variant-numeric: tabular-nums; }
.answer small { font-size: 0.75rem; color: var(--text-muted); }
.chart-box { height: 220px; }
@media (max-width: 700px) { .answers { grid-template-columns: 1fr; } }
</style>
