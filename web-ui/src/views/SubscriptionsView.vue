<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Subscriptions</h2>
        <p class="view-sub">Recurring charges found in your transactions.</p>
      </div>
    </div>

    <div v-if="loading && !subs" class="loading">Loading...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="subs">
      <div v-if="!subs.items.length" class="empty-state">
        <div class="icon"><Icon name="repeat" :size="26" /></div>
        <p>No recurring charges found yet. They're picked up from your bills and from charges that repeat in your
          <RouterLink to="/transactions">transactions</RouterLink>.</p>
      </div>

      <template v-else>
        <div class="grid grid-3" style="margin-bottom:1.5rem">
          <div class="stat-card">
            <div class="stat-label">Per month</div>
            <div class="stat-value">{{ currency(subs.monthlyTotal) }}</div>
            <div class="sub">{{ subs.items.length }} recurring charges</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Per year</div>
            <div class="stat-value">{{ currency(subs.yearlyTotal) }}</div>
            <div class="sub">what they cost over 12 months</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Price increases</div>
            <div class="stat-value" :class="subs.priceIncreases.length ? 'negative' : 'positive'">{{ subs.priceIncreases.length }}</div>
            <div class="sub">{{ subs.priceIncreases.length ? subs.priceIncreases.join(', ') : 'none spotted' }}</div>
          </div>
        </div>

        <div v-if="increases.length" class="card warn-card">
          <strong>{{ increases.length === 1 ? 'A charge went up' : 'Some charges went up' }}</strong>
          <ul>
            <li v-for="i in increases" :key="i.name">
              {{ i.name }}: {{ currency(i.usualAmount) }} → <strong>{{ currency(i.amount) }}</strong>
              (+{{ currency(i.priceIncrease * perYear(i.frequency)) }}/year)
            </li>
          </ul>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">All recurring charges</span>
            <div class="chip-group" style="margin:0">
              <button v-for="f in FILTERS" :key="f.key" class="chip" :class="{ selected: filter === f.key }" @click="filter = f.key">{{ f.label }}</button>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th><th>How often</th><th style="text-align:right">Charge</th>
                  <th style="text-align:right">Monthly</th><th style="text-align:right">Yearly</th><th>Next</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="i in shown" :key="i.source + i.name">
                  <td>
                    <div style="font-weight:500">{{ i.name }}</div>
                    <div class="sub">
                      {{ SOURCE[i.source] }}<template v-if="i.category"> · {{ i.category }}</template>
                      <template v-if="i.count"> · seen {{ i.count }}×</template>
                    </div>
                  </td>
                  <td>{{ FREQ[i.frequency] ?? i.frequency }}</td>
                  <td style="text-align:right;white-space:nowrap">
                    {{ currency(i.amount) }}
                    <div v-if="i.priceIncrease" class="negative" style="font-size:0.75rem">▲ {{ currency(i.priceIncrease) }}</div>
                  </td>
                  <td style="text-align:right">{{ currency(i.monthlyCost) }}</td>
                  <td style="text-align:right;font-weight:600">{{ currency(i.yearlyCost) }}</td>
                  <td>{{ i.nextExpected ? fmtDateShort(i.nextExpected) : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="hint">
            "From transactions" means the same payee charged about the same amount on a regular schedule.
            Cancelling one you don't use saves its yearly cost.
          </p>
        </div>
      </template>
    </template>

    <RecurringSuggestions style="margin-top:1.5rem" @added="refetch()" />
  </div>
</template>

<script setup lang="ts">
import Icon from '../components/Icon.vue'
import { ref, computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { GET_SUBSCRIPTIONS } from '../graphql/planning'
import RecurringSuggestions from '../components/RecurringSuggestions.vue'
import { currency, fmtDateShort } from '../utils/format'
import type { Subscription, Subscriptions } from '../types'

const { result, loading, error, refetch } = useQuery<{ subscriptions: Subscriptions }>(GET_SUBSCRIPTIONS,
  { fetchPolicy: 'cache-and-network' })
const subs = computed(() => result.value?.subscriptions)

const FREQ: Record<string, string> = {
  weekly: 'Weekly', biweekly: 'Every 2 weeks', monthly: 'Monthly', quarterly: 'Quarterly',
  semi_annual: 'Twice a year', yearly: 'Yearly',
}
const SOURCE: Record<string, string> = { bill: 'Bill, paid from transactions', payee: 'From transactions', scheduled: 'Bill' }
const PER_YEAR: Record<string, number> = { weekly: 52, biweekly: 26, monthly: 12, quarterly: 4, semi_annual: 2, yearly: 1 }
const perYear = (f: string) => PER_YEAR[f] ?? 12

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'payee', label: 'Subscriptions' },
  { key: 'bills', label: 'Bills' },
]
const filter = ref('all')
const shown = computed(() => (subs.value?.items ?? []).filter(i =>
  filter.value === 'all' || (filter.value === 'payee' ? i.source === 'payee' : i.source !== 'payee')))
const increases = computed<Subscription[]>(() => (subs.value?.items ?? []).filter(i => i.priceIncrease > 0))
</script>

<style scoped>
.sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem; }
.hint { font-size: 0.8rem; color: var(--text-muted); margin: 0.75rem 0 0; }
.warn-card { border-left: 4px solid var(--warning); margin-bottom: 1.5rem; }
.warn-card ul { margin: 0.4rem 0 0; padding-left: 1.2rem; font-size: 0.9rem; }
</style>
