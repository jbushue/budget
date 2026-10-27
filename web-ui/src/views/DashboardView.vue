<template>
  <div>
    <div class="view-header">
      <h2>Dashboard</h2>
      <button class="btn btn-outline btn-sm" @click="refetch()">Refresh</button>
    </div>

    <div v-if="loading" class="loading">Loading financial snapshot...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">Error: {{ error.message }}</div>

    <template v-else-if="snap">
      <!-- Discretionary Funds banner -->
      <div v-if="safeData" class="card" :style="`margin-bottom:1.5rem;border-left:4px solid ${safeColor}`">
        <div style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap">
          <div>
            <div style="font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em">Discretionary Funds</div>
            <div style="font-size:1.75rem;font-weight:700" :style="`color:${safeColor}`">{{ currency(safeData.safeToSpend) }}</div>
          </div>
          <div style="font-size:0.8rem;color:var(--text-muted);display:flex;gap:1.25rem;flex-wrap:wrap">
            <span>💰 Checking: {{ currency(safeData.totalChecking) }}</span>
            <span v-if="safeData.upcomingIncome > 0" class="positive">📥 Incoming: +{{ currency(safeData.upcomingIncome) }}</span>
            <span>📋 Committed: -{{ currency(safeData.committedBills) }}</span>
            <span>📅 Through: {{ fmtDate(safeData.horizonDate) }}</span>
          </div>
        </div>
      </div>

      <!-- Top recommendations from the payment analyzer -->
      <div v-if="topInsights.length" class="card" style="margin-bottom:1.5rem">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
          <span class="card-title">🧭 What to do next</span>
          <router-link to="/optimizer" style="font-size:0.8rem">See the full payment plan →</router-link>
        </div>
        <div v-if="insightsData" style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.6rem">{{ insightsData.headline }}</div>
        <InsightList :items="topInsights" compact />
      </div>

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
import { computed } from 'vue'
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
  GET_SAFE_TO_SPEND,
  GET_NET_WORTH_HISTORY,
  GET_BILL_PAYMENT_HISTORY,
  GET_PAYMENT_INSIGHTS,
} from '../graphql/queries'
import InsightList from '../components/InsightList.vue'
import { currency, fmtDate, frequencyLabel } from '../utils/format'
import type { FinancialSnapshot, Projection, SimplefinSyncedAccount, SafeToSpend, NetWorthSnapshot, BillPaymentHistory, PaymentInsights } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler, Legend)

const { result, loading, error, refetch } = useQuery<{ snapshot: FinancialSnapshot }>(GET_SNAPSHOT)
const { result: projResult, loading: projLoading, error: projError } = useQuery<{ projection: Projection }>(GET_PROJECTION, { variables: { days: 90 } })
const { result: syncedResult } = useQuery<{ simplefinSyncedAccounts: SimplefinSyncedAccount[] }>(GET_SIMPLEFIN_SYNCED_ACCOUNTS)

// New enhancement queries
const { result: safeResult } = useQuery<{ safeToSpend: SafeToSpend | null }>(GET_SAFE_TO_SPEND)
const { result: nwResult, loading: nwLoading, error: nwError } = useQuery<{ netWorthHistory: NetWorthSnapshot[] }>(GET_NET_WORTH_HISTORY, { variables: { limit: 90 } })
const { result: bphResult, loading: bphLoading, error: bphError } = useQuery<{ billPaymentHistory: BillPaymentHistory[] }>(GET_BILL_PAYMENT_HISTORY, { variables: { limit: 20 } })

const { result: insightsResult } = useQuery<{ paymentInsights: PaymentInsights | null }>(GET_PAYMENT_INSIGHTS, { variables: { days: 30 } })

const snap = computed(() => result.value?.snapshot)
const insightsData = computed(() => insightsResult.value?.paymentInsights)
// The three most important items (the list is already ranked by the backend)
const topInsights = computed(() => (insightsData.value?.insights ?? []).slice(0, 3))
const projData = computed(() => projResult.value?.projection)
const safeData = computed(() => safeResult.value?.safeToSpend)
const netWorthData = computed(() => nwResult.value?.netWorthHistory ?? [])
const billPayments = computed(() => bphResult.value?.billPaymentHistory ?? [])

const safeColor = computed(() => {
  if (!safeData.value) return 'var(--text-muted)'
  const val = safeData.value.safeToSpend
  if (val >= 500) return 'var(--success)'
  if (val >= 100) return 'var(--warning)'
  return 'var(--danger)'
})

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
.sync-badge {
  font-size: 0.7rem;
  cursor: help;
  opacity: 0.75;
  vertical-align: middle;
}
</style>
