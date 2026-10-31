<template>
  <div>
    <div class="view-header">
      <h2>Net Worth</h2>
      <button class="btn btn-primary btn-sm" @click="openAsset()">+ Asset</button>
    </div>

    <div v-if="loading && !nw" class="loading">Loading...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="nw">
      <div class="grid grid-3" style="margin-bottom:1.5rem">
        <div class="stat-card">
          <div class="stat-label">Net worth</div>
          <div class="stat-value" :class="nw.netWorth >= 0 ? 'positive' : 'negative'">{{ currency(nw.netWorth) }}</div>
          <div v-if="change" class="sub">
            <span :class="change.amount >= 0 ? 'positive' : 'negative'">{{ change.amount >= 0 ? '+' : '−' }}{{ currency(Math.abs(change.amount)) }}</span>
            since {{ fmtDate(change.since) }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">What you own</div>
          <div class="stat-value">{{ currency(nw.totalAssets) }}</div>
          <div class="sub">{{ currency(nw.cash) }} in bank accounts</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">What you owe</div>
          <div class="stat-value negative">{{ currency(nw.totalDebt) }}</div>
          <div class="sub">{{ nw.debts.map(d => d.kind).join(', ') || 'debt-free' }}</div>
        </div>
      </div>

      <div class="grid grid-2" style="margin-bottom:1.5rem">
        <div class="card">
          <div class="card-header"><span class="card-title">Assets</span></div>
          <div class="breakdown">
            <div class="bd-row"><span>Bank accounts</span><span>{{ currency(nw.cash) }}</span></div>
            <div v-for="k in nw.assetsByKind" :key="k.kind" class="bd-row"><span>{{ k.kind }}</span><span>{{ currency(k.value) }}</span></div>
            <div class="bd-row total"><span>Total</span><span>{{ currency(nw.totalAssets) }}</span></div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Debts</span></div>
          <div class="breakdown">
            <div v-for="d in nw.debts" :key="d.kind" class="bd-row"><span>{{ d.kind }}</span><span>{{ currency(d.value) }}</span></div>
            <div v-if="!nw.debts.length" class="bd-row muted"><span>No debts 🎉</span><span></span></div>
            <div class="bd-row total"><span>Total</span><span>{{ currency(nw.totalDebt) }}</span></div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Your assets</span></div>
        <p class="hint">
          Things you own besides bank accounts — a car, investment or retirement accounts, property, valuables.
          Update the value now and then; each change is kept so you can see how it moves. Link a loan to see your equity.
        </p>
        <div v-if="!nw.assets.length && !nw.homes.length" class="empty-state" style="padding:1.25rem">
          <div class="icon">🚗</div>
          <p>No assets yet. Add your car, 401(k), brokerage account or home to see your full net worth.</p>
        </div>
        <div v-else class="table-wrap">
          <table>
            <thead><tr><th>Asset</th><th>Type</th><th style="text-align:right">Value</th><th style="text-align:right">Loan</th><th style="text-align:right">Equity</th><th></th></tr></thead>
            <tbody>
              <tr v-for="a in nw.assets" :key="a.id">
                <td>
                  <div style="font-weight:500">{{ a.name }}</div>
                  <div class="sub">{{ [a.notes, a.updated ? `updated ${fmtDate(a.updated)}` : ''].filter(Boolean).join(' · ') }}</div>
                </td>
                <td class="muted">{{ a.kindLabel }}</td>
                <td style="text-align:right;font-weight:600">{{ currency(a.value) }}</td>
                <td style="text-align:right" :title="a.linkedAccount ? `${a.linkedBank} / ${a.linkedAccount}` : ''">
                  {{ a.loanBalance != null ? currency(a.loanBalance) : '—' }}
                </td>
                <td style="text-align:right" :class="a.equity >= 0 ? 'positive' : 'negative'">{{ currency(a.equity) }}</td>
                <td style="text-align:right;white-space:nowrap">
                  <button class="btn btn-outline btn-sm" @click="showHistory(a)">History</button>
                  <button class="btn btn-outline btn-sm" style="margin-left:0.35rem" @click="openAsset(a)">Edit</button>
                  <button class="btn btn-danger btn-sm" style="margin-left:0.35rem" @click="remove(a)">Delete</button>
                </td>
              </tr>
              <tr v-for="h in nw.homes" :key="h.bank + h.name">
                <td>
                  <div style="font-weight:500">{{ h.name }}</div>
                  <div class="sub">Market value from the mortgage on the Accounts page</div>
                </td>
                <td class="muted">Property</td>
                <td style="text-align:right;font-weight:600">{{ currency(h.value) }}</td>
                <td style="text-align:right">{{ currency(h.owed) }}</td>
                <td style="text-align:right" :class="h.value - h.owed >= 0 ? 'positive' : 'negative'">{{ currency(h.value - h.owed) }}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Net worth over time</span></div>
        <div v-if="history.length < 2" class="muted" style="font-size:0.85rem">
          A snapshot is recorded every day the app runs — the chart appears after a couple of days.
        </div>
        <div v-else style="height:260px"><Line :data="historyChart" :options="lineOptions" /></div>
      </div>
    </template>

    <!-- Asset modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ form.id ? 'Edit Asset' : 'Add Asset' }}</h3>
        <div class="grid grid-2">
          <div class="form-group"><label>Name</label><input v-model="form.name" placeholder="e.g. 2019 Civic, Fidelity 401(k)" /></div>
          <div class="form-group">
            <label>Type</label>
            <select v-model="form.kind">
              <option v-for="k in kinds" :key="k.kind" :value="k.kind">{{ k.label }}</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>Current value</label>
          <input v-model.number="form.value" type="number" min="0" step="100" />
          <span class="hint">{{ valueHint }}</span>
        </div>
        <div class="form-group">
          <label>Loan against it (optional)</label>
          <select v-model="form.loan">
            <option value="">None</option>
            <option v-for="l in loanOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
          </select>
          <span class="hint">e.g. the car loan or mortgage, to show equity. It's still counted once in your debts.</span>
        </div>
        <div class="form-group"><label>Notes</label><input v-model="form.notes" /></div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showForm = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!form.name || form.value === '' || form.value < 0" @click="save">Save</button>
        </div>
      </div>
    </div>

    <!-- History modal -->
    <div v-if="historyFor" class="modal-overlay" @click.self="historyFor = null">
      <div class="modal">
        <h3>{{ historyFor.name }} — value history</h3>
        <div v-if="assetHistory.length > 1" style="height:200px;margin-bottom:0.75rem"><Line :data="assetChart" :options="lineOptions" /></div>
        <div class="table-wrap" style="max-height:240px;overflow:auto">
          <table>
            <thead><tr><th>Date</th><th style="text-align:right">Value</th></tr></thead>
            <tbody>
              <tr v-for="p in [...assetHistory].reverse()" :key="p.date">
                <td>{{ fmtDate(p.date) }}</td><td style="text-align:right">{{ currency(p.value) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-actions"><button class="btn btn-outline" @click="historyFor = null">Close</button></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler, type ChartOptions,
} from 'chart.js'
import { GET_NET_WORTH, SAVE_ASSET, DELETE_ASSET, GET_ASSET_HISTORY } from '../graphql/planning'
import { GET_ALL_BANKS } from '../graphql/queries'
import { apolloClient } from '../graphql/client'
import { runMutation } from '../utils/mutation'
import { currency, fmtDate } from '../utils/format'
import type { Asset, Bank, MutationPayload, NetWorthBreakdown, NetWorthSnapshot } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler)

