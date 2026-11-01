<template>
  <div v-if="featured.length || totals.length" class="card">
    <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
      <span class="card-title">Benefits &amp; other money</span>
      <router-link to="/accounts" class="link-more">Accounts <Icon name="chevronRight" :size="14" /></router-link>
    </div>
    <p class="om-sub">Not part of Safe to spend: benefits can only buy certain things, and these accounts don't pay bills.</p>
    <ul class="om-list">
      <li v-for="o in featured" :key="o.bank + o.account">
        <span class="om-icon" :class="`g-${o.group}`"><Icon :name="o.group === 'benefits' ? 'tag' : 'banknote'" :size="15" /></span>
        <span class="om-main">
          <span class="om-name">{{ o.account }} <small>{{ o.label }}<template v-if="o.purpose"> · {{ o.purpose }}</template></small></span>
          <span class="om-meta">
            <template v-if="o.runs_out"><span class="warn">Runs out {{ fmtDateShort(o.runs_out) }}</span></template>
            <template v-else-if="o.weekly_spending > 0">{{ currency(o.weekly_spending) }}/week</template>
            <template v-if="o.next_refill">{{ o.runs_out || o.weekly_spending > 0 ? ' · ' : '' }}+{{ currency(o.refill_amount) }} on {{ fmtDateShort(o.next_refill) }}</template>
          </span>
        </span>
        <span class="om-bal">{{ currency(o.balance) }}</span>
      </li>
    </ul>
    <div v-if="totals.length" class="om-totals">
      <span v-for="t in totals" :key="t.label">{{ t.label }} <strong>{{ currency(t.total) }}</strong></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'
import { currency, fmtDateShort } from '../utils/format'
import { GROUP_LABELS } from '../utils/accountKinds'
import type { OtherMoney } from '../types'

const props = defineProps<{ data: string | OtherMoney[] | null | undefined }>()

const rows = computed<OtherMoney[]>(() => {
  const d = props.data
  if (!d) return []
  try { return typeof d === 'string' ? JSON.parse(d) : d } catch { return [] }
})
const featured = computed(() => rows.value.filter(o => (o.group === 'benefits' || o.group === 'cash')
  && (o.balance > 0 || o.refill_amount > 0)))
const totals = computed(() => (['savings', 'invested', 'other'] as const)
  .map(g => ({ label: GROUP_LABELS[g], total: rows.value.filter(o => o.group === g).reduce((s, o) => s + o.balance, 0) }))
  .filter(t => t.total > 0))
</script>

<style scoped>
.link-more { display: inline-flex; align-items: center; gap: 0.15rem; font-size: 0.82rem; font-weight: 550; text-decoration: none; }
.om-sub { font-size: 0.8rem; color: var(--text-muted); margin: -0.25rem 0 0.6rem; }
.om-list { list-style: none; margin: 0; padding: 0; }
.om-list li { display: flex; align-items: center; gap: 0.7rem; padding: 0.55rem 0; border-bottom: 1px solid var(--border); }
.om-list li:last-child { border-bottom: none; }
.om-icon { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; flex-shrink: 0; background: var(--primary-light); color: var(--primary); }
.om-icon.g-benefits { background: var(--warning-light); color: var(--warning-text); }
.om-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.om-name { font-weight: 600; font-size: 0.9rem; }
.om-name small { font-weight: 450; color: var(--text-muted); font-size: 0.75rem; margin-left: 0.25rem; }
.om-meta { font-size: 0.78rem; color: var(--text-muted); }
.om-meta .warn { color: var(--warning-text); font-weight: 550; }
.om-bal { font-weight: 650; font-variant-numeric: tabular-nums; }
.om-totals { display: flex; flex-wrap: wrap; gap: 0.4rem 1.2rem; font-size: 0.8rem; color: var(--text-muted); margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid var(--border); }
.om-totals strong { color: var(--text); margin-left: 0.2rem; font-variant-numeric: tabular-nums; }
</style>
