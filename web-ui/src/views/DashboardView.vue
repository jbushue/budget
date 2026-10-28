<template>
  <div>
    <div class="view-header">
      <h2>Dashboard</h2>
      <button class="btn btn-outline btn-sm" @click="refreshAll()">Refresh</button>
    </div>

    <div v-if="loading" class="loading">Loading financial snapshot...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">Error: {{ error.message }}</div>

    <template v-else-if="snap">
      <template v-if="dash">
        <!-- 1. Can my bills be paid? -->
        <div class="card status-banner" :class="`status-${dash.status}`">
          <div class="status-icon">{{ STATUS_ICON[dash.status] }}</div>
          <div style="flex:1;min-width:0">
            <div class="status-title">{{ dash.statusTitle }}</div>
            <div class="status-detail">{{ dash.statusDetail }}</div>
          </div>
          <router-link to="/optimizer" class="btn btn-outline btn-sm">See the plan</router-link>
        </div>

        <div class="grid grid-2" style="margin-bottom:1.5rem;align-items:start">
          <!-- 2. How much can I spend? -->
          <div class="card">
            <div class="card-header"><span class="card-title">💵 Safe to spend</span></div>
            <div class="safe-amount" :class="dash.safeToSpend > 0 ? 'positive' : 'negative'">{{ currency(dash.safeToSpend) }}</div>
            <div style="font-size:0.9rem;margin-bottom:0.75rem">
              <template v-if="dash.nextPayday">
                That's about <strong>{{ currency(dash.safePerDay) }}/day</strong> until your {{ fmtDateShort(dash.nextPayday) }} paycheck
                ({{ daysUntil(dash.nextPayday) }} day{{ daysUntil(dash.nextPayday) === 1 ? '' : 's' }}).
              </template>
              <template v-else>No upcoming income found — this is what you can spend over the next few weeks.</template>
            </div>
            <div v-if="dash.everydayWeekly > 0" class="hint">
              On top of your usual {{ currency(dash.everydayWeekly) }}/week everyday spending
              ({{ dash.spendingMode === 'learned' ? 'learned from your transactions' : 'set in Settings' }}).
            </div>
            <div v-else class="hint hint-warn">
              ⚠️ Everyday spending (groceries, gas, eating out) isn't set, so this assumes you spend nothing besides bills.
              <router-link to="/settings">Set it in Settings</router-link> for an accurate number.
            </div>
            <details style="margin-top:0.75rem;font-size:0.8rem;color:var(--text-muted)">
              <summary style="cursor:pointer">How this is worked out</summary>
              <table style="margin-top:0.4rem">
                <tr><td>Checking today</td><td style="text-align:right">{{ currency(dash.checkingNow) }}</td></tr>
                <tr><td>Lowest point ({{ fmtDateShort(dash.lowestDate) }}), after bills{{ dash.everydayWeekly > 0 ? ' and everyday spending' : '' }}</td><td style="text-align:right">{{ currency(dash.lowestBalance) }}</td></tr>
                <tr><td>− Cushion you keep</td><td style="text-align:right">{{ currency(dash.cushion) }}</td></tr>
                <tr v-if="dash.overdueTotal"><td>− Overdue bills not marked paid</td><td style="text-align:right">{{ currency(dash.overdueTotal) }}</td></tr>
                <tr v-if="dash.shortTotal"><td>− Bills that can't be covered</td><td style="text-align:right">{{ currency(dash.shortTotal) }}</td></tr>
                <tr v-if="dash.goalReserves"><td>− Set aside for goals</td><td style="text-align:right">{{ currency(dash.goalReserves) }}</td></tr>
                <tr style="font-weight:600"><td>= Safe to spend</td><td style="text-align:right">{{ currency(dash.safeToSpend) }}</td></tr>
              </table>
              <p style="margin:0.4rem 0 0">Spending today lowers every later day's balance, so the limit is set by your lowest projected point through {{ fmtDateShort(dash.horizon) }}.</p>
            </details>
          </div>

          <!-- 3. This pay period's bills -->
          <div class="card">
            <div class="card-header">
              <span class="card-title">🧾 Bills {{ dash.nextPayday ? `before your ${fmtDateShort(dash.nextPayday)} paycheck` : 'coming up' }}</span>
            </div>
            <div v-if="!dash.billsThisPeriod.length" class="empty-state" style="padding:1rem"><p>Nothing due before your next paycheck. 🎉</p></div>
            <ul v-else class="period-list">
              <li v-for="b in dash.billsThisPeriod" :key="b.billName + b.dueDate" :class="`period-${b.status}`">
                <div style="flex:1;min-width:0">
                  <div style="font-weight:500">{{ b.name }}</div>
                  <div style="font-size:0.75rem;color:var(--text-muted)">
                    <template v-if="b.status === 'overdue'">Was due {{ fmtDateShort(b.dueDate) }} ({{ b.daysOverdue }}d ago)</template>
                    <template v-else>Due {{ fmtDateShort(b.dueDate) }}</template>
                    <template v-if="b.sourceAccount"> · {{ b.sourceAccount }}</template>
                  </div>
                </div>
                <div style="text-align:right">
                  <div style="font-weight:600">{{ currency(b.amount) }}</div>
                  <span class="badge" :class="PERIOD_BADGE[b.status].cls">{{ PERIOD_BADGE[b.status].label }}<template v-if="b.status === 'short'"> {{ currency(b.shortBy) }}</template></span>
                </div>
                <button v-if="b.status !== 'paid'" class="btn btn-sm btn-outline" style="margin-left:0.5rem" @click="payBill = { name: b.name, billName: b.billName, amount: b.amount, sourceAccount: b.sourceAccount }">Mark paid</button>
              </li>
            </ul>
            <div v-if="dash.upcomingIncome.length" style="font-size:0.8rem;color:var(--text-muted);margin-top:0.75rem">
              💰 Next paychecks:
              <span v-for="(inc, i) in dash.upcomingIncome" :key="i">{{ i ? ', ' : '' }}{{ fmtDateShort(inc.date) }} {{ inc.name }} {{ currency(inc.amount) }}</span>
            </div>
          </div>
        </div>

        <!-- Top recommendations -->
        <div v-if="dash.insights.length" class="card" style="margin-bottom:1.5rem">
          <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
            <span class="card-title">🧭 What to do next</span>
            <router-link to="/optimizer" style="font-size:0.8rem">See the full payment plan →</router-link>
          </div>
          <InsightList :items="dash.insights" compact />
        </div>
        <BillMatchSuggestions style="margin-bottom:1.5rem" @changed="refreshAll" />
      </template>
      <div v-else-if="dashLoading" class="loading">Checking your bills...</div>
      <div v-else-if="dashError" class="card" style="color:var(--danger);margin-bottom:1.5rem">Could not check your bills: {{ dashError.message }}</div>

      <MarkPaidDialog :bill="payBill" @close="payBill = null" @paid="refreshAll" />

      <h3 style="margin:0 0 0.75rem;font-size:1rem;color:var(--text-muted)">Details</h3>
      <!-- KPI row -->
      <div class="grid grid-4" style="margin-bottom:1.5rem">
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(snap.totalAssets) }}</div>
          <div class="stat-label">Total Assets</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value negative">{{ currency(snap.totalLiabilities) }}</div>
          <div class="stat-label">Total Liabilities</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value" :class="snap.netWorth >= 0 ? 'positive' : 'negative'">{{ currency(snap.netWorth) }}</div>
          <div class="stat-label">Net Worth</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value neutral">{{ snap.banks.length }}</div>
          <div class="stat-label">Banks</div>
        </div>
      </div>

      <!-- Banks overview + upcoming -->
      <div class="grid grid-2">
        <!-- Banks -->
        <div class="card">
          <div class="card-header"><span class="card-title">Banks & Accounts</span></div>
          <div v-for="bank in snap.banks" :key="bank.name" style="margin-bottom:1rem">
            <div style="font-weight:600;margin-bottom:0.25rem">{{ bank.name }}</div>
            <table>
              <tr v-for="acc in bank.bankAccounts" :key="acc.id">
                <td>{{ acc.accountName }} <span v-if="isSynced(bank.name, acc.accountName)" class="sync-badge" title="Synced via SimpleFIN">🔄</span></td>
                <td><span class="badge badge-info">{{ acc.accountType }}</span></td>
                <td style="text-align:right;font-weight:600" :class="acc.balance >= 0 ? 'positive' : 'negative'">{{ currency(acc.balance) }}</td>
              </tr>
              <tr v-for="cc in bank.creditAccounts" :key="cc.id">
                <td>{{ cc.accountName }} <span v-if="isSynced(bank.name, cc.accountName)" class="sync-badge" title="Synced via SimpleFIN">🔄</span></td>
                <td><span class="badge badge-warning">Credit</span></td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">-{{ currency(cc.balance) }}</td>
              </tr>
              <tr v-for="m in bank.mortgageAccounts" :key="m.id">
                <td>{{ m.accountName }} <span v-if="isSynced(bank.name, m.accountName)" class="sync-badge" title="Synced via SimpleFIN">🔄</span></td>
                <td><span class="badge badge-danger">Mortgage</span></td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">{{ currency(m.currentPrincipal) }}</td>
              </tr>
              <tr v-for="h in bank.helocAccounts" :key="h.id">
                <td>{{ h.accountName }} <span v-if="isSynced(bank.name, h.accountName)" class="sync-badge" title="Synced via SimpleFIN">🔄</span></td>
                <td><span class="badge badge-warning">HELOC</span></td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">-{{ currency(h.balance) }}</td>
              </tr>
            </table>
          </div>
          <div v-if="snap.banks.length === 0" class="empty-state">
            <div class="icon">🏦</div>
            <p>No banks yet. Go to Accounts to add one.</p>
          </div>
        </div>

        <!-- Upcoming events -->
        <div>
          <!-- Upcoming bills -->
          <div class="card" style="margin-bottom:1rem">
            <div class="card-header"><span class="card-title">Upcoming Bills (30 days)</span></div>
            <ul class="event-list" v-if="snap.upcomingBills30Days.length">
              <li v-for="b in snap.upcomingBills30Days" :key="b.id" class="event-item">
                <div>
                  <div style="font-weight:500;display:flex;align-items:center;gap:0.4rem">
                    <span v-if="b.isAccountLinked && b.linkedAccountType === 'credit'">💳</span>
                    <span v-else-if="b.isAccountLinked && b.linkedAccountType === 'mortgage'">🏠</span>
                    <span v-else-if="b.isAccountLinked && b.linkedAccountType === 'heloc'">🏦</span>
                    {{ b.billName }}
                    <span v-if="b.isPaidThisPeriod" class="badge badge-success" style="font-size:0.65rem">✓ Paid</span>
                  </div>
                  <div style="font-size:0.75rem;color:var(--text-muted)">{{ fmtDate(b.nextDueDate) }}</div>
                </div>
                <div style="font-weight:600" :style="b.isPaidThisPeriod ? 'color:var(--text-muted);text-decoration:line-through' : 'color:var(--danger)'">{{ currency(b.effectiveAmount || b.amount) }}</div>
              </li>
            </ul>
            <div v-else class="empty-state"><p>No bills due in 30 days</p></div>
          </div>

          <!-- Upcoming income -->
          <div class="card">
            <div class="card-header"><span class="card-title">Upcoming Income (30 days)</span></div>
            <ul class="event-list" v-if="snap.upcomingIncome30Days.length">
              <li v-for="i in snap.upcomingIncome30Days" :key="i.id" class="event-item">
                <div>
                  <div style="font-weight:500">{{ i.sourceName }}</div>
                  <div style="font-size:0.75rem;color:var(--text-muted)">{{ fmtDate(i.nextPayDate) }} &middot; {{ frequencyLabel(i.frequency) }}</div>
                </div>
                <div style="font-weight:600;color:var(--success)">{{ currency(i.amount) }}</div>
              </li>
            </ul>
            <div v-else class="empty-state"><p>No income expected in 30 days</p></div>
          </div>
        </div>
      </div>

      <!-- Net Worth History chart -->
      <div class="card" style="margin-top:1.5rem">
        <div class="card-header"><span class="card-title">📈 Net Worth Over Time</span></div>
        <div v-if="nwLoading" class="loading">Loading history...</div>
        <div v-else-if="nwError" style="color:var(--danger);font-size:0.85rem;padding:1rem 0">Could not load net worth history: {{ nwError.message }}</div>
        <div v-else-if="netWorthData && netWorthData.length > 1" style="height:250px">
          <Line :data="nwChartData" :options="nwChartOptions" />
        </div>
        <div v-else class="empty-state"><p>Not enough data yet. Net worth is recorded daily.</p></div>
      </div>

      <!-- Projection chart -->
      <div class="card" style="margin-top:1.5rem">
        <div class="card-header"><span class="card-title">90-Day Balance Projection</span></div>
        <div v-if="projLoading" class="loading">Calculating projection...</div>
        <div v-else-if="projError" style="color:var(--danger);font-size:0.85rem;padding:1rem 0">Could not load projection: {{ projError.message }}</div>
        <div v-else-if="projData" style="height:300px">
          <Line :data="chartData" :options="chartOptions" />
        </div>
      </div>

      <!-- Recent Bill Payments -->
      <div class="card" style="margin-top:1.5rem">
        <div class="card-header"><span class="card-title">💳 Recent Bill Payments</span></div>
        <div v-if="bphLoading" class="loading">Loading payment history...</div>
        <div v-else-if="bphError" style="color:var(--danger);font-size:0.85rem;padding:1rem 0">Could not load payment history: {{ bphError.message }}</div>
        <div v-else-if="billPayments && billPayments.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Bill</th>
                <th style="text-align:right">Amount</th>
                <th>Source</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in billPayments.slice(0, 15)" :key="i">
                <td style="font-weight:500">{{ p.billName }}</td>
                <td style="text-align:right">{{ currency(p.amountPaid) }}</td>
                <td style="font-size:0.8rem;color:var(--text-muted)">{{ p.sourceBank }} / {{ p.sourceAccount }}</td>
                <td style="font-size:0.8rem">{{ fmtDate(p.paymentDate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state"><p>No bill payments recorded yet.</p></div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
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
  GET_PROJECTION,
  GET_SIMPLEFIN_SYNCED_ACCOUNTS,
  GET_NET_WORTH_HISTORY,
  GET_BILL_PAYMENT_HISTORY,
  GET_DASHBOARD_SUMMARY,
} from '../graphql/queries'
import InsightList from '../components/InsightList.vue'
import BillMatchSuggestions from '../components/BillMatchSuggestions.vue'
import MarkPaidDialog, { type PayableBill } from '../components/MarkPaidDialog.vue'
import { currency, fmtDate, fmtDateShort, frequencyLabel, daysFromNow } from '../utils/format'
import type { FinancialSnapshot, Projection, SimplefinSyncedAccount, NetWorthSnapshot, BillPaymentHistory, DashboardSummary, PeriodBillStatus } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler, Legend)

const { result, loading, error, refetch } = useQuery<{ snapshot: FinancialSnapshot }>(GET_SNAPSHOT)
const { result: projResult, loading: projLoading, error: projError, refetch: refetchProj } = useQuery<{ projection: Projection }>(GET_PROJECTION, { variables: { days: 90 } })
const { result: dashResult, loading: dashLoading, error: dashError, refetch: refetchDash } = useQuery<{ dashboardSummary: DashboardSummary | null }>(
  GET_DASHBOARD_SUMMARY, { fetchPolicy: 'cache-and-network' })
const { result: syncedResult } = useQuery<{ simplefinSyncedAccounts: SimplefinSyncedAccount[] }>(GET_SIMPLEFIN_SYNCED_ACCOUNTS)

const { result: nwResult, loading: nwLoading, error: nwError } = useQuery<{ netWorthHistory: NetWorthSnapshot[] }>(GET_NET_WORTH_HISTORY, { variables: { limit: 90 } })
const { result: bphResult, loading: bphLoading, error: bphError, refetch: refetchBph } = useQuery<{ billPaymentHistory: BillPaymentHistory[] }>(GET_BILL_PAYMENT_HISTORY, { variables: { limit: 20 } })

const snap = computed(() => result.value?.snapshot)
const dash = computed(() => dashResult.value?.dashboardSummary)
const projData = computed(() => projResult.value?.projection)

const payBill = ref<PayableBill | null>(null)

function refreshAll() {
  refetch()
  refetchDash()
  refetchProj()
  refetchBph()
}

const STATUS_ICON: Record<DashboardSummary['status'], string> = { ok: '✅', warning: '⚠️', danger: '🚨' }

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
const netWorthData = computed(() => nwResult.value?.netWorthHistory ?? [])
const billPayments = computed(() => bphResult.value?.billPaymentHistory ?? [])


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

// Net Worth chart
const nwChartData = computed(() => {
  const data = netWorthData.value
  if (!data?.length) return { labels: [], datasets: [] }
  return {
    labels: data.map((s: any) => s.snapshotDate),
    datasets: [
      {
        label: 'Net Worth',
        data: data.map((s: any) => s.netWorth),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16,185,129,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 2,
      },
      {
        label: 'Assets',
        data: data.map((s: any) => s.totalAssets),
        borderColor: '#3b82f6',
        borderDash: [4, 2],
        tension: 0.3,
        pointRadius: 0,
      },
      {
        label: 'Liabilities',
        data: data.map((s: any) => s.totalLiabilities),
        borderColor: '#ef4444',
        borderDash: [4, 2],
        tension: 0.3,
        pointRadius: 0,
      },
    ],
  }
})

const nwChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: true, position: 'top' as const } },
  scales: {
    x: { ticks: { maxTicksLimit: 10, font: { size: 10 } } },
    y: { ticks: { callback: (v: any) => '$' + Number(v).toLocaleString(), font: { size: 10 } } },
  },
}

