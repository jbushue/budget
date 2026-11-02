<template>
  <div>
    <div class="tool-controls">
      <div class="segmented" role="radiogroup" aria-label="Which debt first">
        <button v-for="s in STRATS" :key="s.key" role="radio" :aria-checked="strategy === s.key"
                :class="{ active: strategy === s.key }" :title="s.hint" @click="strategy = s.key">{{ s.label }}</button>
      </div>
      <select v-model.number="days" style="width:auto" aria-label="How far ahead">
        <option :value="90">3 months</option>
        <option :value="180">6 months</option>
        <option :value="365">1 year</option>
        <option :value="730">2 years</option>
      </select>
      <label class="try">
        Try
        <input v-model.number="tryAmount" type="number" min="0" step="10" placeholder="safe amount" aria-label="Monthly amount to try" />
        /month
      </label>
    </div>

    <div v-if="loading && !result" class="loading">Simulating amounts to find the most you can safely pay...</div>
    <div v-else-if="error" class="callout danger">{{ error.message }}</div>
    <div v-else-if="r && !r.available" class="empty-state" style="padding:1rem"><p>{{ r.reason }}.</p></div>
    <template v-else-if="r">
      <div class="hero" :class="{ unsafe: !r.monthly_is_safe }">
        <div class="hero-amount">{{ currency(r.monthly) }}<span>/month</span></div>
        <div class="hero-text">
          <template v-if="tryAmount == null">
            is the most you can put toward debt and still never drop below
            {{ currency(r.floor) }} in checking or pay anything late.
            <span v-if="r.capped">More than that is safe too: this already clears the debt you're paying down.</span>
          </template>
          <template v-else-if="r.monthly_is_safe">is safe: checking stays above {{ currency(r.floor) }} with nothing late.</template>
          <template v-else>is too much. Checking would drop below {{ currency(r.floor) }} or a bill would be late.
            The most that's safe is <a href="#" @click.prevent="tryAmount = null">{{ currency(r.safe_monthly) }}/month</a>.</template>
          <div class="muted" style="font-size:0.78rem;margin-top:0.3rem">
            Split across your paydays, paid from {{ r.source }}, {{ r.strategy_label.toLowerCase() }}. Every amount was run
            through the full day-by-day plan.
          </div>
        </div>
      </div>

      <div class="cmp-grid">
        <div class="cmp">
          <span class="cmp-label">Saved over {{ horizonLabel }}</span>
          <strong :class="r.saved > 0 ? 'positive' : ''">{{ currency(r.saved) }}</strong>
          <small>less interest, so you keep more</small>
        </div>
        <div class="cmp">
          <span class="cmp-label">Debt at the end</span>
          <strong>{{ currency(r.plan.debt) }}</strong>
          <small>instead of {{ currency(r.base.debt) }}</small>
        </div>
        <div class="cmp">
          <span class="cmp-label">Interest charged</span>
          <strong>{{ currency(r.plan.interest) }}</strong>
          <small>instead of {{ currency(r.base.interest) }}</small>
        </div>
        <div class="cmp">
          <span class="cmp-label">Lowest checking</span>
          <strong :class="r.plan.lowest < r.floor ? 'negative' : ''">{{ currency(r.plan.lowest) }}</strong>
          <small>on {{ fmtDateShort(r.plan.lowest_date) }}</small>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>{{ strategy === 'avalanche' ? 'Order (highest rate first)' : 'Order (smallest first)' }}</th><th style="text-align:right">Rate</th><th style="text-align:right">Owed now</th><th style="text-align:right">Extra paid</th><th>Paid off</th></tr>
          </thead>
          <tbody>
            <tr v-for="(d, i) in r.debts" :key="d.bank + d.account">
              <td><span class="order">{{ i + 1 }}</span> <strong style="font-weight:600">{{ d.account }}</strong> <small class="muted">{{ KIND[d.kind] }}</small></td>
              <td style="text-align:right">{{ pct(d.rate) }}</td>
              <td style="text-align:right">{{ currency(d.balance) }}</td>
              <td style="text-align:right" :class="d.extra_paid > 0 ? 'positive' : 'muted'">{{ d.extra_paid > 0 ? currency(d.extra_paid) : '—' }}</td>
              <td>
                <span v-if="d.paid_off_plan" class="badge badge-success">{{ fmtDateShort(d.paid_off_plan) }}</span>
                <span v-else class="muted">not in {{ horizonLabel }}</span>
                <small v-if="d.paid_off_plan && !d.paid_off_base" class="muted"> (wouldn't be otherwise)</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="r.monthly > 0" class="muted" style="font-size:0.8rem;margin:0.6rem 0 0">
        {{ r.other_strategy.label }} would save {{ currency(r.other_strategy.saved) }} with the same
        amount<template v-if="Math.abs(r.other_strategy.saved - r.saved) < 1">, the same here.</template><template
          v-else-if="r.other_strategy.saved > r.saved">, more than this.
          <a href="#" @click.prevent="strategy = r.other_strategy.strategy">Switch</a></template><template
          v-else>. {{ r.strategy_label }} is the better pick.</template>
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { refDebounced } from '../utils/debounce'
import { GET_DEBT_BOOST } from '../graphql/tools'
import { currency, fmtDateShort, pct } from '../utils/format'

interface Debt { bank: string; account: string; kind: string; balance: number; rate: number; extra_paid: number
  paid_off_base: string | null; paid_off_plan: string | null }
interface Outcome { debt: number; interest: number; lowest: number; lowest_date: string; late: number; score: number }
interface Boost {
  available: boolean; reason?: string; strategy: string; strategy_label: string; days: number; debts: Debt[]
  floor: number; source: string | null; safe_monthly: number; monthly: number; monthly_is_safe: boolean; capped: boolean
  extra_paid: number; base: Outcome; plan: Outcome; saved: number
  other_strategy: { strategy: string; label: string; saved: number; debt: number }
}

const STRATS = [
  { key: 'avalanche', label: 'Highest interest first', hint: 'Avalanche: saves the most interest' },
  { key: 'snowball', label: 'Smallest balance first', hint: 'Snowball: clears accounts fastest' },
]
const KIND: Record<string, string> = { credit: 'card', heloc: 'HELOC', mortgage: 'mortgage' }

const strategy = ref('avalanche')
const days = ref(180)
const tryAmount = ref<number | null>(null)
const tryDebounced = refDebounced(tryAmount, 600)

const { result, loading, error } = useQuery<{ debtBoost: string }>(GET_DEBT_BOOST, () => ({
  variables: {
    days: days.value, strategy: strategy.value,
    monthly: tryDebounced.value == null || (tryDebounced.value as unknown) === '' ? null : Number(tryDebounced.value),
  },
  fetchPolicy: 'cache-and-network',
}))
const r = computed<Boost | null>(() => {
  const raw = result.value?.debtBoost
  return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : null
})
const horizonLabel = computed(() => ({ 90: '3 months', 180: '6 months', 365: 'a year', 730: '2 years' } as Record<number, string>)[days.value] ?? `${days.value} days`)
</script>

<style scoped>
.tool-controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin-bottom: 1rem; }
.try { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; font-weight: 500; text-transform: none; letter-spacing: normal; color: var(--text-muted); margin: 0 0 0 auto; }
.try input { width: 8rem; }
.hero { display: flex; gap: 1.1rem; align-items: center; padding: 1rem 1.1rem; border-radius: 12px; background: var(--success-light); margin-bottom: 1rem; }
.hero.unsafe { background: var(--danger-light); }
.hero-amount { font-size: 2rem; font-weight: 750; letter-spacing: -0.02em; white-space: nowrap; color: var(--success-text); }
.hero.unsafe .hero-amount { color: var(--danger-text); }
.hero-amount span { font-size: 0.95rem; font-weight: 550; margin-left: 0.15rem; }
.hero-text { font-size: 0.9rem; line-height: 1.45; }
.cmp-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.7rem; margin-bottom: 1rem; }
.cmp { border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.8rem; display: flex; flex-direction: column; gap: 0.15rem; }
.cmp-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; }
.cmp strong { font-size: 1.15rem; font-variant-numeric: tabular-nums; }
.cmp small { font-size: 0.75rem; color: var(--text-light); }
.order { display: inline-grid; place-items: center; width: 1.3rem; height: 1.3rem; border-radius: 999px; background: var(--primary-light); color: var(--primary); font-size: 0.72rem; font-weight: 700; margin-right: 0.25rem; }
@media (max-width: 760px) {
  .cmp-grid { grid-template-columns: 1fr 1fr; }
  .hero { flex-direction: column; align-items: flex-start; gap: 0.4rem; }
  .try { margin-left: 0; }
}
</style>
