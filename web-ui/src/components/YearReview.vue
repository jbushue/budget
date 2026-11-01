<template>
  <div class="card">
    <div class="card-header">
      <span class="card-title">Year in review</span>
      <div class="year-nav">
        <button class="btn btn-outline btn-sm" aria-label="Previous year" @click="year--"><Icon name="chevronLeft" :size="15" /></button>
        <strong>{{ year }}</strong>
        <button class="btn btn-outline btn-sm" aria-label="Next year" :disabled="year >= thisYear" @click="year++"><Icon name="chevronRight" :size="15" /></button>
      </div>
    </div>

    <div v-if="loading && !review" class="loading">Loading...</div>
    <p v-else-if="review && !review.hasData" class="muted" style="font-size:0.9rem">No transactions in {{ year }}.</p>

    <template v-else-if="review">
      <div class="yr-stats">
        <div><div class="lbl">Income</div><div class="val positive">{{ currency(review.income) }}</div></div>
        <div><div class="lbl">Spending</div><div class="val">{{ currency(review.spending) }}</div></div>
        <div>
          <div class="lbl">Saved</div>
          <div class="val" :class="review.saved >= 0 ? 'positive' : 'negative'">{{ currency(review.saved) }}</div>
          <div v-if="review.savingsRate != null" class="muted small">{{ review.savingsRate }}% of income</div>
        </div>
        <div>
          <div class="lbl">Avg. month</div><div class="val">{{ currency(review.averageMonthlySpending) }}</div>
          <div v-if="review.biggestMonth" class="muted small">most in {{ monthName(review.biggestMonth) }}</div>
        </div>
      </div>

      <div style="height:220px;margin:1rem 0"><Bar :data="chart" :options="options" /></div>

      <div class="yr-grid">
        <div>
          <h4>Top categories</h4>
          <div v-for="c in review.topCategories" :key="c.name" class="yr-row">
            <span><span class="dot" :style="{ background: c.color }"></span>{{ c.name }}</span>
            <span>{{ currency(c.amount) }} <span class="muted small">{{ c.share }}%</span></span>
          </div>
        </div>
        <div>
          <h4>Where you spent most</h4>
          <div v-for="p in review.topPayees.slice(0, 8)" :key="p.name" class="yr-row">
            <span>{{ p.name }}</span><span>{{ currency(p.amount) }}</span>
          </div>
        </div>
        <div>
          <h4>Biggest purchases</h4>
          <div v-for="p in review.largestPurchases" :key="p.date + p.description" class="yr-row">
            <span>{{ p.description }} <span class="muted small">{{ fmtDateShort(p.date) }}</span></span><span>{{ currency(p.amount) }}</span>
          </div>
          <template v-if="review.byTag.length">
            <h4 style="margin-top:1rem">By tag</h4>
            <div v-for="t in review.byTag.slice(0, 6)" :key="t.tag" class="yr-row">
              <span>#{{ t.tag }}</span><span>{{ currency(t.amount) }}</span>
            </div>
          </template>
        </div>
      </div>
      <p class="muted small" style="margin:0.75rem 0 0">{{ review.transactionCount }} transactions. Transfers between your own accounts aren't counted as spending.</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import Icon from './Icon.vue'
import { useQuery } from '@vue/apollo-composable'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend, type ChartOptions, type TooltipItem } from 'chart.js'
import { GET_YEAR_REVIEW } from '../graphql/planning'
import { currency, fmtDateShort } from '../utils/format'
import type { YearReview } from '../types'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const thisYear = new Date().getFullYear()
const year = ref(thisYear)
const { result, loading } = useQuery<{ yearReview: YearReview }>(GET_YEAR_REVIEW, () => ({
  variables: { year: year.value }, fetchPolicy: 'cache-and-network' }))
const review = computed(() => result.value?.yearReview)

function monthName(key: string, short = false) {
  const [y, m] = key.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: short ? 'short' : 'long' })
}

const chart = computed(() => {
  const ms = review.value?.months ?? []
  return {
    labels: ms.map(m => monthName(m.month, true)),
    datasets: [
      { label: 'Income', data: ms.map(m => m.income), backgroundColor: '#22c55e' },
      { label: 'Spending', data: ms.map(m => m.spending), backgroundColor: '#f97316' },
    ],
  }
})
const options: ChartOptions<'bar'> = {
  responsive: true, maintainAspectRatio: false,
  scales: { y: { ticks: { callback: (v: number | string) => currency(Number(v)) } } },
  plugins: { tooltip: { callbacks: { label: (c: TooltipItem<'bar'>) => `${c.dataset.label}: ${currency(c.parsed.y)}` } } },
}
</script>

<style scoped>
.muted { color: var(--text-muted); }
.small { font-size: 0.75rem; }
.year-nav { display: flex; gap: 0.5rem; align-items: center; }
.yr-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; }
.lbl { font-size: 0.78rem; color: var(--text-muted); }
.val { font-size: 1.35rem; font-weight: 700; }
.yr-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem; }
.yr-grid h4 { margin: 0 0 0.4rem; font-size: 0.9rem; }
.yr-row { display: flex; justify-content: space-between; gap: 0.75rem; font-size: 0.85rem; padding: 0.3rem 0; border-bottom: 1px solid var(--border); }
.yr-row > span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.yr-row > span:last-child { white-space: nowrap; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 0.35rem; }
</style>
