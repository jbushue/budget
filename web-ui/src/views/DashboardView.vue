<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Dashboard</h2>
        <p class="view-sub">Where your money stands today and what's coming up.</p>
      </div>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
        <RouterLink to="/accounts?action=balances" class="btn btn-outline"><Icon name="pencil" :size="15" /> Update balances</RouterLink>
        <RouterLink to="/transactions?action=add" class="btn btn-outline"><Icon name="plus" :size="15" /> Transaction</RouterLink>
        <button class="btn btn-ghost btn-icon" title="Refresh" aria-label="Refresh" @click="refreshAll()"><Icon name="refresh" :size="16" /></button>
      </div>
    </div>

    <div v-if="loading && !result" class="loading">Loading financial snapshot...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">Error: {{ error.message }}</div>

    <template v-else-if="snap">
      <template v-if="dash">
        <!-- 1. Can my bills be paid? -->
        <div class="card status-banner" :class="`status-${dash.status}`">
          <div class="status-icon"><Icon :name="STATUS_ICON[dash.status]" :size="22" :stroke="2.2" /></div>
          <div style="flex:1;min-width:0">
            <div class="status-title">{{ dash.statusTitle }}</div>
            <div class="status-detail">{{ dash.statusDetail }}</div>
          </div>
          <router-link to="/optimizer" class="btn btn-outline btn-sm">See the plan</router-link>
        </div>

        <div class="grid grid-2" style="margin-bottom:1.5rem;align-items:start">
          <!-- 2. How much can I spend? -->
          <div class="card">
            <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem">
              <span class="card-title">Safe to spend</span>
              <router-link to="/optimizer" class="plan-chip" title="The plan bills, Safe to spend and the timeline follow. Change it on the Optimizer page.">
                <Icon name="zap" :size="12" /> {{ PLAN_LABELS[dash.planGoal || ''] || 'Most cash' }}{{ dash.planTarget ? `: ${dash.planTarget}` : '' }} plan
              </router-link>
            </div>
            <div class="safe-amount" :class="dash.safeToSpend > 0 ? 'positive' : 'negative'">{{ currency(dash.safeToSpend) }}</div>
            <div style="font-size:0.9rem;margin-bottom:0.75rem">
              <template v-if="dash.nextPayday">
                That's about <strong>{{ currency(dash.safePerDay) }}/day</strong> until your {{ fmtDateShort(dash.nextPayday) }} paycheck
                ({{ daysUntil(dash.nextPayday) }} day{{ daysUntil(dash.nextPayday) === 1 ? '' : 's' }}).
              </template>
              <template v-else>No upcoming income found — this is what you can spend over the next few weeks.</template>
            </div>
            <div v-if="(dash.heldForLater ?? 0) > 0.5" class="held-later">
              <strong>{{ currency(dash.heldForLater ?? 0) }}</strong> of today's money is kept for bills after your next paycheck
              <template v-if="heldFor.length">:
                <span v-for="(h, i) in heldFor" :key="i">{{ i ? ', ' : '' }}{{ billName(h.name) }} {{ currency(h.amount) }} ({{ fmtDateShort(h.date) }})</span>
              </template>.
              Your paychecks before then aren't enough to cover them on their own.
            </div>
            <div v-if="dash.everydayWeekly > 0" class="hint">
              On top of your usual {{ currency(dash.everydayWeekly) }}/week everyday spending
              ({{ dash.spendingMode === 'learned' ? 'learned from your transactions' : 'set in Settings' }}).
            </div>
            <div v-else class="hint hint-warn">
              Everyday spending (groceries, gas, eating out) isn't set, so this assumes you spend nothing besides bills.
              <router-link to="/settings">Set it in Settings</router-link> for an accurate number.
            </div>
            <details style="margin-top:0.75rem;font-size:0.8rem;color:var(--text-muted)">
              <summary style="cursor:pointer">How this is worked out</summary>
              <table style="margin-top:0.4rem">
                <tr><td>Checking today</td><td style="text-align:right">{{ currency(dash.checkingNow) }}</td></tr>
                <tr v-if="(dash.heldForLater ?? 0) > 0.5"><td>Lowest before your second paycheck</td><td style="text-align:right">{{ currency(dash.nearLowest ?? 0) }}</td></tr>
                <tr v-if="(dash.heldForLater ?? 0) > 0.5"><td>− Kept for bills later (lowest point {{ fmtDateShort(dash.lowestDate) }})</td><td style="text-align:right">{{ currency(dash.heldForLater ?? 0) }}</td></tr>
                <tr v-else><td>Lowest point ({{ fmtDateShort(dash.lowestDate) }}), after bills{{ dash.everydayWeekly > 0 ? ' and everyday spending' : '' }}</td><td style="text-align:right">{{ currency(dash.lowestBalance) }}</td></tr>
                <tr v-if="(dash.parkedAtLowest ?? 0) > 0.5"><td style="padding-left:0.75rem">of which the plan keeps in savings or pays toward debt early (still yours)</td><td style="text-align:right">{{ currency(dash.parkedAtLowest ?? 0) }}</td></tr>
                <tr><td>− Cushion you keep</td><td style="text-align:right">{{ currency(dash.cushion) }}</td></tr>
                <tr v-if="dash.overdueTotal"><td>− Overdue bills not marked paid</td><td style="text-align:right">{{ currency(dash.overdueTotal) }}</td></tr>
                <tr v-if="dash.shortTotal"><td>− Bills the plan can't pay on time</td><td style="text-align:right">{{ currency(dash.shortTotal) }}</td></tr>
                <tr v-if="dash.goalReserves"><td>− Set aside for goals</td><td style="text-align:right">{{ currency(dash.goalReserves) }}</td></tr>
                <tr style="font-weight:600"><td>= Safe to spend</td><td style="text-align:right">{{ currency(dash.safeToSpend) }}</td></tr>
              </table>
              <p style="margin:0.4rem 0 0">Spending today lowers every later day's balance, so the limit is set by your lowest
                projected point over the next {{ dash.lookaheadDays ?? 90 }} days, following your plan (bills, card and promo
                payments, and the optimizer's moves).</p>
            </details>
          </div>

          <!-- 3. This pay period's bills -->
          <div class="card">
            <div class="card-header">
              <span class="card-title">Bills {{ dash.nextPayday ? `before your ${fmtDateShort(dash.nextPayday)} paycheck` : 'coming up' }}</span>
            </div>
            <div v-if="!dash.billsThisPeriod.length" class="empty-state" style="padding:1rem"><p>Nothing due before your next paycheck.</p></div>
            <ul v-else class="period-list">
              <li v-for="b in dash.billsThisPeriod" :key="b.billName + b.dueDate" :class="`period-${b.status}`">
                <div style="flex:1;min-width:0">
                  <div style="font-weight:500">{{ billName(b.name) }}</div>
                  <div style="font-size:0.75rem;color:var(--text-muted)">
                    <template v-if="b.status === 'overdue'">Was due {{ fmtDateShort(b.dueDate) }} ({{ b.daysOverdue }}d ago)</template>
                    <template v-else>Due {{ fmtDateShort(b.dueDate) }}</template>
                    <template v-if="b.sourceAccount"> · {{ b.sourceAccount }}</template>
                  </div>
                </div>
                <div style="text-align:right">
                  <div style="font-weight:600">{{ currency(b.amount) }}</div>
                  <span class="badge" :class="PERIOD_BADGE[b.status].cls">{{ PERIOD_BADGE[b.status].label }}{{ b.status === 'short' && b.shortBy >= 0.01 ? ` ${currency(b.shortBy)}` : '' }}</span>
                </div>
                <button v-if="b.status !== 'paid'" class="btn btn-sm btn-outline" style="margin-left:0.5rem" @click="payBill = { name: b.name, billName: b.billName, amount: b.amount, sourceAccount: b.sourceAccount, dueDate: b.dueDate }">Mark paid</button>
              </li>
            </ul>
            <div v-if="dash.upcomingIncome.length" style="font-size:0.8rem;color:var(--text-muted);margin-top:0.75rem">
              Next paychecks:
              <span v-for="(inc, i) in dash.upcomingIncome" :key="i">{{ i ? ', ' : '' }}{{ fmtDateShort(inc.date) }} {{ inc.name }} {{ currency(inc.amount) }}</span>
            </div>
          </div>
        </div>

        <!-- Checking ahead: the same numbers Safe to spend comes from -->
        <div v-if="planSeries.length" class="card" style="margin-bottom:1.5rem">
          <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem">
            <span class="card-title">Checking over the next {{ dash.lookaheadDays ?? 90 }} days</span>
            <router-link to="/timeline" class="link-more">Day by day <Icon name="chevronRight" :size="14" /></router-link>
          </div>
          <div style="height:240px">
            <Line :data="chartData" :options="chartOptions" />
          </div>
          <p class="muted chart-note">
            Following your plan, after bills{{ dash.everydayWeekly > 0 ? ' and everyday spending' : '' }}. Money the plan
            parks in savings or puts toward debt early is counted as yours. Lowest point
            {{ currency(dash.lowestBalance) }} on {{ fmtDateShort(dash.lowestDate) }}.
          </p>
        </div>

        <!-- Top recommendations -->
        <div v-if="dash.insights.length" class="card" style="margin-bottom:1.5rem">
          <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
            <span class="card-title">What to do next</span>
            <router-link to="/optimizer" class="link-more">Full payment plan <Icon name="chevronRight" :size="14" /></router-link>
          </div>
          <InsightList :items="dash.insights" compact />
        </div>
        <OtherMoneyCard :data="dash.otherMoney" style="margin-bottom:1.5rem" />
        <BillMatchSuggestions style="margin-bottom:1.5rem" @changed="refreshAll" />
      </template>
      <div v-else-if="dashLoading" class="loading">Checking your bills...</div>
      <div v-else-if="dashError" class="card" style="color:var(--danger);margin-bottom:1.5rem">Could not check your bills: {{ dashError.message }}</div>

      <MarkPaidDialog :bill="payBill" @close="payBill = null" @paid="refreshAll" />

      <h3 class="section-heading">Where things stand</h3>
      <div class="grid grid-4" style="margin-bottom:1.5rem">
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(snap.totalAssets) }}</div>
          <div class="stat-label">Total assets</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value negative">{{ currency(snap.totalLiabilities) }}</div>
          <div class="stat-label">Total liabilities</div>
        </div>
        <RouterLink to="/net-worth" class="card stat-card kpi-link" title="Assets, debts and net worth over time">
          <div class="stat-value" :class="snap.netWorth >= 0 ? 'positive' : 'negative'">{{ currency(snap.netWorth) }}</div>
          <div class="stat-label">Net worth</div>
        </RouterLink>
        <RouterLink to="/checkup" class="card stat-card kpi-link" title="Savings rate, emergency fund, debt and more">
          <div class="stat-value neutral">
            {{ health?.score ?? '—' }}<span v-if="health?.grade" class="grade">{{ health.grade }}</span>
          </div>
          <div class="stat-label">Health score</div>
        </RouterLink>
      </div>

      <div class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
          <span class="card-title">Banks & accounts</span>
          <router-link to="/accounts" class="link-more">Accounts <Icon name="chevronRight" :size="14" /></router-link>
        </div>
        <div v-if="snap.banks.length" class="bank-grid">
          <div v-for="bank in snap.banks" :key="bank.name" class="bank-block">
            <div class="bank-name">{{ bank.name }}</div>
            <table>
              <tr v-for="acc in bank.bankAccounts" :key="acc.id">
                <td>{{ acc.accountName }} <span v-if="isSynced(bank.name, acc.accountName)" class="sync-badge" title="Synced via SimpleFIN"><Icon name="refresh" :size="12" /></span></td>
                <td><span class="badge">{{ accountTypeLabel(acc.accountType) }}</span></td>
                <td style="text-align:right;font-weight:600" :class="acc.balance >= 0 ? 'positive' : 'negative'">{{ currency(acc.balance) }}</td>
              </tr>
              <tr v-for="cc in bank.creditAccounts" :key="cc.id">
                <td>{{ cc.accountName }} <span v-if="isSynced(bank.name, cc.accountName)" class="sync-badge" title="Synced via SimpleFIN"><Icon name="refresh" :size="12" /></span></td>
                <td><span class="badge">Credit</span></td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">-{{ currency(cc.balance) }}</td>
              </tr>
              <tr v-for="m in bank.mortgageAccounts" :key="m.id">
                <td>{{ m.accountName }} <span v-if="isSynced(bank.name, m.accountName)" class="sync-badge" title="Synced via SimpleFIN"><Icon name="refresh" :size="12" /></span></td>
                <td><span class="badge">Mortgage</span></td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">{{ currency(m.currentPrincipal) }}</td>
              </tr>
              <tr v-for="h in bank.helocAccounts" :key="h.id">
                <td>{{ h.accountName }} <span v-if="isSynced(bank.name, h.accountName)" class="sync-badge" title="Synced via SimpleFIN"><Icon name="refresh" :size="12" /></span></td>
                <td><span class="badge">HELOC</span></td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">-{{ currency(h.balance) }}</td>
              </tr>
            </table>
          </div>
        </div>
        <div v-else class="empty-state">
          <div class="icon"><Icon name="accounts" :size="26" /></div>
          <p>No banks yet. Go to Accounts to add one.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import Icon from '../components/Icon.vue'