const { result, loading, error, refetch } = useQuery<{
  netWorthBreakdown: NetWorthBreakdown; assetKinds: { kind: string; label: string }[]; netWorthHistory: NetWorthSnapshot[]
}>(GET_NET_WORTH, { fetchPolicy: 'cache-and-network' })
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)

const nw = computed(() => result.value?.netWorthBreakdown)
const kinds = computed(() => result.value?.assetKinds ?? [])
const history = computed(() => [...(result.value?.netWorthHistory ?? [])].sort((a, b) => a.snapshotDate.localeCompare(b.snapshotDate)))
const change = computed(() => {
  const h = history.value
  return h.length > 1 ? { amount: h[h.length - 1].netWorth - h[0].netWorth, since: h[0].snapshotDate } : null
})

const loanOptions = computed(() => (banksResult.value?.allBanks ?? []).flatMap(b => [
  ...b.creditAccounts.map(a => ({ value: `${b.name}:${a.accountName}`, label: `${b.name} / ${a.accountName} (${currency(a.balance)} owed)` })),
  ...b.mortgageAccounts.map(a => ({ value: `${b.name}:${a.accountName}`, label: `${b.name} / ${a.accountName} (mortgage)` })),
  ...b.helocAccounts.map(a => ({ value: `${b.name}:${a.accountName}`, label: `${b.name} / ${a.accountName} (HELOC)` })),
]))