// Existing projection chart
const chartData = computed(() => {
  if (!projData.value) return { labels: [], datasets: [] }
  const snaps = projData.value.snapshots
  // sample every 3rd day for legibility
  const sampled = snaps.filter((_, i) => i % 3 === 0 || i === snaps.length - 1)
  return {
    labels: sampled.map((s) => s.date),
    datasets: [
      {
        label: 'Total Balance',
        data: sampled.map((s) => s.total),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { maxTicksLimit: 10, font: { size: 10 } } },
    y: {
      ticks: {
        callback: (v: any) => '$' + Number(v).toLocaleString(),
        font: { size: 10 },
      },
    },
  },
}
</script>

<style scoped>
.status-banner { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; border-left: 6px solid var(--border); }
.status-ok { border-left-color: var(--success); background: var(--success-light); }
.status-warning { border-left-color: var(--warning); background: var(--warning-light); }
.status-danger { border-left-color: var(--danger); background: var(--danger-light); }
.status-icon { font-size: 2rem; }
.status-title { font-size: 1.15rem; font-weight: 700; }
.status-detail { font-size: 0.85rem; color: var(--text-muted); margin-top: 0.15rem; }
.safe-amount { font-size: 2.5rem; font-weight: 800; line-height: 1.1; margin-bottom: 0.4rem; }
.hint { font-size: 0.8rem; color: var(--text-muted); }
.hint-warn { color: #92400e; background: var(--warning-light); padding: 0.4rem 0.6rem; border-radius: var(--radius); }
.period-list { list-style: none; margin: 0; padding: 0; }
.period-list li { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
.period-list li:last-child { border-bottom: none; }
@media (max-width: 767px) {
  .status-banner { flex-wrap: wrap; gap: 0.6rem 0.85rem; }
  .status-banner > .btn { flex: 1 1 100%; }
  .status-icon { font-size: 1.6rem; }
  .status-title { font-size: 1.05rem; }
  .safe-amount { font-size: 2.1rem; }
}
.period-paid { opacity: 0.6; }
.period-short, .period-overdue { background: var(--danger-light); margin: 0 -0.5rem; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
.sync-badge {
  font-size: 0.7rem;
  cursor: help;
  opacity: 0.75;
  vertical-align: middle;
}
</style>