import { computed, ref } from 'vue'
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
import {
  GET_SNAPSHOT,
  GET_SIMPLEFIN_SYNCED_ACCOUNTS,
  GET_DASHBOARD_SUMMARY,
} from '../graphql/queries'
import { GET_HEALTH_CHECK } from '../graphql/planning'
import InsightList from '../components/InsightList.vue'
import BillMatchSuggestions from '../components/BillMatchSuggestions.vue'
import OtherMoneyCard from '../components/OtherMoneyCard.vue'
import MarkPaidDialog, { type PayableBill } from '../components/MarkPaidDialog.vue'
import { currency, fmtDateShort, daysFromNow, billName, accountTypeLabel } from '../utils/format'
import { PLAN_LABELS } from '../utils/plan'
import type { HealthCheck } from '../types'
import type { FinancialSnapshot, SimplefinSyncedAccount, DashboardSummary, PeriodBillStatus } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler, Legend)

const { result, loading, error, refetch } = useQuery<{ snapshot: FinancialSnapshot }>(GET_SNAPSHOT)
const { result: dashResult, loading: dashLoading, error: dashError, refetch: refetchDash } = useQuery<{ dashboardSummary: DashboardSummary | null }>(
  GET_DASHBOARD_SUMMARY, { fetchPolicy: 'cache-and-network' })