const VALUE_HINTS: Record<string, string> = {
  vehicle: 'Private-party value from Kelley Blue Book or Edmunds is a good estimate.',
  investment: 'The balance on your brokerage statement.',
  retirement: 'Your 401(k)/IRA balance (before taxes).',
  property: 'An estimate like Zillow or a recent appraisal. If you track the mortgage, link it below.',
}
const valueHint = computed(() => VALUE_HINTS[form.kind] ?? '')

// ── Add / edit ──
const showForm = ref(false)
const form = reactive({ id: null as number | null, name: '', kind: 'vehicle', value: '' as number | '', notes: '', loan: '' })
const { mutate: saveM } = useMutation<{ saveAsset: MutationPayload }>(SAVE_ASSET)
const { mutate: deleteM } = useMutation<{ deleteAsset: MutationPayload }>(DELETE_ASSET)

function openAsset(a?: Asset) {
  Object.assign(form, a
    ? { id: a.id, name: a.name, kind: a.kind, value: a.value, notes: a.notes, loan: a.linkedBank ? `${a.linkedBank}:${a.linkedAccount}` : '' }
    : { id: null, name: '', kind: 'vehicle', value: '', notes: '', loan: '' })
  showForm.value = true
}

async function save() {
  const i = form.loan.indexOf(':')
  const [linkedBank, linkedAccount] = i > 0 ? [form.loan.slice(0, i), form.loan.slice(i + 1)] : ['', '']
  const res = await runMutation(() => saveM({ variables: {
    id: form.id, name: form.name.trim(), kind: form.kind, value: Number(form.value), notes: form.notes,
    linkedBank, linkedAccount,
  } }), 'saveAsset')
  if (res) {
    showForm.value = false
    refetch()
  }
}

async function remove(a: Asset) {
  if (!confirm(`Delete "${a.name}" and its value history?`)) return
  const res = await runMutation(() => deleteM({ variables: { id: a.id } }), 'deleteAsset')
  if (res) refetch()
}

// ── History ──
const historyFor = ref<Asset | null>(null)
const assetHistory = ref<{ date: string; value: number }[]>([])

async function showHistory(a: Asset) {
  const res = await apolloClient.query<{ assetHistory: { date: string; value: number }[] }>({
    query: GET_ASSET_HISTORY, variables: { id: a.id },
  })
  assetHistory.value = res.data?.assetHistory ?? []
  historyFor.value = a
}

function line(labels: string[], data: number[]) {
  return {
    labels,
    datasets: [{ data, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.12)', fill: true, tension: 0.25,
      pointRadius: data.length > 30 ? 0 : 3 }],
  }
}
const historyChart = computed(() => line(history.value.map(s => fmtDate(s.snapshotDate)), history.value.map(s => s.netWorth)))
const assetChart = computed(() => line(assetHistory.value.map(p => fmtDate(p.date)), assetHistory.value.map(p => p.value)))

const lineOptions: ChartOptions<'line'> = {
  responsive: true, maintainAspectRatio: false,
  scales: { y: { ticks: { callback: (v: number | string) => currency(Number(v)) } } },
  plugins: { legend: { display: false } },
}
</script>

<style scoped>
.sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem; }
.muted { color: var(--text-muted); }
.hint { display: block; font-size: 0.8rem; color: var(--text-muted); margin: 0 0 0.75rem; }
.form-group .hint { margin: 0.25rem 0 0; }
.breakdown { font-size: 0.92rem; }
.bd-row { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }
.bd-row.total { font-weight: 600; border-bottom: none; }
.card + .card { margin-top: 1.5rem; }
.grid > .card { margin-top: 0; }
</style>
