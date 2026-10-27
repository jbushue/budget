<template>
  <div>
    <div class="view-header">
      <h2>⚡ Payment Optimizer</h2>
      <div style="display:flex;gap:0.5rem;align-items:center">
        <select v-model.number="days" style="width:auto">
          <option :value="30">30 days</option>
          <option :value="60">60 days</option>
          <option :value="90">90 days</option>
          <option :value="180">6 months</option>
          <option :value="365">1 year</option>
        </select>
        <button class="btn btn-outline btn-sm" @click="refetchAll()">Analyze</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Analyzing your payment plan...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="ins">
      <!-- Headline -->
      <div class="card" :style="`margin-bottom:1.5rem;border-left:4px solid ${headlineColor}`">
        <div style="font-size:1.05rem;font-weight:600;margin-bottom:0.5rem">{{ ins.headline }}</div>
        <ul style="margin:0;padding-left:1.1rem;font-size:0.85rem;color:var(--text-muted)">
          <li v-for="(c, i) in ins.changes" :key="i">{{ c }}</li>
        </ul>
      </div>

      <!-- Due date vs optimized -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header">
          <span class="card-title">⚖️ Paying on due dates vs. the optimized plan ({{ ins.days }} days)</span>
        </div>
        <p style="font-size:0.8rem;color:var(--text-muted);margin:0 0 0.75rem">
          <strong>On due date</strong>: every bill comes out of its usual account on the day it's due, nothing else moves.
          <strong>Optimized</strong>: the same bills, plus the optimizer's routing and transfers (savings sweeps, HELOC parking, promo payoffs).
        </p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th></th>
                <th style="text-align:right">On due date</th>
                <th style="text-align:right">Optimized</th>
                <th style="text-align:right">Difference</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in comparisonRows" :key="row.label">
                <td>
                  <div style="font-weight:500">{{ row.label }}</div>
                  <div v-if="row.hint" style="font-size:0.72rem;color:var(--text-muted)">{{ row.hint }}</div>
                </td>
                <td style="text-align:right">{{ row.fmt(row.base) }}<div v-if="row.baseNote" class="cell-note">{{ row.baseNote }}</div></td>
                <td style="text-align:right">{{ row.fmt(row.opt) }}<div v-if="row.optNote" class="cell-note">{{ row.optNote }}</div></td>
                <td style="text-align:right;font-weight:600" :class="diffClass(row)">{{ diffText(row) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Recommendations -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header"><span class="card-title">🧭 Recommendations</span></div>
        <InsightList :items="ins.insights" />
      </div>

      <!-- When to pay each bill -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
          <span class="card-title">🗓️ When to pay each bill</span>
          <label style="font-size:0.8rem;display:flex;align-items:center;gap:0.35rem;cursor:pointer">
            <input v-model="attentionOnly" type="checkbox" style="width:auto" /> Only show bills that need attention
          </label>
        </div>
        <p style="font-size:0.8rem;color:var(--text-muted);margin:0 0 0.75rem">
          Next {{ Math.min(45, ins.days) }} days, plus any late payment in the window. Paying early only saves money on
          interest-bearing debt (credit cards, HELOCs, loan groups). For regular bills it just shrinks your cushion.
        </p>
        <div v-if="timingRows.length === 0" class="empty-state" style="padding:1rem">
          <p>{{ attentionOnly ? 'Nothing needs attention: every bill is covered on time.' : 'No payments due in this period.' }}</p>
        </div>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Due</th>
                <th>Bill</th>
                <th style="text-align:right">Amount</th>
                <th>Status</th>
                <th>Pay early?</th>
                <th>What to do</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in timingRows" :key="i" :style="r.status === 'late' ? 'background:var(--danger-light)' : ''">
                <td style="white-space:nowrap;font-size:0.85rem">{{ fmtDateShort(r.dueDate) }}</td>
                <td style="font-size:0.85rem">
                  <div style="font-weight:500">{{ r.name }}</div>
                  <div style="font-size:0.72rem;color:var(--text-muted)">
                    {{ KIND_LABELS[r.kind] }}<template v-if="r.sourceAccount"> · from {{ r.sourceAccount }}</template>
                  </div>
                </td>
                <td style="text-align:right;font-weight:600;white-space:nowrap">
                  {{ currency(r.amount) }}<span v-if="r.estimated" title="Estimated amount (floating bill)"> ~</span>
                </td>
                <td><span class="badge" :class="statusBadge(r).cls">{{ statusBadge(r).label }}</span></td>
                <td style="font-size:0.8rem;white-space:nowrap">
                  <span v-if="r.earlySavings > 0" class="positive" style="font-weight:600">
                    Saves {{ currency(r.earlySavings) }}
                    <div style="font-weight:400;color:var(--text-muted)">on {{ fmtDateShort(r.payEarlyDate) }} ({{ r.daysEarly }}d early)</div>
                  </span>
                  <span v-else-if="r.status === 'already_paid'" style="color:var(--text-muted)">-</span>
                  <span v-else style="color:var(--text-muted)">No benefit</span>
                </td>
                <td style="font-size:0.8rem;max-width:420px">
                  {{ r.advice }}
                  <ul v-if="r.fixes.length" style="margin:0.35rem 0 0;padding-left:1rem">
                    <li v-for="(f, j) in r.fixes" :key="j">{{ f }}</li>
                  </ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Bill groups -->
      <div v-for="g in ins.groups" :key="g.groupName" class="card" style="margin-bottom:1.5rem">
        <div class="card-header">
          <span class="card-title">📦 {{ g.groupName }}: how the {{ currency(g.payment) }} payment is split</span>
        </div>
        <div class="grid grid-2">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Loan</th>
                  <th style="text-align:right">Balance</th>
                  <th style="text-align:right">APR</th>
                  <th style="text-align:right">Interest / mo</th>
                  <th style="text-align:right">Gets next payment</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in g.members" :key="m.accountName">
                  <td>
                    {{ m.accountName }}
                    <span v-if="m.accountName === g.highestRateMember && g.reallocationSavings > 0" class="badge badge-warning" style="margin-left:0.25rem">highest rate</span>
                  </td>
                  <td style="text-align:right">{{ currency(m.balance) }}</td>
                  <td style="text-align:right">{{ pct(m.apr, 2) }}</td>
                  <td style="text-align:right">{{ currency(m.monthlyInterest) }}</td>
                  <td style="text-align:right;font-weight:600">{{ currency(m.nextPaymentShare) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>If you...</th>
                  <th style="text-align:right">Paid off in</th>
                  <th style="text-align:right">Total interest</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Keep the current split</td>
                  <td style="text-align:right">{{ monthsText(g.current) }}</td>
                  <td style="text-align:right">{{ interestText(g.current) }}</td>
                </tr>
                <tr v-if="g.members.length > 1">
                  <td>Send extra to the highest rate first</td>
                  <td style="text-align:right">{{ monthsText(g.highestRateFirst) }}</td>
                  <td style="text-align:right" :class="g.reallocationSavings > 0 ? 'positive' : ''">{{ interestText(g.highestRateFirst) }}</td>
                </tr>
                <tr>
                  <td>Pay {{ currency(g.withExtra.extraMonthly ?? 0) }} more each month</td>
                  <td style="text-align:right">{{ monthsText(g.withExtra) }}</td>
                  <td style="text-align:right" :class="g.withExtra.paysOff ? 'positive' : ''">{{ interestText(g.withExtra) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!g.current.paysOff" style="font-size:0.8rem;color:var(--danger);margin:0.5rem 0 0">
              The payment doesn't cover the {{ currency(g.monthlyInterest) }} of monthly interest, so the balance grows.
            </p>
            <p v-else-if="g.reallocationSavings > 0 && g.suggestedFixedAmount" style="font-size:0.8rem;color:var(--text-muted);margin:0.5rem 0 0">
              To aim at {{ g.highestRateMember }}: on the Bill Groups page set it to <strong>Fixed {{ currency(g.suggestedFixedAmount) }}</strong>,
              leaving the others enough to cover their interest. Your servicer must also apply payments that way.
            </p>
          </div>
        </div>
      </div>

      <!-- Promos -->
      <div v-if="ins.promos.length" class="card" style="margin-bottom:1.5rem">
        <div class="card-header"><span class="card-title">🏷️ 0% promo deadlines</span></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Promo</th>
                <th style="text-align:right">Balance</th>
                <th>Expires</th>
                <th style="text-align:right">Needed / mo</th>
                <th style="text-align:right">Deferred interest at stake</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in ins.promos" :key="p.card + p.promoName">
                <td>{{ p.promoName }} <span style="color:var(--text-muted);font-size:0.8rem">· {{ p.card }}</span></td>
                <td style="text-align:right">{{ currency(p.balance) }}</td>
                <td style="white-space:nowrap">{{ fmtDate(p.expires) }} <span style="color:var(--text-muted);font-size:0.75rem">({{ p.daysLeft }}d)</span></td>
                <td style="text-align:right">{{ currency(p.monthlyNeeded) }}</td>
                <td style="text-align:right" class="negative">{{ currency(p.interestAtRisk) }}</td>
                <td>
                  <span v-if="p.onTrack === true" class="badge badge-success">On track</span>
                  <span v-else-if="p.onTrack === false" class="badge badge-danger">Short {{ currency(p.shortfall) }}</span>
                  <span v-else class="badge badge-info">After this window</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Optimizer moves -->
      <div class="card" style="margin-bottom:1.5rem">
        <div class="card-header"><span class="card-title">🔁 What the optimized plan does</span></div>
        <div v-if="ins.optimizerMoves.length === 0" class="empty-state" style="padding:1rem">
          <p>No transfers needed: paying each bill on its due date is already the best plan for this period.</p>
        </div>
        <template v-else>
          <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin-bottom:1rem">
            <div v-for="grp in moveGroups" :key="grp.type" class="stat-card" style="padding:0.75rem;text-align:left;border:1px solid var(--border);border-radius:var(--radius)">
              <div style="font-weight:600;font-size:0.9rem">{{ eventIcon(grp.type) }} {{ grp.title }}</div>
              <div style="font-size:1.15rem;font-weight:700;margin:0.2rem 0">{{ currency(grp.total) }}</div>
              <div style="font-size:0.75rem;color:var(--text-muted)">{{ grp.count }} time(s). {{ grp.why }}</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Date</th><th>Move</th><th>Details</th><th style="text-align:right">Amount</th></tr>
              </thead>
              <tbody>
                <tr v-for="(m, i) in ins.optimizerMoves" :key="i" :style="{ borderLeft: `3px solid ${eventColor(m.type)}` }">
                  <td style="font-size:0.85rem;white-space:nowrap">{{ fmtDateShort(m.date) }}</td>
                  <td><span class="badge" :class="eventBadgeClass(m.type)">{{ eventIcon(m.type) }} {{ m.title }}</span></td>
                  <td style="font-size:0.85rem">{{ m.description }}</td>
                  <td style="text-align:right;font-weight:600">{{ currency(m.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <!-- Technical warnings from the optimizer -->
      <div v-if="plan && plan.violations.length" class="card" style="border-left:4px solid var(--warning)">
        <div class="card-header" style="cursor:pointer;user-select:none;display:flex;align-items:center;justify-content:space-between" @click="violationsOpen = !violationsOpen">
          <span class="card-title">🔧 Optimizer checks ({{ plan.violations.length }})</span>
          <span style="font-size:0.75rem;color:var(--text-muted)">{{ violationsOpen ? '▲ Collapse' : '▼ Expand' }}</span>
        </div>
        <ul v-show="violationsOpen" style="list-style:none;margin:0;padding:0">
          <li v-for="(v, i) in plan.violations" :key="i" style="padding:0.4rem 0;border-bottom:1px solid var(--border);font-size:0.85rem">
            <span v-if="v.startsWith('WARNING')" style="color:var(--warning)">&#9888;</span>
            <span v-else-if="v.startsWith('INFO')" style="color:var(--primary)">&#9432;</span>
            <span v-else style="color:var(--danger)">&#10060;</span>
            {{ v }}
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { GET_PAYMENT_INSIGHTS, GET_PAYMENT_PLAN } from '../graphql/queries'
import { currency, fmtDate, fmtDateShort, pct } from '../utils/format'
import InsightList from '../components/InsightList.vue'
import type { BillTiming, GroupPayoff, OutcomeSummary, PaymentInsights, PaymentPlan } from '../types'

const days = ref(90)
const violationsOpen = ref(false)
const attentionOnly = ref(false)

const { result, loading, error, refetch } = useQuery<{ paymentInsights: PaymentInsights }>(
  GET_PAYMENT_INSIGHTS, () => ({ variables: { days: days.value } })
)
const { result: planResult, refetch: refetchPlan } = useQuery<{ paymentPlan: PaymentPlan }>(
  GET_PAYMENT_PLAN, () => ({ variables: { days: days.value } })
)

function refetchAll() {
  refetch()
  refetchPlan()
}

const ins = computed(() => result.value?.paymentInsights)
const plan = computed(() => planResult.value?.paymentPlan)

const headlineColor = computed(() => {
  const sev = new Set(ins.value?.insights.map(i => i.severity))
  if (sev.has('urgent')) return 'var(--danger)'
  if (sev.has('warning')) return 'var(--warning)'
  return 'var(--success)'
})

// ── Comparison table ──────────────────────────────────────────────────

interface CompRow {
  label: string
  hint?: string
  base: number
  opt: number
  /** +1 when a higher value is better, -1 when lower is better */
  better: 1 | -1
  fmt: (v: number) => string
  baseNote?: string
  optNote?: string
}

const lowNote = (s: OutcomeSummary) =>
  s.lowestCheckingDate ? `${s.lowestCheckingAccount} on ${fmtDateShort(s.lowestCheckingDate)}` : undefined

const comparisonRows = computed<CompRow[]>(() => {
  const i = ins.value
  if (!i) return []
  const b = i.onDueDate, o = i.optimized
  const rows: CompRow[] = [
    { label: 'Late or missed payments', hint: 'Bills there isn\'t enough money for on the due date',
      base: b.latePayments.length, opt: o.latePayments.length, better: -1, fmt: v => String(v) },
    { label: 'Lowest checking balance', hint: 'Your tightest point in the window',
      base: b.lowestChecking ?? 0, opt: o.lowestChecking ?? 0, better: 1, fmt: currency,
      baseNote: lowNote(b), optNote: lowNote(o) },
    { label: 'Cash at the end', base: b.endingCash, opt: o.endingCash, better: 1, fmt: currency },
    { label: 'Debt at the end', hint: 'Cards, loans, HELOC and mortgage', base: b.endingDebt, opt: o.endingDebt, better: -1, fmt: currency },
    { label: 'Interest charged', hint: 'On cards and HELOCs', base: b.interestCharged, opt: o.interestCharged, better: -1, fmt: currency },
    { label: 'Interest earned', hint: 'On savings / checking', base: b.interestEarned, opt: o.interestEarned, better: 1, fmt: currency },
  ]
  if (b.fees || o.fees) {
    rows.push({ label: 'Late & overdraft fees', hint: 'Using the fees in Settings → Planning (and each bill’s own late fee)',
      base: b.fees, opt: o.fees, better: -1, fmt: currency })
  }
  if (b.pendingDeferredInterest || o.pendingDeferredInterest) {
    rows.push({ label: 'Deferred promo interest at risk', hint: 'If promo money still owed at the end isn\'t paid before the promo expires',
      base: b.pendingDeferredInterest, opt: o.pendingDeferredInterest, better: -1, fmt: currency })
  }
  rows.push({ label: 'Overall (cash − debt)', hint: 'The bottom line: how much better off you end up',
    base: b.netPosition, opt: o.netPosition, better: 1, fmt: currency })
  return rows
})

function diffText(row: CompRow): string {
  const d = row.opt - row.base
  if (Math.abs(d) < 0.005) return 'same'
  const s = row.fmt(Math.abs(d))
  return `${d > 0 ? '+' : '−'}${s}`
}

function diffClass(row: CompRow): string {
  const d = (row.opt - row.base) * row.better
  if (Math.abs(d) < 0.005) return 'neutral'
  return d > 0 ? 'positive' : 'negative'
}

// ── Bill timing ───────────────────────────────────────────────────────

const KIND_LABELS: Record<BillTiming['kind'], string> = {
  bill: 'Bill', floating: 'Variable bill', credit: 'Card payment', mortgage: 'Mortgage',
  heloc: 'HELOC payment', group: 'Loan group',
}

const timingRows = computed(() => {
  const rows = ins.value?.billTiming ?? []
  if (!attentionOnly.value) return rows
  return rows.filter(r => r.status === 'late' || r.earlySavings > 0
    || (r.cushionIfEarly != null && r.cushionIfEarly < 0 && r.earlySavings > 0))
})

function statusBadge(r: BillTiming): { label: string; cls: string } {
  if (r.status === 'already_paid') return { label: 'Paid', cls: 'badge-success' }
  if (r.status === 'late' && r.planStatus === 'paid') return { label: 'On time with plan', cls: 'badge-warning' }
  if (r.status === 'late') return { label: 'Short', cls: 'badge-danger' }
  return { label: 'On time', cls: 'badge-success' }
}

// ── Groups ────────────────────────────────────────────────────────────

function monthsText(p: GroupPayoff): string {
  if (!p.paysOff || p.months == null) return 'Never'
  const y = Math.floor(p.months / 12), m = p.months % 12
  return y ? `${y}y ${m}m` : `${m} mo`
}

function interestText(p: GroupPayoff): string {
  return p.paysOff && p.interest != null ? currency(p.interest) : '-'
}

// ── Optimizer moves ───────────────────────────────────────────────────

const moveGroups = computed(() => {
  const by = new Map<string, { type: string; title: string; why: string; total: number; count: number }>()
  for (const m of ins.value?.optimizerMoves ?? []) {
    const g = by.get(m.type) ?? { type: m.type, title: m.title, why: m.why, total: 0, count: 0 }
    g.total += m.amount
    g.count++
    by.set(m.type, g)
  }
  return [...by.values()]
})

function eventIcon(type: string): string {
  const map: Record<string, string> = {
    SAVINGS_SWEEP: '💸', SAVINGS_RECALL: '📥',
    HELOC_PARK: '🅿️', HELOC_RECALL: '⬆️',
    EXTRA_CREDIT_PAYMENT: '💳', PROMO_PAYOFF: '🏷️',
  }
  return map[type] || '📌'
}

function eventColor(type: string): string {
  const map: Record<string, string> = {
    SAVINGS_SWEEP: 'var(--success)',
    SAVINGS_RECALL: 'var(--warning)',
    HELOC_PARK: 'var(--primary)',
    HELOC_RECALL: 'var(--warning)',
    EXTRA_CREDIT_PAYMENT: 'var(--danger)',
    PROMO_PAYOFF: 'var(--danger)',
  }
  return map[type] || 'var(--text-muted)'
}

function eventBadgeClass(type: string): string {
  const map: Record<string, string> = {
    SAVINGS_SWEEP: 'badge-success',
    SAVINGS_RECALL: 'badge-warning',
    HELOC_PARK: 'badge-info',
    HELOC_RECALL: 'badge-warning',
    EXTRA_CREDIT_PAYMENT: 'badge-danger',
    PROMO_PAYOFF: 'badge-danger',
  }
  return map[type] || 'badge-info'
}
</script>

<style scoped>
.cell-note { font-size: 0.72rem; color: var(--text-muted); }
</style>