const { result: syncedResult } = useQuery<{ simplefinSyncedAccounts: SimplefinSyncedAccount[] }>(GET_SIMPLEFIN_SYNCED_ACCOUNTS)

const { result: healthResult, refetch: refetchHealth } = useQuery<{ healthCheck: HealthCheck }>(GET_HEALTH_CHECK)
const health = computed(() => healthResult.value?.healthCheck)

const snap = computed(() => result.value?.snapshot)
const dash = computed(() => dashResult.value?.dashboardSummary)
const heldFor = computed<{ name: string; date: string; amount: number }[]>(() => {
  const raw = dash.value?.heldFor
  if (!raw) return []
  try { return typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return [] }
})
const planSeries = computed<{ date: string; amount: number }[]>(() => {
  const raw = dash.value?.planSeries
  if (!raw) return []
  try { return typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return [] }
})

const payBill = ref<PayableBill | null>(null)

function refreshAll() {
  refetch()
  refetchDash()
  refetchHealth()
}

const STATUS_ICON: Record<DashboardSummary['status'], string> = { ok: 'check', warning: 'alert', danger: 'alertCircle' }

const PERIOD_BADGE: Record<PeriodBillStatus, { label: string; cls: string }> = {
  paid: { label: 'Paid', cls: 'badge-success' },
  covered: { label: 'Covered', cls: 'badge-info' },
  covered_by_plan: { label: 'Covered with plan', cls: 'badge-warning' },
  short: { label: 'Short', cls: 'badge-danger' },
  overdue: { label: 'Overdue', cls: 'badge-danger' },
}

