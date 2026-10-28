<template>
  <div>
    <div class="view-header">
      <h2>🔮 What-If Scenarios</h2>
    </div>

    <div class="grid grid-2">
      <!-- Scenario builder -->
      <div class="card">
        <div class="card-header"><span class="card-title">Build a Scenario</span></div>

        <!-- Quick presets -->
        <div style="margin-bottom:1rem">
          <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem;color:var(--text-muted)">Quick Presets</div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
            <button class="btn btn-outline btn-sm" @click="startPreset('lose_job')">Job Loss</button>
            <button class="btn btn-outline btn-sm" @click="startPreset('raise')">10% Raise</button>
            <button class="btn btn-outline btn-sm" @click="applyPreset('new_bill')">New $200 Bill</button>
            <button class="btn btn-outline btn-sm" @click="applyPreset('cut_bills')">Cut Bills 20%</button>
          </div>
          <!-- Inline income picker for Job Loss / Raise presets -->
          <div v-if="presetPending" style="margin-top:0.75rem;padding:0.75rem;border:1px solid var(--primary);border-radius:var(--radius);background:var(--bg-card)">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem">
              {{ presetPending === 'lose_job' ? '💼 Job Loss — select income source' : '📈 10% Raise — select income source' }}
            </div>
            <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
              <button v-for="inc in availableIncome" :key="inc.sourceName"
                class="btn btn-sm" :class="presetPending === 'lose_job' ? 'btn-danger' : 'btn-primary'"
                @click="applyIncomePreset(inc.sourceName)">
                {{ inc.sourceName }} ({{ currency(inc.amount) }})
              </button>
              <button class="btn btn-outline btn-sm" @click="presetPending = null">Cancel</button>
            </div>
          </div>
        </div>

        <!-- Projection days -->
        <div style="margin-bottom:1rem">
          <div class="form-group" style="margin:0;max-width:160px">
            <label style="font-size:0.7rem">Projection Period</label>
            <select v-model.number="scenarioDays">
              <option :value="30">30 days</option>
              <option :value="60">60 days</option>
              <option :value="90">90 days</option>
              <option :value="180">6 months</option>
              <option :value="365">1 year</option>
            </select>
          </div>
        </div>

        <!-- Add new bill -->
        <div style="border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem;margin-bottom:1rem">
          <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem">Add Bill</div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:end">
            <div class="form-group" style="margin:0;flex:1;min-width:120px">
              <label style="font-size:0.7rem">Name</label>
              <input v-model="newBill.name" placeholder="Bill name" />
            </div>
            <div class="form-group" style="margin:0;width:100px">
              <label style="font-size:0.7rem">Amount</label>
              <input v-model.number="newBill.amount" type="number" />
            </div>
            <div class="form-group" style="margin:0;width:80px">
              <label style="font-size:0.7rem">Due Day</label>
              <input v-model.number="newBill.dueDate" type="number" min="1" max="31" />
            </div>
            <button class="btn btn-primary btn-sm" @click="addBill" :disabled="!newBill.name || !newBill.amount">+</button>
          </div>
        </div>

        <!-- Remove payments (unified dropdown: bills, credit, mortgage, HELOC, groups) -->
        <div style="border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem;margin-bottom:1rem">
          <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem">Remove Payments</div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
            <select v-model="removeBillName" style="flex:1">
              <option value="">Select a payment to remove...</option>
              <optgroup v-for="grp in removableGroups" :key="grp.label" :label="grp.label">
                <option v-for="p in grp.items" :key="p.key" :value="p.key">
                  {{ p.icon }} {{ p.label }} ({{ p.detail }})
                </option>
              </optgroup>
            </select>
            <button class="btn btn-danger btn-sm" @click="removeBill" :disabled="!removeBillName">Remove</button>
          </div>
        </div>

        <!-- Adjust income (dropdown) -->
        <div style="border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem;margin-bottom:1rem">
          <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem">Adjust Income</div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:end">
            <div class="form-group" style="margin:0;flex:1;min-width:140px">
              <label style="font-size:0.7rem">Source</label>
              <select v-model="incAdj.name" @change="onIncomeSelected">
                <option value="">Select income source...</option>
                <option v-for="i in availableIncome" :key="i.sourceName" :value="i.sourceName">
                  {{ i.sourceName }} ({{ currency(i.amount) }}/{{ i.frequency }})
                </option>
              </select>
            </div>
            <div class="form-group" style="margin:0;width:120px">
              <label style="font-size:0.7rem">New Amount</label>
              <input v-model.number="incAdj.amount" type="number" step="100" />
            </div>
            <button class="btn btn-primary btn-sm" @click="adjustIncome" :disabled="!incAdj.name">Set</button>
          </div>
        </div>

        <!-- Remove income (dropdown) -->
        <div style="border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem;margin-bottom:1rem">
          <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem">Remove Income</div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
            <select v-model="removeIncomeName" style="flex:1">
              <option value="">Select income to remove...</option>
              <option v-for="i in availableIncome" :key="i.sourceName" :value="i.sourceName">
                {{ i.sourceName }} ({{ currency(i.amount) }})
              </option>
            </select>
            <button class="btn btn-danger btn-sm" @click="removeIncome" :disabled="!removeIncomeName">Remove</button>
          </div>
        </div>

        <!-- Current modifications summary -->
        <div v-if="hasModifications" style="margin-bottom:1rem">
          <div style="font-size:0.8rem;font-weight:600;margin-bottom:0.5rem;color:var(--text-muted)">Modifications</div>
          <div v-for="(b, i) in modifications.add_bills" :key="'add'+i" style="font-size:0.8rem;display:flex;justify-content:space-between;padding:0.25rem 0">
            <span>+ {{ b.bill_name }} ({{ currency(b.amount) }}/mo)</span>
            <button class="btn btn-outline btn-sm" @click="modifications.add_bills.splice(i,1)" style="padding:0 0.35rem;font-size:0.65rem">×</button>
          </div>
          <div v-for="(name, i) in modifications.remove_bills" :key="'rem'+i" style="font-size:0.8rem;display:flex;justify-content:space-between;padding:0.25rem 0;color:var(--danger)">
            <span>- {{ getRemovableLabel(name) }}</span>
            <button class="btn btn-outline btn-sm" @click="modifications.remove_bills.splice(i,1)" style="padding:0 0.35rem;font-size:0.65rem">×</button>
          </div>
          <div v-for="(adj, i) in modifications.adjust_income" :key="'inc'+i" style="font-size:0.8rem;display:flex;justify-content:space-between;padding:0.25rem 0;color:var(--primary)">
            <span>📝 {{ adj.source_name }} → {{ adj.new_amount < 0 ? `+${Math.abs(adj.new_amount)}% raise` : (adj.new_amount === 0 ? '$0 (job loss)' : currency(adj.new_amount)) }}</span>
            <button class="btn btn-outline btn-sm" @click="modifications.adjust_income.splice(i,1)" style="padding:0 0.35rem;font-size:0.65rem">×</button>
          </div>
          <div v-for="(name, i) in modifications.remove_income" :key="'rminc'+i" style="font-size:0.8rem;display:flex;justify-content:space-between;padding:0.25rem 0;color:var(--danger)">
            <span>✕ Remove income: {{ name }}</span>
            <button class="btn btn-outline btn-sm" @click="modifications.remove_income.splice(i,1)" style="padding:0 0.35rem;font-size:0.65rem">×</button>
          </div>
        </div>

        <div style="display:flex;gap:0.5rem">
          <button class="btn btn-primary" @click="runScenario" :disabled="!hasModifications || scenarioLoading">
            {{ scenarioLoading ? 'Calculating...' : 'Run Scenario' }}
          </button>
          <button class="btn btn-outline" @click="resetScenario">Reset</button>
        </div>
      </div>

      <!-- Results -->
      <div>
        <div v-if="scenarioError" class="card" style="margin-bottom:1rem;color:var(--danger)">
          Scenario failed: {{ scenarioError }}
        </div>
        <div v-if="scenarioResult" class="card" style="margin-bottom:1rem">
          <div class="card-header"><span class="card-title">Scenario Results ({{ scenarioDays }}-day projection)</span></div>
          <!-- Plain-language verdict -->
          <div v-if="scenarioResult.changes?.length" :style="`margin:0.5rem 0 1rem;padding:0.75rem 1rem;border-radius:var(--radius);border-left:4px solid ${verdictColor};background:var(--surface-alt)`">
            <div style="font-weight:600;margin-bottom:0.35rem">{{ verdictTitle }}</div>
            <ul style="margin:0;padding-left:1.1rem;font-size:0.85rem;color:var(--text-muted)">
              <li v-for="(c, i) in scenarioResult.changes" :key="i">{{ c }}</li>
            </ul>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th style="text-align:right">Current plan</th>
                  <th style="text-align:right">Scenario</th>
                  <th style="text-align:right">Change</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in outcomeRows" :key="row.label">
                  <td>{{ row.label }}</td>
                  <td style="text-align:right">{{ row.fmt(row.base) }}</td>
                  <td style="text-align:right">{{ row.fmt(row.scen) }}</td>
                  <td style="text-align:right;font-weight:600" :class="changeClass(row)">{{ changeText(row) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="newLatePayments.length" style="margin-top:0.75rem;font-size:0.85rem">
            <div style="font-weight:600;color:var(--danger);margin-bottom:0.25rem">Payments that would be late or missed in this scenario:</div>
            <ul style="margin:0;padding-left:1.1rem">
              <li v-for="(p, i) in newLatePayments" :key="i">{{ fmtDateShort(p.date) }}: {{ p.name }} ({{ currency(p.amount) }})</li>
            </ul>
          </div>
        </div>

        <div v-if="scenarioResult" class="card">
          <div class="card-header"><span class="card-title">Baseline vs Scenario</span></div>
          <div style="height:350px">
            <Line :data="scenarioChartData" :options="scenarioChartOptions" />
          </div>
        </div>

        <div v-else class="card">
          <div class="empty-state">
            <div class="icon">🔮</div>
            <p v-if="scenarioEmpty">The scenario returned no results. Check your modifications and try again.</p>
            <p v-else>Build a scenario and click "Run Scenario" to see the impact.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
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
  Legend,
} from 'chart.js'
import { GET_WHAT_IF_SCENARIO, GET_ALL_BILLS, GET_ALL_INCOME, GET_ALL_BANKS, GET_ALL_BILL_GROUPS } from '../graphql/queries'
import { currency, fmtDateShort } from '../utils/format'
import { apolloClient } from '../graphql/client'
import type { BillItem, IncomeItem, Bank, BillGroup, WhatIfResult, OutcomeSummary } from '../types'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const scenarioDays = ref(90)

// Fetch existing bills, income, banks, and groups for dropdowns
const { result: billsResult } = useQuery<{ allBills: BillItem[] }>(GET_ALL_BILLS)
const { result: incomeResult } = useQuery<{ allIncome: IncomeItem[] }>(GET_ALL_INCOME)
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const { result: groupsResult } = useQuery<{ allBillGroups: BillGroup[] }>(GET_ALL_BILL_GROUPS)

// Account-linked "[Auto] ..." bills are covered by the credit/mortgage/HELOC groups below
const availableBills = computed(() => (billsResult.value?.allBills ?? []).filter(b => !b.isAccountLinked))
const availableIncome = computed(() => incomeResult.value?.allIncome ?? [])

interface RemovablePayment {
  key: string       // prefixed key sent to backend: "MyBill", "credit:Bank:Acct", etc.
  label: string     // display label
  detail: string    // amount / frequency detail
  icon: string      // emoji icon
  group: string     // optgroup label
}

const allRemovablePayments = computed<RemovablePayment[]>(() => {
  const items: RemovablePayment[] = []

  // Regular bills
  for (const b of availableBills.value) {
    items.push({
      key: b.billName,
      label: b.billName,
      detail: `${currency(b.amount)}/${b.frequency}`,
      icon: '📄',
      group: 'Bills',
    })
  }

  // Credit card payments (with balance > 0)
  const banks = banksResult.value?.allBanks ?? []
  for (const bank of banks) {
    for (const cc of (bank.creditAccounts ?? [])) {
      if (cc.balance > 0) {
        items.push({
          key: `credit:${bank.name}:${cc.accountName}`,
          label: `${cc.accountName}`,
          detail: `${currency(cc.balance)} bal · ${currency(cc.minimumPayment || 0)} min`,
          icon: '💳',
          group: 'Credit Cards',
        })
      }
    }

    // Mortgage payments
    for (const m of (bank.mortgageAccounts ?? [])) {
      items.push({
        key: `mortgage:${bank.name}:${m.accountName}`,
        label: `${m.accountName}`,
        detail: `${currency(m.totalMonthlyPayment)}/mo`,
        icon: '🏠',
        group: 'Mortgages',
      })
    }

    // HELOC payments
    for (const h of (bank.helocAccounts ?? [])) {
      if (h.balance > 0) {
        items.push({
          key: `heloc:${bank.name}:${h.accountName}`,
          label: `${h.accountName}`,
          detail: `${currency(h.balance)} bal · ${currency(h.minimumPayment || 0)} min`,
          icon: '🏦',
          group: 'HELOCs',
        })
      }
    }
  }

  // Bill groups
  const groups = groupsResult.value?.allBillGroups ?? []
  for (const g of groups) {
    items.push({
      key: `group:${g.groupName}`,
      label: g.groupName,
      detail: `${currency(g.totalPayment)}/mo · ${g.memberCount} accounts`,
      icon: '📦',
      group: 'Loan Groups',
    })
  }

  return items
})

const removableGroups = computed(() => {
  const groupMap = new Map<string, RemovablePayment[]>()
  for (const p of allRemovablePayments.value) {
    if (!groupMap.has(p.group)) groupMap.set(p.group, [])
    groupMap.get(p.group)!.push(p)
  }
  return Array.from(groupMap.entries()).map(([label, items]) => ({ label, items }))
})

function getRemovableLabel(key: string): string {
  const p = allRemovablePayments.value.find(r => r.key === key)
  if (p) return `${p.icon} ${p.label}`
  if (key.startsWith('__')) return 'Cut all bills 20%'
  return key
}

interface Modifications {
  add_bills: Array<{ bill_name: string; amount: number; due_date: number; frequency: string }>
  remove_bills: string[]
  adjust_income: Array<{ source_name: string; new_amount: number }>
  remove_income: string[]
}

const modifications = reactive<Modifications>({
  add_bills: [],
  remove_bills: [],
  adjust_income: [],
  remove_income: [],
})

const newBill = reactive({ name: '', amount: 0, dueDate: 1 })
const removeBillName = ref('')
const incAdj = reactive({ name: '', amount: 0 })
const removeIncomeName = ref('')
const presetPending = ref<string | null>(null)

const hasModifications = computed(() =>
  modifications.add_bills.length > 0 ||
  modifications.remove_bills.length > 0 ||
  modifications.adjust_income.length > 0 ||
  modifications.remove_income.length > 0
)

function addBill() {
  modifications.add_bills.push({
    bill_name: newBill.name,
    amount: newBill.amount,
    due_date: newBill.dueDate,
    frequency: 'monthly',
  })
  newBill.name = ''
  newBill.amount = 0
  newBill.dueDate = 1
}

function removeBill() {
  if (removeBillName.value && !modifications.remove_bills.includes(removeBillName.value)) {
    modifications.remove_bills.push(removeBillName.value)
    removeBillName.value = ''
  }
}

function onIncomeSelected() {
  const income = availableIncome.value.find(i => i.sourceName === incAdj.name)
  if (income) {
    incAdj.amount = income.amount
  }
}

function adjustIncome() {
  modifications.adjust_income.push({
    source_name: incAdj.name,
    new_amount: incAdj.amount,
  })
  incAdj.name = ''
  incAdj.amount = 0
}

function removeIncome() {
  if (removeIncomeName.value && !modifications.remove_income.includes(removeIncomeName.value)) {
    modifications.remove_income.push(removeIncomeName.value)
    removeIncomeName.value = ''
  }
}

function resetScenario() {
  modifications.add_bills = []
  modifications.remove_bills = []
  modifications.adjust_income = []
  modifications.remove_income = []
  scenarioResult.value = null
  scenarioError.value = ''
  scenarioEmpty.value = false
  presetPending.value = null
}

function startPreset(preset: string) {
  // For income-targeting presets, show the income picker
  if (availableIncome.value.length === 1) {
    // Only one income source — apply directly, no need to pick
    resetScenario()
    const sourceName = availableIncome.value[0].sourceName
    if (preset === 'lose_job') {
      modifications.adjust_income.push({ source_name: sourceName, new_amount: 0 })
    } else if (preset === 'raise') {
      modifications.adjust_income.push({ source_name: sourceName, new_amount: -10 })
    }
    presetPending.value = null
  } else {
    resetScenario()
    presetPending.value = preset
  }
}

function applyIncomePreset(sourceName: string) {
  if (presetPending.value === 'lose_job') {
    modifications.adjust_income.push({ source_name: sourceName, new_amount: 0 })
  } else if (presetPending.value === 'raise') {
    modifications.adjust_income.push({ source_name: sourceName, new_amount: -10 })
  }
  presetPending.value = null
}

function applyPreset(preset: string) {
  resetScenario()
  switch (preset) {
    case 'new_bill':
      modifications.add_bills.push({ bill_name: 'New Expense', amount: 200, due_date: 15, frequency: 'monthly' })
      break
    case 'cut_bills':
      modifications.remove_bills.push('__CUT_20%__')
      break
  }
}

// Scenario query
const scenarioResult = ref<WhatIfResult | null>(null)
const scenarioLoading = ref(false)
const scenarioError = ref('')
const scenarioEmpty = ref(false)

async function runScenario() {
  scenarioLoading.value = true
  scenarioError.value = ''
  scenarioEmpty.value = false
  try {
    const res = await apolloClient.query<{ whatIfScenario: WhatIfResult | null }>({
      query: GET_WHAT_IF_SCENARIO,
      variables: {
        modifications: JSON.stringify(modifications),
        days: scenarioDays.value,
      },
      fetchPolicy: 'network-only',
    })
    const data = res.data?.whatIfScenario ?? null
    scenarioResult.value = data
    if (!data) scenarioEmpty.value = true
  } catch (e: unknown) {
    scenarioResult.value = null
    scenarioError.value = e instanceof Error ? e.message : String(e)
  } finally {
    scenarioLoading.value = false
  }
}

// ── Plain-language outcome comparison ──
interface OutcomeRow {
  label: string
  base: number
  scen: number
  /** +1 when higher is better, -1 when lower is better */
  better: 1 | -1
  fmt: (v: number) => string
}

const overall = (s: OutcomeSummary) => s.netPosition

const outcomeRows = computed<OutcomeRow[]>(() => {
  const r = scenarioResult.value
  if (!r?.baseline || !r?.scenario) return []
  const b = r.baseline, s = r.scenario
  return [
    { label: 'Late or missed payments', base: b.latePayments.length, scen: s.latePayments.length, better: -1, fmt: v => String(v) },
    { label: 'Lowest checking balance', base: b.lowestChecking ?? 0, scen: s.lowestChecking ?? 0, better: 1, fmt: currency },
    { label: 'Cash at the end', base: b.endingCash, scen: s.endingCash, better: 1, fmt: currency },
    { label: 'Debt at the end', base: b.endingDebt, scen: s.endingDebt, better: -1, fmt: currency },
    { label: 'Interest charged', base: b.interestCharged, scen: s.interestCharged, better: -1, fmt: currency },
    { label: 'Late & overdraft fees', base: b.fees, scen: s.fees, better: -1, fmt: currency },
    { label: 'Overall (cash − debt)', base: overall(b), scen: overall(s), better: 1, fmt: currency },
  ]
})

function changeText(row: OutcomeRow): string {
  const d = row.scen - row.base
  if (Math.abs(d) < 0.005) return 'same'
  return `${d > 0 ? '+' : '−'}${row.fmt(Math.abs(d))}`
}

function changeClass(row: OutcomeRow): string {
  const d = (row.scen - row.base) * row.better
  if (Math.abs(d) < 0.005) return 'neutral'
  return d > 0 ? 'positive' : 'negative'
}

const newLatePayments = computed(() => {
  const r = scenarioResult.value
  if (!r?.scenario) return []
  const before = new Set((r.baseline?.latePayments ?? []).map(p => `${p.date}|${p.name}`))
  return r.scenario.latePayments.filter(p => !before.has(`${p.date}|${p.name}`))
})

const verdictColor = computed(() => {
  const r = scenarioResult.value
  if (!r?.scenario || !r.baseline) return 'var(--border)'
  if (newLatePayments.value.length || (r.scenario.lowestChecking ?? 0) < 0) return 'var(--danger)'
  return overall(r.scenario) >= overall(r.baseline) ? 'var(--success)' : 'var(--warning)'
})

const verdictTitle = computed(() => {
  const r = scenarioResult.value
  if (!r?.scenario || !r.baseline) return ''
  if (newLatePayments.value.length) return `⚠️ ${newLatePayments.value.length} bill(s) couldn't be paid on time in this scenario`
  if ((r.scenario.lowestChecking ?? 0) < 0) return '⚠️ Checking would be overdrawn in this scenario'
  const d = overall(r.scenario) - overall(r.baseline)
  if (Math.abs(d) < 0.01) return 'No meaningful change'
  return d > 0 ? `✅ You'd be ${currency(d)} better off` : `Every bill still gets paid, but you'd be ${currency(-d)} worse off`
})

const scenarioChartData = computed(() => {
  if (!scenarioResult.value) return { labels: [], datasets: [] }

  // Snapshots arrive as a JSON string (or already-parsed array); tolerate double-encoding
  const parseSnaps = (s: unknown): any[] => {
    let v: unknown = s
    for (let i = 0; i < 2 && typeof v === 'string'; i++) {
      try { v = JSON.parse(v) } catch { return [] }
    }
    return Array.isArray(v) ? v : []
  }

  const baseline = parseSnaps(scenarioResult.value.baselineSnapshots)
  const scenario = parseSnaps(scenarioResult.value.scenarioSnapshots)

  const step = Math.max(1, Math.floor(baseline.length / 60))
  const bSampled = baseline.filter((_: any, i: number) => i % step === 0 || i === baseline.length - 1)
  const sSampled = scenario.filter((_: any, i: number) => i % step === 0 || i === scenario.length - 1)

  return {
    labels: bSampled.map((s: any) => s.date),
    datasets: [
      {
        label: 'Baseline',
        data: bSampled.map((s: any) => {
          const bals = typeof s.balances === 'string' ? JSON.parse(s.balances) : s.balances
          return Object.values(bals as Record<string, number>).reduce((a, b) => a + b, 0)
        }),
        borderColor: '#3b82f6',
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: 'Scenario',
        data: sSampled.map((s: any) => {
          const bals = typeof s.balances === 'string' ? JSON.parse(s.balances) : s.balances
          return Object.values(bals as Record<string, number>).reduce((a, b) => a + b, 0)
        }),
        borderColor: '#f59e0b',
        borderDash: [6, 3],
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  }
})

const scenarioChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: true, position: 'top' as const } },
  scales: {
    x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } },
    y: { ticks: { callback: (v: any) => '$' + Number(v).toLocaleString(), font: { size: 10 } } },
  },
}
</script>

