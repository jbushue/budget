<template>
  <div>
    <div class="view-header">
      <h2>Income Sources</h2>
      <button class="btn btn-primary btn-sm" @click="openCreate()">+ Add Income</button>
    </div>

    <div v-if="loading" class="loading">Loading income sources...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else>
      <div v-if="incomes.length === 0" class="empty-state">
        <div class="icon">💵</div>
        <p>No income sources yet. Click "+ Add Income" to add one.</p>
      </div>

      <div class="card" v-else>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Frequency</th>
                <th>Pay Dates</th>
                <th>Next Pay Date</th>
                <th style="text-align:right">Amount</th>
                <th style="text-align:right">Est. Monthly</th>
                <th>Distribution</th>
                <th style="text-align:right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="inc in incomes" :key="inc.id">
                <td style="font-weight:500">{{ inc.sourceName }}</td>
                <td><span class="badge badge-info">{{ frequencyLabel(inc.frequency) }}</span></td>
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
                <td style="text-align:right;font-weight:600;color:var(--success)">{{ currency(inc.amount) }}</td>
                <td style="text-align:right">{{ currency(estimatedMonthly(inc)) }}</td>
                <td style="font-size:0.8rem;color:var(--text-muted)">
                  <template v-if="parseDist(inc.distribution)">
                    <div v-for="(val, acct) in parseDist(inc.distribution)" :key="acct">
                      <strong>{{ acct }}:</strong> {{ val === null ? 'remainder' : currency(val as number) }}
                    </div>
                  </template>
                  <span v-else>Default</span>
                </td>
                <td style="text-align:right;white-space:nowrap">
                  <button class="btn btn-outline btn-sm" @click="openDistEdit(inc)" style="margin-right:0.25rem" title="Edit distribution">Dist</button>
                  <button class="btn btn-outline btn-sm" @click="openEdit(inc)" style="margin-right:0.25rem">Edit</button>
                  <button class="btn btn-danger btn-sm" @click="deleteIncome(inc.sourceName)">Del</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Income summary -->
      <div class="grid grid-3" style="margin-top:1.5rem">
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(totalMonthly) }}</div>
          <div class="stat-label">Est. Monthly Income</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value positive">{{ currency(totalMonthly * 12) }}</div>
          <div class="stat-label">Est. Annual Income</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{{ incomes.length }}</div>
          <div class="stat-label">Income Sources</div>
        </div>
      </div>
    </template>

    <!-- Create / Edit Income Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3>{{ editMode ? 'Edit Income Source' : 'Add Income Source' }}</h3>
        <div class="form-group">
          <label>Source Name</label>
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
            <label>Second Pay Day (day of month, 1-31)</label>
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
        <h3>Edit Distribution: {{ distForm.sourceName }}</h3>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Assign fixed amounts to checking/savings accounts. At most one account can receive the "remainder" (leave its amount blank).
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
          <input v-model.number="entry.amount" type="number" step="0.01" placeholder="Amt (blank=rest)" style="flex:0.8" />
          <button class="btn btn-danger btn-sm" @click="distForm.entries.splice(idx, 1)" style="padding:0.3rem 0.5rem">&times;</button>
        </div>
        <button class="btn btn-outline btn-sm" @click="distForm.entries.push({ bank: '', account: '', amount: null })" style="margin-bottom:1rem">+ Add Account</button>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showDistModal = false">Cancel</button>
          <button class="btn btn-primary" @click="saveDist">Save Distribution</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_ALL_INCOME, GET_ALL_BANKS, CREATE_INCOME_SOURCE, UPDATE_INCOME, DELETE_INCOME } from '../graphql/queries'
import { currency, fmtDate, frequencyLabel } from '../utils/format'
import { runMutation } from '../utils/mutation'
import type { IncomeItem, Bank, MutationPayload } from '../types'

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
  if (!confirm(`Delete income source "${name}"?`)) return
  const ok = await runMutation(() => doDelete({ variables: { sourceName: name }}), 'deleteIncome', { failMessage: 'Failed to delete income source' })
  if (ok) refetch()
}

// ── Edit Distribution
const showDistModal = ref(false)
const distForm = ref<{ sourceName: string; entries: { bank: string; account: string; amount: number | null }[] }>({ sourceName: '', entries: [] })

function openDistEdit(inc: IncomeItem) {
  const dist = parseDist(inc.distribution)
  const entries = dist
    ? Object.entries(dist).map(([account, amount]) => {
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
  distForm.value = { sourceName: inc.sourceName, entries }
  showDistModal.value = true
}

async function saveDist() {
  const distObj: Record<string, number | null> = {}
  let remainderCount = 0
  for (const entry of distForm.value.entries) {
    const account = entry.account.trim()
    if (!account) continue
    // v-model.number yields '' for a cleared input — treat blank as "remainder" (null)
    const raw = entry.amount as number | string | null
    const amount = raw === '' || raw == null || Number.isNaN(Number(raw)) ? null : Number(raw)
    if (amount === null) remainderCount++
    else if (amount < 0) {
      alert(`Error: Amount for "${account}" cannot be negative`)
      return
    }
    distObj[account] = amount
  }
  if (remainderCount > 1) {
    alert('Error: Only one account can receive the remainder (blank amount)')
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