function daysUntil(iso: string): number {
  return Math.max(1, daysFromNow(iso) + 1)
}


// Build a Set of "bankName:accountName" keys for synced accounts
const syncedKeys = computed(() => {
  const set = new Set<string>()
  for (const sa of syncedResult.value?.simplefinSyncedAccounts ?? []) {
    set.add(`${sa.bankName}:${sa.accountName}`)
  }
  return set
})

function isSynced(bankName: string, accountName: string): boolean {
  return syncedKeys.value.has(`${bankName}:${accountName}`)
}

// Checking ahead (from the dashboard summary: the same plan and numbers as Safe to spend)
const chartData = computed(() => {
  const pts = planSeries.value
  const lowIdx = pts.reduce((best, p, i) => (p.amount < pts[best].amount ? i : best), 0)
  return {
    labels: pts.map(p => fmtDateShort(p.date)),
    datasets: [
      {
        label: 'Checking',
        data: pts.map(p => p.amount),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.08)',
        fill: true,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: pts.map((_, i) => (i === lowIdx ? 4 : 0)),
        pointBackgroundColor: '#ef4444',
      },
      {
        label: 'Cushion',
        data: pts.map(() => dash.value?.cushion ?? 0),
        borderColor: '#f59e0b',
        borderDash: [5, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        fill: false,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (c: any) => `${c.dataset.label}: ${currency(c.parsed.y ?? 0)}` } },
  },
  scales: {
    x: { ticks: { maxTicksLimit: 8, font: { size: 10 } } },
    y: { ticks: { callback: (v: any) => '$' + Number(v).toLocaleString(), font: { size: 10 } } },
  },
}
</script>

<style scoped>
.status-banner { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; position: relative; overflow: hidden; }
.status-banner::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--border-strong); }
.status-ok::before { background: var(--success); }
.status-warning::before { background: var(--warning); }
.status-danger::before { background: var(--danger); }
.status-icon {
  flex: 0 0 44px; width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center;
  background: var(--surface-alt); color: var(--text-muted);
}
.status-ok .status-icon { background: var(--success-light); color: var(--success-text); }
.status-warning .status-icon { background: var(--warning-light); color: var(--warning-text); }
.status-danger .status-icon { background: var(--danger-light); color: var(--danger-text); }
.status-title { font-size: 1.1rem; font-weight: 650; letter-spacing: -0.01em; }
.status-detail { font-size: 0.85rem; color: var(--text-muted); margin-top: 0.15rem; }
.section-heading { margin: 0.5rem 0 0.75rem; font-size: 0.8rem; font-weight: 600; color: var(--text-light); letter-spacing: 0.02em; }
.link-more { display: inline-flex; align-items: center; gap: 0.15rem; font-size: 0.82rem; font-weight: 550; text-decoration: none; }
.bank-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem 2rem; }
.chart-note { font-size: 0.78rem; margin: 0.6rem 0 0; }
.bank-name { font-weight: 600; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.25rem; }
.safe-amount { font-size: 2.5rem; font-weight: 800; line-height: 1.1; margin-bottom: 0.4rem; }
.hint { font-size: 0.8rem; color: var(--text-muted); }
.hint-warn { color: var(--warning-text); background: var(--warning-light); padding: 0.4rem 0.6rem; border-radius: var(--radius); }
.held-later { font-size: 0.82rem; line-height: 1.45; background: var(--primary-light); color: var(--text); padding: 0.5rem 0.7rem; border-radius: var(--radius); margin-bottom: 0.6rem; }
.plan-chip { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.72rem; font-weight: 600; padding: 2px 9px; border-radius: 999px; background: var(--surface-alt); border: 1px solid var(--border); color: var(--text-muted); text-decoration: none; white-space: nowrap; }
.plan-chip:hover { color: var(--primary); border-color: var(--primary); }
.period-list { list-style: none; margin: 0; padding: 0; }
.period-list li { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
.period-list li:last-child { border-bottom: none; }
@media (max-width: 767px) {
  .status-banner { flex-wrap: wrap; gap: 0.6rem 0.85rem; }
  .status-banner > .btn { flex: 1 1 100%; }
  .status-title { font-size: 1.05rem; }
  .safe-amount { font-size: 2.1rem; }
}
.period-paid { opacity: 0.6; }
.period-short, .period-overdue { background: var(--danger-light); margin: 0 -0.5rem; padding-left: 0.5rem !important; padding-right: 0.5rem !important; border-radius: var(--radius-sm); }
.sync-badge { display: inline-flex; color: var(--text-light); cursor: help; vertical-align: middle; }
.kpi-link { color: inherit; text-decoration: none; }
.kpi-link:hover { border-color: var(--primary); }
.grade { font-size: 0.9rem; margin-left: 0.35rem; color: var(--text-muted); font-weight: 600; }
</style>
