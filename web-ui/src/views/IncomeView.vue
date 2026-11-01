<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Income</h2>
        <p class="view-sub">Paychecks and other money coming in, and where it lands.</p>
      </div>
      <button class="btn btn-primary" @click="openCreate()"><Icon name="plus" :size="16" /> Add income</button>
    </div>

    <div v-if="loading" class="loading">Loading income sources...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else>
      <div v-if="incomes.length === 0" class="empty-state">
        <div class="icon"><Icon name="income" :size="26" /></div>
        <p>No income sources yet. Add your paycheck to get started.</p>
      </div>

      <!-- Income summary -->
      <div v-if="incomes.length" class="grid grid-3" style="margin-bottom:1.5rem">
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(totalMonthly) }}</div>
          <div class="stat-label">Income per month</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(totalMonthly * 12) }}</div>
          <div class="stat-label">Income per year</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{{ incomes.length }}</div>
          <div class="stat-label">Sources</div>
        </div>
      </div>

      <div v-if="incomes.length" class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Frequency</th>
                <th>Pay dates</th>
                <th>Next payday</th>
                <th style="text-align:right">Amount</th>
                <th style="text-align:right">Per month</th>
                <th>Deposits to</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="inc in incomes" :key="inc.id">
                <td style="font-weight:500">{{ inc.sourceName }}</td>
                <td><span class="badge">{{ frequencyLabel(inc.frequency) }}</span></td>
                <td>
                  <span v-if="!usesDayOfMonth(inc.frequency) && inc.startDate">
                    from {{ fmtDate(inc.startDate) }}
                  </span>
                  <span v-else-if="inc.payDates && inc.payDates.length">
                    {{ inc.payDates.join(', ') }}
                  </span>
                  <span v-else style="color:var(--text-muted)">-</span>
                </td>
                <td>{{ fmtDate(inc.nextPayDate) }}</td>
                <td style="text-align:right;font-weight:600" class="positive">{{ currency(inc.amount) }}</td>
                <td style="text-align:right">{{ currency(estimatedMonthly(inc)) }}</td>
                <td style="font-size:0.8rem;color:var(--text-muted)">
                  <template v-if="parseDist(inc.distribution)">
                    <div v-for="(val, acct) in parseDist(inc.distribution)" :key="acct">
                      <strong>{{ acct }}:</strong> {{ distLabel(inc, String(acct), val as number | null) }}
                    </div>
                  </template>
                  <span v-else>Primary account</span>
                </td>
                <td style="text-align:right;white-space:nowrap">
                  <RowMenu :items="[
                    { label: 'Edit income', icon: 'pencil', action: () => openEdit(inc) },
                    { label: 'Split between accounts', icon: 'accounts', action: () => openDistEdit(inc) },
                    { label: 'Delete income', icon: 'trash', danger: true, divider: true, action: () => deleteIncome(inc.sourceName) },
                  ]" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>

    <!-- Create / Edit Income Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3>{{ editMode ? 'Edit income' : 'Add income' }}</h3>
        <div class="form-group">
          <label>Name</label>
          <input v-model="form.sourceName" placeholder="e.g. Primary Job" :disabled="editMode" />
        </div>
        <div class="form-group">
          <label>Amount (per pay period)</label>
          <input v-model.number="form.amount" type="number" step="0.01" />
        </div>
        <div class="form-group">
          <label>Frequency</label>
          <select v-model="form.frequency">
            <option value="monthly">Monthly</option>
            <option value="semimonthly">Semi-monthly</option>
            <option value="biweekly">Bi-weekly</option>
            <option value="weekly">Weekly</option>
            <option value="bimonthly">Bi-monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="yearly">Yearly</option>
            <option value="once">One-time</option>
          </select>
        </div>
        <template v-if="usesDayOfMonth(form.frequency)">
          <div class="form-group">
            <label>{{ form.frequency === 'semimonthly' ? 'First Pay Day (day of month, 1-31)' : 'Pay Day (day of month, 1-31)' }}</label>
            <input v-model.number="form.payDate1" type="number" min="1" max="31" />
          </div>
          <div v-if="form.frequency === 'semimonthly'" class="form-group">
            <label>Second pay day (day of month, 1-31)</label>
            <input v-model.number="form.payDate2" type="number" min="1" max="31" />
          </div>
        </template>
        <div v-else class="form-group">
          <label>{{ form.frequency === 'once' ? 'Pay Date' : 'First Pay Date' }} (optional)</label>
          <input v-model="form.startDate" type="date" />
          <small style="color:var(--text-muted)">
            Anchor for the {{ frequencyLabel(form.frequency).toLowerCase() }} schedule; later pay dates are counted from this date.
          </small>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showModal = false">Cancel</button>
          <button class="btn btn-primary" @click="saveIncome" :disabled="!form.sourceName || !form.amount">
            {{ editMode ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Edit Distribution Modal -->
    <div v-if="showDistModal" class="modal-overlay" @click.self="showDistModal = false">
      <div class="modal" style="max-width:560px">
        <h3>Split “{{ distForm.sourceName }}” between accounts</h3>
        <div class="segmented" style="margin-bottom:0.75rem" role="radiogroup" aria-label="Split by">
          <button :class="{ active: distForm.mode === 'fixed' }" role="radio" :aria-checked="distForm.mode === 'fixed'" @click="setDistMode('fixed')">Dollar amounts</button>
          <button :class="{ active: distForm.mode === 'percent' }" role="radio" :aria-checked="distForm.mode === 'percent'" @click="setDistMode('percent')">Percentages</button>
        </div>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          {{ distForm.mode === 'fixed' ? 'Send a set amount' : 'Send a share of each paycheck' }} to each account.
          Leave one account blank to get whatever is left.
        </p>
        <div v-for="(entry, idx) in distForm.entries" :key="idx" style="display:flex;gap:0.5rem;margin-bottom:0.5rem;align-items:center">
          <select v-model="entry.bank" style="flex:1" @change="entry.account = ''">
            <option value="">Select bank...</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
          <select v-model="entry.account" style="flex:1.5" :disabled="!entry.bank">
            <option value="">Select account...</option>
            <option v-for="acc in depositAccountsForBank(entry.bank)" :key="acc.name" :value="acc.name">{{ acc.name }} ({{ acc.type }})</option>
          </select>
          <div class="amt-wrap" style="flex:0.8">
            <input v-model.number="entry.amount" type="number" :step="distForm.mode === 'percent' ? 1 : 0.01" min="0"
                   :max="distForm.mode === 'percent' ? 100 : undefined" :placeholder="distForm.mode === 'percent' ? '% (blank = rest)' : 'Amount (blank = rest)'" />
            <span v-if="distForm.mode === 'percent'" class="amt-suffix">%</span>
          </div>
          <button class="btn btn-danger btn-sm" @click="distForm.entries.splice(idx, 1)" style="padding:0.3rem 0.5rem">&times;</button>
        </div>
        <p v-if="distPreview" class="muted" style="font-size:0.82rem;margin:0.25rem 0 0.75rem">{{ distPreview }}</p>
        <button class="btn btn-outline btn-sm" @click="distForm.entries.push({ bank: '', account: '', amount: null })" style="margin-bottom:1rem"><Icon name="plus" :size="16" /> Add account</button>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showDistModal = false">Cancel</button>
          <button class="btn btn-primary" @click="saveDist">Save split</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onRouteAction } from '../utils/routeAction'
import RowMenu from '../components/RowMenu.vue'
import Icon from '../components/Icon.vue'
import { ref, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_ALL_INCOME, GET_ALL_BANKS, CREATE_INCOME_SOURCE, UPDATE_INCOME, DELETE_INCOME } from '../graphql/queries'
import { currency, fmtDate, frequencyLabel } from '../utils/format'
import { runMutation } from '../utils/mutation'
import type { IncomeItem, Bank, MutationPayload } from '../types'
import { ask, notify } from '../utils/dialog'

const { result, loading, error, refetch } = useQuery<{ allIncome: IncomeItem[] }>(GET_ALL_INCOME)
const incomes = computed(() => result.value?.allIncome ?? [])

// Fetch banks for dropdowns
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const banks = computed(() => banksResult.value?.allBanks ?? [])

/** Checking/savings accounts for a given bank name (income can only be deposited there) */
function depositAccountsForBank(bankName: string): { name: string; type: string }[] {
  if (!bankName) return []
  const bank = banks.value.find(b => b.name === bankName)
  if (!bank) return []
  return bank.bankAccounts
    .filter(acc => acc.accountType === 'checking' || acc.accountType === 'savings')
    .map(acc => ({ name: acc.accountName, type: acc.accountType }))
}

/** Frequencies scheduled by day-of-month; the rest are anchored on a first pay date. */
function usesDayOfMonth(freq: string): boolean {
  return freq === 'monthly' || freq === 'semimonthly'
}

function parseDist(dist: any): Record<string, number | null> | null {
  if (!dist) return null
  if (typeof dist === 'string') {
    try {
      const parsed = JSON.parse(dist)
      if (parsed && typeof parsed === 'object' && Object.keys(parsed).length > 0) return parsed
      return null
    } catch { return null }
  }
  if (typeof dist === 'object' && Object.keys(dist).length > 0) return dist
  return null
}

function estimatedMonthly(inc: IncomeItem): number {
  const mult: Record<string, number> = {
    monthly: 1, semimonthly: 2, biweekly: 2.17, weekly: 4.33,
    bimonthly: 0.5, quarterly: 0.33, yearly: 0.083, once: 0,
  }
  return inc.amount * (mult[inc.frequency] ?? 1)
}

const totalMonthly = computed(() => incomes.value.reduce((s, i) => s + estimatedMonthly(i), 0))

const showModal = ref(false)
const editMode = ref(false)
const form = ref({ sourceName: '', amount: 0, frequency: 'monthly', payDate1: 1, payDate2: 15, startDate: '' })

function openCreate() {
  editMode.value = false
  form.value = { sourceName: '', amount: 0, frequency: 'monthly', payDate1: 1, payDate2: 15, startDate: '' }
  showModal.value = true
}

onRouteAction({ add: () => openCreate() })

function openEdit(inc: IncomeItem) {
  editMode.value = true
  form.value = {
    sourceName: inc.sourceName,
    amount: inc.amount,
    frequency: inc.frequency,
    payDate1: inc.payDates?.[0] ?? 1,
    payDate2: inc.payDates?.[1] ?? 15,
    startDate: inc.startDate || '',
  }
  showModal.value = true
}

const { mutate: doCreate } = useMutation<{ createIncomeSource: MutationPayload }>(CREATE_INCOME_SOURCE)
const { mutate: doUpdate } = useMutation<{ updateIncome: MutationPayload }>(UPDATE_INCOME)
const { mutate: doDelete } = useMutation<{ deleteIncome: MutationPayload }>(DELETE_INCOME)

async function saveIncome() {
  const f = form.value
  const byDay = usesDayOfMonth(f.frequency)
  const startDate = !byDay && f.startDate ? f.startDate : null
  // Day-of-month schedules use payDates; anchored schedules keep a day-of-month
  // derived from the first pay date (if given) for backwards compatibility.
  const payDates = f.frequency === 'semimonthly'
    ? [f.payDate1, f.payDate2]
    : byDay
      ? [f.payDate1]
      : [startDate ? Number(startDate.slice(8, 10)) : f.payDate1]

  const vars = {
    sourceName: f.sourceName,
    amount: f.amount,
    frequency: f.frequency,
    payDates,
    startDate,
  }
  const ok = editMode.value
    ? await runMutation(() => doUpdate({ variables: vars }), 'updateIncome', { failMessage: 'Failed to update income source' })
    : await runMutation(() => doCreate({ variables: vars }), 'createIncomeSource', { failMessage: 'Failed to create income source' })
  if (!ok) return
  showModal.value = false
  refetch()
}

async function deleteIncome(name: string) {
  if (!(await ask(`Delete the income source "${name}"?`, { title: 'Delete income', danger: true }))) return
  const ok = await runMutation(() => doDelete({ variables: { sourceName: name }}), 'deleteIncome', { failMessage: 'Failed to delete income source' })
  if (ok) refetch()
}

// ── Edit Distribution
const showDistModal = ref(false)
const distForm = ref<{ sourceName: string; paycheck: number; mode: 'fixed' | 'percent'; entries: { bank: string; account: string; amount: number | null }[] }>({ sourceName: '', paycheck: 0, mode: 'fixed', entries: [] })

/** The saved split with each entry's type ("percentage" values are stored as 0–1). */
function distDetail(inc: IncomeItem): Record<string, { value: number | null; type: string }> | null {
  const raw = inc.distributionDetail
  if (!raw) return null
  try { return typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return null }
}

function distLabel(inc: IncomeItem, account: string, val: number | null) {
  if (val === null) return 'the rest'
  if (distDetail(inc)?.[account]?.type === 'percentage') return `${Math.round(val * 1000) / 10}% (${currency(inc.amount * val)})`
  return currency(val)
}

function setDistMode(mode: 'fixed' | 'percent') {
  if (distForm.value.mode === mode) return
  const pay = distForm.value.paycheck || 1
  for (const e of distForm.value.entries) {
    if (e.amount == null || (e.amount as unknown) === '') continue
    e.amount = mode === 'percent' ? Math.round((e.amount / pay) * 1000) / 10 : Math.round(pay * e.amount) / 100
  }
  distForm.value.mode = mode
}

const distPreview = computed(() => {
  const f = distForm.value
  const parts = f.entries.filter(e => e.account && e.amount != null && (e.amount as unknown) !== '')
    .map(e => `${e.account} ${currency(f.mode === 'percent' ? f.paycheck * Number(e.amount) / 100 : Number(e.amount))}`)
  const given = f.entries.reduce((sum, e) => sum + (e.amount == null || (e.amount as unknown) === '' ? 0
    : f.mode === 'percent' ? f.paycheck * Number(e.amount) / 100 : Number(e.amount)), 0)
  const rest = f.entries.find(e => e.account && (e.amount == null || (e.amount as unknown) === ''))
  if (rest) parts.push(`${rest.account} ${currency(Math.max(0, f.paycheck - given))} (the rest)`)
  if (!parts.length) return ''
  return `From a ${currency(f.paycheck)} paycheck: ${parts.join(' · ')}` + (given > f.paycheck + 0.005 ? ' — more than the paycheck!' : '')
})

function openDistEdit(inc: IncomeItem) {
  const dist = parseDist(inc.distribution)
  const detail = distDetail(inc)
  const percent = !!detail && Object.values(detail).some(d => d?.type === 'percentage')
  const entries = dist
    ? Object.entries(dist).map(([account, rawAmount]) => {
        const amount = percent && rawAmount != null ? Math.round(Number(rawAmount) * 1000) / 10 : rawAmount
        // Try to find which bank owns this account
        let bankName = ''
        for (const b of banks.value) {
          const found = b.bankAccounts.some(a => a.accountName === account) ||
                        b.creditAccounts.some(a => a.accountName === account)
          if (found) { bankName = b.name; break }
        }
        return { bank: bankName, account, amount: amount as number | null }
      })
    : []
  if (entries.length === 0) entries.push({ bank: '', account: '', amount: null })
  distForm.value = { sourceName: inc.sourceName, paycheck: inc.amount, mode: percent ? 'percent' : 'fixed', entries }
  showDistModal.value = true
}

async function saveDist() {
  const distObj: Record<string, { value: number; type: string } | null> = {}
  const percent = distForm.value.mode === 'percent'
  let totalPct = 0
  let remainderCount = 0
  for (const entry of distForm.value.entries) {
    const account = entry.account.trim()
    if (!account) continue
    // v-model.number yields '' for a cleared input — treat blank as "remainder" (null)
    const raw = entry.amount as number | string | null
    const amount = raw === '' || raw == null || Number.isNaN(Number(raw)) ? null : Number(raw)
    if (amount === null) remainderCount++
    else if (amount < 0) {
      notify(`The amount for "${account}" can’t be negative`, 'error')
      return
    }
    if (amount !== null && percent) totalPct += amount
    distObj[account] = amount === null ? null
      : { value: percent ? amount / 100 : amount, type: percent ? 'percentage' : 'fixed_amount' }
  }
  if (percent && totalPct > 100.0001) {
    notify('The percentages add up to more than 100%', 'error')
    return
  }
  if (remainderCount > 1) {
    notify('Only one account can receive the remainder (blank amount)', 'error')
    return
  }
  const ok = await runMutation(() => doUpdate({ variables: {
    sourceName: distForm.value.sourceName,
    distribution: JSON.stringify(distObj),
  }}), 'updateIncome', { failMessage: 'Failed to save distribution' })
  if (!ok) return
  showDistModal.value = false
  refetch()
}
</script>


<style scoped>
.amt-wrap { position: relative; }
.amt-wrap input { width: 100%; }
.amt-suffix { position: absolute; right: 0.6rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 0.85rem; pointer-events: none; }
</style>
