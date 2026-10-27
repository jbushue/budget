<template>
  <div>
    <div class="view-header">
      <h2>Bills &amp; Payments</h2>
      <div style="display:flex;gap:0.5rem">
        <button class="btn btn-outline btn-sm" @click="autoReset()">🔄 Auto-Reset</button>
        <button class="btn btn-primary btn-sm" @click="openCreate()">+ Add Bill</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading bills...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else>
      <!-- Filter chips -->
      <div class="chip-group" style="margin-bottom:1rem">
        <span class="chip" :class="{ selected: filter === 'all' }" @click="filter = 'all'">All ({{ unifiedRows.length }})</span>
        <span class="chip" :class="{ selected: filter === 'fixed' }" @click="filter = 'fixed'">Fixed</span>
        <span class="chip" :class="{ selected: filter === 'floating' }" @click="filter = 'floating'">Variable</span>
        <span class="chip" :class="{ selected: filter === 'credit' }" @click="filter = 'credit'">💳 Credit</span>
        <span class="chip" :class="{ selected: filter === 'group' }" @click="filter = 'group'">🎓 Groups</span>
        <span class="chip" :class="{ selected: filter === 'mortgage' }" @click="filter = 'mortgage'">🏠 Mortgage</span>
        <span class="chip" :class="{ selected: filter === 'heloc' }" @click="filter = 'heloc'">🏦 HELOC</span>
        <span class="chip" :class="{ selected: filter === 'unpaid' }" @click="filter = 'unpaid'">Unpaid</span>
        <span class="chip" :class="{ selected: filter === 'paid' }" @click="filter = 'paid'">Paid</span>
      </div>

      <div v-if="filtered.length === 0" class="empty-state">
        <div class="icon">📋</div>
        <p>No bills found. Add your first bill above.</p>
      </div>

      <div class="card" v-else>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Name</th>
                <th>Type</th>
                <th>Frequency</th>
                <th>Due Day</th>
                <th style="text-align:right">Amount</th>
                <th>Details</th>
                <th>Source</th>
                <th style="text-align:right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in filtered" :key="row.key" :style="row.isPaid ? 'opacity:0.65' : ''">
                <!-- Status -->
                <td>
                  <span v-if="row.isPaid" class="badge badge-success">PAID</span>
                  <span v-else class="badge badge-warning">DUE</span>
                  <div v-if="row.isPaid && row.lastPaymentInfo" style="font-size:0.7rem;color:var(--text-muted)">
                    {{ row.lastPaymentInfo }}
                  </div>
                </td>
                <!-- Name -->
                <td style="font-weight:500">{{ row.name }}</td>
                <!-- Type badge -->
                <td>
                  <span class="badge" :class="row.typeBadgeClass">{{ row.typeLabel }}</span>
                </td>
                <!-- Frequency -->
                <td>{{ row.frequencyLabel }}</td>
                <!-- Due Day -->
                <td>{{ row.dueDay ?? '-' }}</td>
                <!-- Amount -->
                <td style="text-align:right;font-weight:600">
                  <span :style="row.amountColor ? `color:${row.amountColor}` : ''">{{ currency(row.amount) }}</span>
                  <div v-if="row.amountSubtext" style="font-size:0.7rem;color:var(--text-muted)" v-html="row.amountSubtext"></div>
                </td>
                <!-- Details -->
                <td style="font-size:0.8rem;color:var(--text-muted)">
                  <!-- Credit: utilization bar -->
                  <template v-if="row.kind === 'credit' && row.creditData">
                    <div style="display:flex;align-items:center;gap:0.5rem">
                      <div class="progress-bar" style="width:80px">
                        <div class="fill" :style="{ width: creditUtilPct(row.creditData) + '%', background: creditUtilColor(row.creditData) }"></div>
                      </div>
                      <span style="font-size:0.7rem">{{ creditUtilPct(row.creditData).toFixed(0) }}%</span>
                    </div>
                    <div style="font-size:0.7rem">APR {{ pct(row.creditData.interestRate) }}</div>
                  </template>
                  <!-- Group: member count + total balance -->
                  <template v-else-if="row.kind === 'group' && row.groupData">
                    <div>{{ row.groupData.memberCount }} accounts</div>
                    <div style="color:var(--danger)">Bal: {{ currency(row.groupData.totalBalance) }}</div>
                  </template>
                  <!-- Mortgage: principal info -->
                  <template v-else-if="row.kind === 'mortgage' && row.mortgageData">
                    <div>Principal: {{ currency(row.mortgageData.currentPrincipal) }}</div>
                    <div>APR {{ pct(row.mortgageData.interestRate) }}</div>
                  </template>
                  <!-- HELOC: balance/phase -->
                  <template v-else-if="row.kind === 'heloc' && row.helocData">
                    <div>Bal: {{ currency(row.helocData.balance) }}</div>
                    <div>{{ row.helocData.currentPhase }} · APR {{ pct(row.helocData.interestRate) }}</div>
                  </template>
                  <!-- Bill: carryover / floating range -->
                  <template v-else-if="row.kind === 'bill' && row.billData">
                    <div v-if="row.billData.carryoverBalance > 0" style="color:var(--danger)">
                      +{{ currency(row.billData.carryoverBalance) }} carryover
                    </div>
                    <div v-if="row.billData.billType === 'floating' && row.billData.hasActualAmount" style="color:var(--success)">
                      Actual: {{ currency(row.billData.actualAmount!) }}
                    </div>
                    <div v-else-if="row.billData.billType === 'floating' && row.billData.minAmount && row.billData.maxAmount">
                      {{ currency(row.billData.minAmount) }} - {{ currency(row.billData.maxAmount) }}
                    </div>
                  </template>
                </td>
                <!-- Source -->
                <td style="font-size:0.8rem;color:var(--text-muted)">
                  {{ row.source || 'Auto' }}
                </td>
                <!-- Actions -->
                <td style="text-align:right;white-space:nowrap">
                  <!-- Bill actions -->
                  <template v-if="row.kind === 'bill'">
                    <template v-if="!row.isPaid">
                      <button v-if="row.billData?.billType === 'floating'" class="btn btn-outline btn-sm" @click="openSetActual(row.billData!)" style="margin-right:0.25rem" title="Set actual amount">$</button>
                      <button class="btn btn-success btn-sm" @click="openMarkPaid(row.billData!)" style="margin-right:0.25rem" title="Mark as paid">Pay</button>
                    </template>
                    <button v-else class="btn btn-outline btn-sm" @click="resetBill(row.billData!.billName)" style="margin-right:0.25rem" title="Reset for new period">Reset</button>
                    <button class="btn btn-outline btn-sm" @click="openEdit(row.billData!)" style="margin-right:0.25rem">Edit</button>
                    <button class="btn btn-danger btn-sm" @click="deleteBill(row.billData!.billName)">Del</button>
                  </template>
                  <!-- Credit actions -->
                  <template v-else-if="row.kind === 'credit'">
                    <template v-if="creditTarget(row)">
                      <template v-if="!row.isPaid">
                        <button class="btn btn-success btn-sm" @click="openCreditPay(row)" title="Mark as paid">Pay</button>
                      </template>
                      <button v-else class="btn btn-outline btn-sm" @click="resetCreditPayment(row)" title="Reset for new period">Reset</button>
                    </template>
                  </template>
                  <!-- Group actions -->
                  <template v-else-if="row.kind === 'group'">
                    <template v-if="!row.isPaid">
                      <button v-if="row.groupData" class="btn btn-success btn-sm" @click="openGroupPay(row.groupData)" style="margin-right:0.25rem">Pay</button>
                    </template>
                    <router-link to="/bill-groups" class="btn btn-outline btn-sm">Details →</router-link>
                  </template>
                  <!-- Mortgage / HELOC actions (linked "[Auto] ... Payment" bill) -->
                  <template v-else-if="(row.kind === 'mortgage' || row.kind === 'heloc') && row.billData">
                    <button v-if="!row.isPaid" class="btn btn-success btn-sm" @click="openMarkPaid(row.billData)" title="Mark as paid">Pay</button>
                    <button v-else class="btn btn-outline btn-sm" @click="resetBill(row.billData.billName)" title="Reset for new period">Reset</button>
                  </template>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr style="font-weight:600">
                <td colspan="5">Total ({{ filtered.length }} items)</td>
                <td style="text-align:right">{{ currency(filteredTotal) }}</td>
                <td colspan="3"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Monthly summary -->
      <div class="grid grid-3" style="margin-top:1.5rem">
        <div class="card stat-card">
          <div class="stat-value">{{ currency(totalMonthly) }}</div>
          <div class="stat-label">Est. Monthly Obligations</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{{ paidCount }} / {{ unifiedRows.length }}</div>
          <div class="stat-label">Paid This Period</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{{ currency(totalMonthly * 12) }}</div>
          <div class="stat-label">Est. Annual Obligations</div>
        </div>
      </div>
    </template>

    <!-- Create / Edit Bill Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3>{{ editMode ? 'Edit Bill' : 'Add Bill' }}</h3>
        <div class="form-group">
          <label>Bill Name</label>
          <input v-model="form.billName" placeholder="e.g. Electric Bill" :disabled="editMode" />
        </div>
        <div v-if="!editMode" class="form-group">
          <label>Bill Type</label>
          <select v-model="form.billType">
            <option value="fixed">Fixed</option>
            <option value="floating">Variable</option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ form.billType === 'floating' ? 'Estimated Amount' : 'Amount' }}</label>
          <input v-model.number="form.amount" type="number" step="0.01" />
        </div>
        <div v-if="form.billType === 'floating'" style="display:flex;gap:0.75rem">
          <div class="form-group" style="flex:1">
            <label>Min Amount</label>
            <input v-model.number="form.minAmount" type="number" step="0.01" />
          </div>
          <div class="form-group" style="flex:1">
            <label>Max Amount</label>
            <input v-model.number="form.maxAmount" type="number" step="0.01" />
          </div>
        </div>
        <div class="form-group">
          <label>Due Day (1-31)</label>
          <input v-model.number="form.dueDate" type="number" min="1" max="31" />
        </div>
        <div class="form-group">
          <label>Frequency</label>
          <select v-model="form.frequency">
            <option value="monthly">Monthly</option>
            <option value="weekly">Weekly</option>
            <option value="biweekly">Bi-weekly</option>
            <option value="quarterly">Quarterly</option>
            <option value="semi_annual">Semi-annual</option>
            <option value="yearly">Yearly</option>
            <option value="once">One-time</option>
          </select>
        </div>
        <div v-if="form.frequency === 'yearly' || form.frequency === 'semi_annual'" class="form-group">
          <label>Due Month (1-12)</label>
          <select v-model.number="form.dueMonth">
            <option :value="null">Same as current month</option>
            <option v-for="m in 12" :key="m" :value="m">{{ monthName(m) }}</option>
          </select>
        </div>
        <div v-if="usesStartDate(form.frequency)" class="form-group">
          <label>Start / First Due Date (optional)</label>
          <input v-model="form.startDate" type="date" />
        </div>
        <div class="form-group">
          <label>Preferred Source Bank (optional)</label>
          <select v-model="form.preferredSourceBank">
            <option value="">Auto (no preference)</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Preferred Source Account (optional)</label>
          <select v-model="form.preferredSourceAccount" :disabled="!form.preferredSourceBank">
            <option value="">Auto (no preference)</option>
            <option v-for="acc in accountsForBank(form.preferredSourceBank)" :key="acc.name" :value="acc.name">{{ acc.name }} ({{ acc.label }})</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showModal = false">Cancel</button>
          <button class="btn btn-primary" @click="saveBill" :disabled="!form.billName || !form.amount">
            {{ editMode ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Mark Paid Modal -->
    <div v-if="showPayModal" class="modal-overlay" @click.self="showPayModal = false">
      <div class="modal">
        <h3>Mark "{{ payForm.billName }}" as Paid</h3>
        <p v-if="payingBill" style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Amount due: {{ currency(payingBill.effectiveAmount) }}
          <template v-if="payingBill.carryoverBalance > 0"> (includes {{ currency(payingBill.carryoverBalance) }} carryover)</template>
        </p>
        <div class="form-group">
          <label>Amount Paid</label>
          <input v-model.number="payForm.amountPaid" type="number" step="0.01" />
          <div v-if="payingBill && payForm.amountPaid < payingBill.effectiveAmount" style="font-size:0.75rem;color:var(--warning);margin-top:0.25rem">
            {{ currency(payingBill.effectiveAmount - payForm.amountPaid) }} will carry over to next period
          </div>
        </div>
        <div class="form-group">
          <label>Source Bank</label>
          <select v-model="payForm.sourceBank">
            <option value="">Select bank...</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Source Account</label>
          <select v-model="payForm.sourceAccount" :disabled="!payForm.sourceBank">
            <option value="">Select account...</option>
            <option v-for="acc in accountsForBank(payForm.sourceBank)" :key="acc.name" :value="acc.name">{{ acc.name }} ({{ acc.label }})</option>
          </select>
        </div>
        <div class="form-group">
          <label>Payment Date</label>
          <input v-model="payForm.paymentDate" type="date" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showPayModal = false">Cancel</button>
          <button class="btn btn-success" @click="markPaid">Mark Paid</button>
        </div>
      </div>
    </div>

    <!-- Set Actual Amount Modal -->
    <div v-if="showActualModal" class="modal-overlay" @click.self="showActualModal = false">
      <div class="modal">
        <h3>Set Actual Amount for "{{ actualForm.billName }}"</h3>
        <p v-if="actualForm.min && actualForm.max" style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Range: {{ currency(actualForm.min) }} - {{ currency(actualForm.max) }}
        </p>
        <div class="form-group">
          <label>Actual Amount</label>
          <input v-model.number="actualForm.amount" type="number" step="0.01" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showActualModal = false">Cancel</button>
          <button class="btn btn-primary" @click="setActualAmount">Set Amount</button>
        </div>
      </div>
    </div>

    <!-- Credit Card Payment Modal -->
    <div v-if="showCreditPayModal" class="modal-overlay" @click.self="showCreditPayModal = false">
      <div class="modal">
        <h3>Pay "{{ creditPayForm.accountName }}" ({{ creditPayForm.bankName }})</h3>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Balance: {{ currency(creditPayForm.balance) }} · Min Payment: {{ currency(creditPayForm.minPayment) }}
        </p>
        <div class="form-group">
          <label>Amount Paid</label>
          <input v-model.number="creditPayForm.amountPaid" type="number" step="0.01" />
        </div>
        <div class="form-group">
          <label>Source Bank</label>
          <select v-model="creditPayForm.sourceBank">
            <option value="">Select bank...</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Source Account</label>
          <select v-model="creditPayForm.sourceAccount" :disabled="!creditPayForm.sourceBank">
            <option value="">Select account...</option>
            <option v-for="acc in accountsForBank(creditPayForm.sourceBank)" :key="acc.name" :value="acc.name">{{ acc.name }} ({{ acc.label }})</option>
          </select>
        </div>
        <div class="form-group">
          <label>Payment Date</label>
          <input v-model="creditPayForm.paymentDate" type="date" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showCreditPayModal = false">Cancel</button>
          <button class="btn btn-success" @click="markCreditPaid">Mark Paid</button>
        </div>
      </div>
    </div>

    <!-- Bill Group Payment Modal -->
    <div v-if="showGroupPayModal" class="modal-overlay" @click.self="showGroupPayModal = false">
      <div class="modal">
        <h3>Pay "{{ groupPayForm.groupName }}"</h3>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Scheduled payment: {{ currency(groupPayForm.totalPayment) }}
        </p>
        <div class="form-group">
          <label>Amount Paid</label>
          <input v-model.number="groupPayForm.amountPaid" type="number" step="0.01" />
        </div>
        <div class="form-group">
          <label>Source Bank</label>
          <select v-model="groupPayForm.sourceBank">
            <option value="">Select bank...</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Source Account</label>
          <select v-model="groupPayForm.sourceAccount" :disabled="!groupPayForm.sourceBank">
            <option value="">Select account...</option>
            <option v-for="acc in accountsForBank(groupPayForm.sourceBank, false)" :key="acc.name" :value="acc.name">{{ acc.name }} ({{ acc.label }})</option>
          </select>
        </div>
        <div class="form-group">
          <label>Payment Date</label>
          <input v-model="groupPayForm.paymentDate" type="date" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showGroupPayModal = false">Cancel</button>
          <button class="btn btn-success" @click="markGroupPaid" :disabled="!groupPayForm.amountPaid || groupPayForm.amountPaid <= 0">Mark Paid</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import {
  GET_ALL_BILLS, GET_ALL_BANKS, GET_CREDIT_PAYMENTS_DUE,
  GET_ALL_BILL_GROUPS,
  CREATE_BILL, UPDATE_BILL, DELETE_BILL,
  MARK_BILL_PAID, RESET_BILL_PERIOD, SET_FLOATING_BILL_AMOUNT,
  MARK_CREDIT_PAYMENT_PAID, RESET_CREDIT_PAYMENT_PERIOD,
  AUTO_RESET_PERIODS,
  MARK_BILL_GROUP_PAID,
} from '../graphql/queries'
import { currency, pct, fmtDate, frequencyLabel, billTypeLabel, todayISO } from '../utils/format'
import { runMutation } from '../utils/mutation'
import type { BillItem, Bank, CreditPaymentDue, BillGroup, MortgageAccount, HELOCAccount, MutationPayload } from '../types'

// ── Unified Row Type ──
interface UnifiedRow {
  key: string
  kind: 'bill' | 'credit' | 'group' | 'mortgage' | 'heloc'
  name: string
  typeLabel: string
  typeBadgeClass: string
  frequencyLabel: string
  dueDay: number | null
  amount: number
  amountColor?: string
  amountSubtext?: string
  isPaid: boolean
  lastPaymentInfo?: string
  source: string
  billData?: BillItem
  creditData?: CreditPaymentDue
  groupData?: BillGroup
  mortgageData?: MortgageAccount & { bankName: string }
  helocData?: HELOCAccount & { bankName: string }
}

// ── Data Queries ──
const { result, loading, error, refetch } = useQuery<{ allBills: BillItem[] }>(GET_ALL_BILLS)
const bills = computed(() => result.value?.allBills ?? [])

// Split bills into regular and linked categories
const regularBills = computed(() => bills.value.filter(b => !b.isAccountLinked))
const linkedBills = computed(() => bills.value.filter(b => b.isAccountLinked))

const { result: banksResult, refetch: refetchBanks } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const banks = computed(() => banksResult.value?.allBanks ?? [])

const { result: groupsResult, refetch: refetchGroups } = useQuery<{ allBillGroups: BillGroup[] }>(GET_ALL_BILL_GROUPS)
const billGroups = computed(() => groupsResult.value?.allBillGroups ?? [])

// Build a set of "bank:account" keys for accounts that belong to a bill group
const groupedAccountKeys = computed(() => {
  const keys = new Set<string>()
  for (const g of billGroups.value) {
    for (const m of g.members) {
      keys.add(`${m.bankName}:${m.accountName}`)
    }
  }
  return keys
})

// Credit payments due query — used for detailed credit info (balance, utilization)
const { result: creditResult, refetch: refetchCredit } = useQuery<{ creditPaymentsDue: CreditPaymentDue[] }>(GET_CREDIT_PAYMENTS_DUE)
const creditPayments = computed(() => {
  const all = creditResult.value?.creditPaymentsDue ?? []
  return all.filter(cp => !groupedAccountKeys.value.has(`${cp.bankName}:${cp.accountName}`))
})

// Build a lookup map of credit details from the credit payments query
const creditDetailMap = computed(() => {
  const map = new Map<string, CreditPaymentDue>()
  for (const cp of creditResult.value?.creditPaymentsDue ?? []) {
    map.set(`${cp.bankName}:${cp.accountName}`, cp)
  }
  return map
})

// Build lookup maps for mortgage & HELOC details from banks
const mortgageDetailMap = computed(() => {
  const map = new Map<string, MortgageAccount & { bankName: string }>()
  for (const b of banks.value) {
    for (const m of b.mortgageAccounts) {
      map.set(`${b.name}:${m.accountName}`, { ...m, bankName: b.name })
    }
  }
  return map
})

const helocDetailMap = computed(() => {
  const map = new Map<string, HELOCAccount & { bankName: string }>()
  for (const b of banks.value) {
    for (const h of b.helocAccounts) {
      map.set(`${b.name}:${h.accountName}`, { ...h, bankName: b.name })
    }
  }
  return map
})

// ── Build unified rows ──
const unifiedRows = computed<UnifiedRow[]>(() => {
  const rows: UnifiedRow[] = []

  // Regular bills (not account-linked)
  for (const b of regularBills.value) {
    rows.push({
      key: `bill-${b.id}`,
      kind: 'bill',
      name: b.billName,
      typeLabel: billTypeLabel(b.billType),
      typeBadgeClass: b.billType === 'fixed' ? 'badge-info' : 'badge-warning',
      frequencyLabel: frequencyLabel(b.frequency),
      dueDay: b.dueDate,
      amount: b.effectiveAmount,
      isPaid: b.isPaidThisPeriod,
      source: b.preferredSourceBank ? `${b.preferredSourceBank} / ${b.preferredSourceAccount}` : '',
      billData: b,
    })
  }

  // Account-linked bills (credit cards, mortgages, HELOCs)
  for (const b of linkedBills.value) {
    const acctKey = b.linkedBankName && b.linkedAccountName
      ? `${b.linkedBankName}:${b.linkedAccountName}`
      : null

    if (b.linkedAccountType === 'credit') {
      // Skip grouped credit accounts
      if (acctKey && groupedAccountKeys.value.has(acctKey)) continue
      // Skip zero-balance credit cards (no payment needed)
      if (b.amount <= 0) continue

      const cp = acctKey ? creditDetailMap.value.get(acctKey) : null
      rows.push({
        key: `credit-${b.id}`,
        kind: 'credit',
        name: `${b.linkedBankName} · ${b.linkedAccountName}`,
        typeLabel: '💳 Credit',
        typeBadgeClass: 'badge-danger',
        frequencyLabel: 'Monthly',
        dueDay: b.dueDate,
        amount: b.amount,
        amountColor: 'var(--danger)',
        amountSubtext: cp ? `Bal: ${currency(cp.balance)}` : undefined,
        isPaid: b.isPaidThisPeriod,
        lastPaymentInfo: b.isPaidThisPeriod && cp?.lastPaymentAmount
          ? `${currency(cp.lastPaymentAmount)} on ${fmtDate(cp.lastPaymentDate)}`
          : undefined,
        source: b.preferredSourceBank ? `${b.preferredSourceBank} / ${b.preferredSourceAccount}` : '',
        creditData: cp ?? undefined,
        billData: b,
      })
    } else if (b.linkedAccountType === 'mortgage') {
      const md = acctKey ? mortgageDetailMap.value.get(acctKey) : null
      rows.push({
        key: `mortgage-${b.id}`,
        kind: 'mortgage',
        name: `${b.linkedBankName} · ${b.linkedAccountName}`,
        typeLabel: '🏠 Mortgage',
        typeBadgeClass: 'badge-info',
        frequencyLabel: 'Monthly',
        dueDay: b.dueDate,
        amount: b.amount,
        isPaid: b.isPaidThisPeriod,
        source: b.preferredSourceBank ? `${b.preferredSourceBank} / ${b.preferredSourceAccount}` : '',
        mortgageData: md ?? undefined,
        billData: b,
      })
    } else if (b.linkedAccountType === 'heloc') {
      // Skip zero-balance HELOCs
      if (b.amount <= 0) continue

      const hd = acctKey ? helocDetailMap.value.get(acctKey) : null
      rows.push({
        key: `heloc-${b.id}`,
        kind: 'heloc',
        name: `${b.linkedBankName} · ${b.linkedAccountName}`,
        typeLabel: '🏦 HELOC',
        typeBadgeClass: 'badge-warning',
        frequencyLabel: 'Monthly',
        dueDay: b.dueDate,
        amount: b.amount,
        isPaid: b.isPaidThisPeriod,
        source: b.preferredSourceBank ? `${b.preferredSourceBank} / ${b.preferredSourceAccount}` : '',
        helocData: hd ?? undefined,
        billData: b,
      })
    }
  }

  // Bill groups
  for (const g of billGroups.value) {
    rows.push({
      key: `group-${g.groupName}`,
      kind: 'group',
      name: `${groupTypeIcon(g.groupType)} ${g.groupName}`,
      typeLabel: '🎓 Group',
      typeBadgeClass: 'badge-info',
      frequencyLabel: frequencyLabel(g.frequency),
      dueDay: g.dueDate,
      amount: g.totalPayment,
      isPaid: g.isPaidThisPeriod,
      source: g.preferredSourceBank ? `${g.preferredSourceBank} / ${g.preferredSourceAccount}` : '',
      groupData: g,
    })
  }

  // Sort: unpaid first, then by due day
  rows.sort((a, b) => {
    if (a.isPaid !== b.isPaid) return a.isPaid ? 1 : -1
    return (a.dueDay ?? 32) - (b.dueDay ?? 32)
  })

  return rows
})

// ── Filtering ──
const filter = ref('all')
const filtered = computed(() => {
  if (filter.value === 'all') return unifiedRows.value
  if (filter.value === 'paid') return unifiedRows.value.filter(r => r.isPaid)
  if (filter.value === 'unpaid') return unifiedRows.value.filter(r => !r.isPaid)
  if (filter.value === 'credit') return unifiedRows.value.filter(r => r.kind === 'credit')
  if (filter.value === 'group') return unifiedRows.value.filter(r => r.kind === 'group')
  if (filter.value === 'mortgage') return unifiedRows.value.filter(r => r.kind === 'mortgage')
  if (filter.value === 'heloc') return unifiedRows.value.filter(r => r.kind === 'heloc')
  if (filter.value === 'fixed') return unifiedRows.value.filter(r => r.kind === 'bill' && r.billData?.billType === 'fixed')
  if (filter.value === 'floating') return unifiedRows.value.filter(r => r.kind === 'bill' && r.billData?.billType === 'floating')
  return unifiedRows.value
})

const filteredTotal = computed(() => filtered.value.reduce((s, r) => s + r.amount, 0))
const paidCount = computed(() => unifiedRows.value.filter(r => r.isPaid).length)

const totalMonthly = computed(() => {
  let total = 0
  for (const row of unifiedRows.value) {
    if (row.kind === 'bill') {
      const mult: Record<string, number> = { monthly: 1, weekly: 4.33, biweekly: 2.17, quarterly: 0.33, semi_annual: 0.167, yearly: 0.083, once: 0 }
      const freq = row.billData?.frequency ?? 'monthly'
      total += row.amount * (mult[freq] ?? 1)
    } else if (row.kind === 'group') {
      const mult: Record<string, number> = { monthly: 1, biweekly: 2.17, quarterly: 0.33 }
      const freq = row.groupData?.frequency ?? 'monthly'
      total += row.amount * (mult[freq] ?? 1)
    } else {
      // credit, mortgage, heloc — all monthly
      total += row.amount
    }
  }
  return total
})

// ── Helpers ──
function groupTypeIcon(t: string): string {
  const map: Record<string, string> = { student_loan: '🎓', bundled_bill: '📦', consolidated_loan: '🏦', other: '📋' }
  return map[t] || '📋'
}

function creditUtilPct(cp: CreditPaymentDue): number {
  return cp.creditLimit > 0 ? (cp.balance / cp.creditLimit) * 100 : 0
}
function creditUtilColor(cp: CreditPaymentDue): string {
  const u = creditUtilPct(cp)
  if (u > 80) return 'var(--danger)'
  if (u > 50) return 'var(--warning)'
  return 'var(--success)'
}

function monthName(m: number): string {
  return new Date(2024, m - 1).toLocaleString('en-US', { month: 'long' })
}

const START_DATE_FREQS = ['weekly', 'biweekly', 'quarterly', 'semi_annual', 'yearly', 'once']
function usesStartDate(freq: string): boolean {
  return START_DATE_FREQS.includes(freq)
}

function accountsForBank(bankName: string, includeCredit = true): { name: string; type: string; label: string }[] {
  if (!bankName) return []
  const bank = banks.value.find(b => b.name === bankName)
  if (!bank) return []
  const accounts: { name: string; type: string; label: string }[] = []
  for (const acc of bank.bankAccounts) accounts.push({ name: acc.accountName, type: acc.accountType, label: acc.accountType })
  if (includeCredit) {
    for (const acc of bank.creditAccounts) accounts.push({ name: acc.accountName, type: 'credit', label: 'credit card' })
  }
  return accounts
}

/** Keep the selected account only if it exists under the (newly) selected bank. */
function keepAccountIfValid(bankName: string, account: string): string {
  if (!account || !bankName) return ''
  if (banks.value.length === 0) return account
  return accountsForBank(bankName).some(a => a.name === account) ? account : ''
}

function firstCheckingSource(): { bank: string; account: string } {
  for (const b of banks.value) {
    const acc = b.bankAccounts.find(a => a.accountType === 'checking')
    if (acc) return { bank: b.name, account: acc.accountName }
  }
  return { bank: '', account: '' }
}

// ── Create / Edit Bill ──
const showModal = ref(false)
const editMode = ref(false)
function emptyForm() {
  return {
    billName: '', amount: 0, dueDate: 1, frequency: 'monthly' as string, dueMonth: null as number | null,
    billType: 'fixed' as string, minAmount: null as number | null, maxAmount: null as number | null,
    startDate: '', preferredSourceBank: '', preferredSourceAccount: '',
  }
}
const form = ref(emptyForm())

// Only clears the account when it doesn't belong to the chosen bank, so populating
// the form from Edit doesn't wipe the saved preference.
watch(() => form.value.preferredSourceBank, (newVal) => {
  form.value.preferredSourceAccount = keepAccountIfValid(newVal, form.value.preferredSourceAccount)
})

function openCreate() {
  editMode.value = false
  form.value = emptyForm()
  showModal.value = true
}

function openEdit(b: BillItem) {
  editMode.value = true
  form.value = {
    billName: b.billName, amount: b.amount, dueDate: b.dueDate, frequency: b.frequency,
    dueMonth: b.dueMonth ?? null,
    billType: b.billType, minAmount: b.minAmount ?? null, maxAmount: b.maxAmount ?? null,
    startDate: b.startDate || '',
    preferredSourceBank: b.preferredSourceBank || '', preferredSourceAccount: b.preferredSourceAccount || '',
  }
  showModal.value = true
}

const { mutate: doCreate } = useMutation<{ createBill: MutationPayload }>(CREATE_BILL)
const { mutate: doUpdate } = useMutation<{ updateBill: MutationPayload }>(UPDATE_BILL)
const { mutate: doDelete } = useMutation<{ deleteBill: MutationPayload }>(DELETE_BILL)

async function saveBill() {
  const f = form.value
  const isFloating = f.billType === 'floating'
  if (isFloating && f.minAmount != null && f.maxAmount != null && f.minAmount > f.maxAmount) {
    alert('Error: Min amount cannot be greater than max amount')
    return
  }
  const yearlyish = f.frequency === 'yearly' || f.frequency === 'semi_annual'
  const startDate = usesStartDate(f.frequency) ? (f.startDate || null) : null
  let ok
  if (editMode.value) {
    // An empty string clears the preferred source on the backend
    const bank = f.preferredSourceBank || ''
    ok = await runMutation(() => doUpdate({ variables: {
      billName: f.billName, amount: f.amount, dueDate: f.dueDate,
      frequency: f.frequency, dueMonth: yearlyish ? f.dueMonth : null,
      startDate,
      minAmount: isFloating ? f.minAmount : null, maxAmount: isFloating ? f.maxAmount : null,
      preferredSourceBank: bank, preferredSourceAccount: bank ? (f.preferredSourceAccount || '') : '',
    }}), 'updateBill', { failMessage: 'Failed to update bill' })
  } else {
    ok = await runMutation(() => doCreate({ variables: {
      billName: f.billName, amount: f.amount, dueDate: f.dueDate, frequency: f.frequency,
      dueMonth: yearlyish ? f.dueMonth : null,
      billType: f.billType,
      minAmount: isFloating ? f.minAmount : null, maxAmount: isFloating ? f.maxAmount : null,
      startDate,
      preferredSourceBank: f.preferredSourceBank || null,
      preferredSourceAccount: f.preferredSourceBank ? (f.preferredSourceAccount || null) : null,
    }}), 'createBill', { failMessage: 'Failed to create bill' })
  }
  if (!ok) return
  showModal.value = false
  refetch()
}

async function deleteBill(name: string) {
  if (!confirm(`Delete bill "${name}"?`)) return
  const ok = await runMutation(() => doDelete({ variables: { billName: name }}), 'deleteBill', { failMessage: 'Failed to delete bill' })
  if (ok) refetch()
}

// ── Mark Paid (regular bills and mortgage/HELOC "[Auto] ... Payment" bills) ──
const showPayModal = ref(false)
const payForm = ref({ billName: '', amountPaid: 0, sourceBank: '', sourceAccount: '', paymentDate: '' })
const { mutate: doMarkPaid } = useMutation<{ markBillPaid: MutationPayload }>(MARK_BILL_PAID)
const payingBill = computed(() => bills.value.find(b => b.billName === payForm.value.billName))

watch(() => payForm.value.sourceBank, (newVal) => {
  payForm.value.sourceAccount = keepAccountIfValid(newVal, payForm.value.sourceAccount)
})

function openMarkPaid(b: BillItem) {
  payForm.value = {
    billName: b.billName, amountPaid: b.effectiveAmount,
    sourceBank: b.preferredSourceBank || '', sourceAccount: b.preferredSourceAccount || '',
    paymentDate: todayISO(),
  }
  showPayModal.value = true
}

async function markPaid() {
  const ok = await runMutation(() => doMarkPaid({ variables: {
    billName: payForm.value.billName, amountPaid: payForm.value.amountPaid,
    sourceBank: payForm.value.sourceBank || null, sourceAccount: payForm.value.sourceAccount || null,
    paymentDate: payForm.value.paymentDate || null,
  }}), 'markBillPaid', { failMessage: 'Failed to mark bill as paid' })
  if (!ok) return
  showPayModal.value = false
  refetch()
  refetchCredit()
  refetchBanks()
}

// ── Reset Period ──
const { mutate: doReset } = useMutation<{ resetBillPeriod: MutationPayload }>(RESET_BILL_PERIOD)
async function resetBill(name: string) {
  const ok = await runMutation(() => doReset({ variables: { billName: name }}), 'resetBillPeriod', { failMessage: 'Failed to reset bill period' })
  if (ok) refetch()
}

// ── Set Floating Bill Actual Amount ──
const showActualModal = ref(false)
const actualForm = ref({ billName: '', amount: 0, min: 0, max: 0 })
const { mutate: doSetActual } = useMutation<{ setFloatingBillAmount: MutationPayload }>(SET_FLOATING_BILL_AMOUNT)

function openSetActual(b: BillItem) {
  actualForm.value = { billName: b.billName, amount: b.amount, min: b.minAmount || 0, max: b.maxAmount || 0 }
  showActualModal.value = true
}

async function setActualAmount() {
  const ok = await runMutation(
    () => doSetActual({ variables: { billName: actualForm.value.billName, actualAmount: actualForm.value.amount }}),
    'setFloatingBillAmount', { failMessage: 'Failed to set actual amount' },
  )
  if (!ok) return
  showActualModal.value = false
  refetch()
}

// ── Credit Card Payment tracking ──
const showCreditPayModal = ref(false)
const creditPayForm = ref({ bankName: '', accountName: '', balance: 0, minPayment: 0, amountPaid: 0, sourceBank: '', sourceAccount: '', paymentDate: '' })
const { mutate: doMarkCreditPaid } = useMutation<{ markCreditPaymentPaid: MutationPayload }>(MARK_CREDIT_PAYMENT_PAID)
const { mutate: doResetCreditPeriod } = useMutation<{ resetCreditPaymentPeriod: MutationPayload }>(RESET_CREDIT_PAYMENT_PERIOD)
const { mutate: doAutoReset } = useMutation<{ autoResetPeriods: MutationPayload & { resetCount?: number | null } }>(AUTO_RESET_PERIODS)

async function autoReset() {
  const ok = await runMutation(() => doAutoReset(), 'autoResetPeriods', { failMessage: 'Auto-reset failed', showSuccess: true })
  if (!ok) return
  refetch()
  refetchCredit()
  refetchGroups()
}

watch(() => creditPayForm.value.sourceBank, (newVal) => {
  creditPayForm.value.sourceAccount = keepAccountIfValid(newVal, creditPayForm.value.sourceAccount)
})

/** Resolve the card a credit row refers to (creditPaymentsDue entry, else the linked bill). */
function creditTarget(row: UnifiedRow): { bankName: string; accountName: string; balance: number; minimumPayment: number } | null {
  if (row.creditData) return row.creditData
  const b = row.billData
  if (b?.linkedBankName && b.linkedAccountName) {
    return { bankName: b.linkedBankName, accountName: b.linkedAccountName, balance: 0, minimumPayment: b.amount }
  }
  return null
}

function openCreditPay(row: UnifiedRow) {
  const cp = creditTarget(row)
  if (!cp) return
  const b = row.billData
  const src = b?.preferredSourceBank
    ? { bank: b.preferredSourceBank, account: b.preferredSourceAccount || '' }
    : firstCheckingSource()
  creditPayForm.value = {
    bankName: cp.bankName, accountName: cp.accountName,
    balance: cp.balance, minPayment: cp.minimumPayment,
    amountPaid: cp.minimumPayment, sourceBank: src.bank, sourceAccount: src.account,
    paymentDate: todayISO(),
  }
  showCreditPayModal.value = true
}

async function markCreditPaid() {
  const ok = await runMutation(() => doMarkCreditPaid({ variables: {
    bankName: creditPayForm.value.bankName, accountName: creditPayForm.value.accountName,
    amountPaid: creditPayForm.value.amountPaid,
    sourceBank: creditPayForm.value.sourceBank || null, sourceAccount: creditPayForm.value.sourceAccount || null,
    paymentDate: creditPayForm.value.paymentDate || null,
  }}), 'markCreditPaymentPaid', { failMessage: 'Failed to mark credit payment as paid' })
  if (!ok) return
  showCreditPayModal.value = false
  refetch()
  refetchCredit()
  refetchBanks()
}

async function resetCreditPayment(row: UnifiedRow) {
  const cp = creditTarget(row)
  if (!cp) return
  const ok = await runMutation(
    () => doResetCreditPeriod({ variables: { bankName: cp.bankName, accountName: cp.accountName }}),
    'resetCreditPaymentPeriod', { failMessage: 'Failed to reset credit payment period' },
  )
  if (!ok) return
  refetch()
  refetchCredit()
}

// ── Bill Group actions ──
const { mutate: doMarkGroupPaid } = useMutation<{ markBillGroupPaid: MutationPayload }>(MARK_BILL_GROUP_PAID)
const showGroupPayModal = ref(false)
const groupPayForm = ref({ groupName: '', totalPayment: 0, amountPaid: 0, sourceBank: '', sourceAccount: '', paymentDate: '' })

watch(() => groupPayForm.value.sourceBank, (newVal) => {
  const acct = groupPayForm.value.sourceAccount
  if (acct && banks.value.length > 0 && !accountsForBank(newVal, false).some(a => a.name === acct)) {
    groupPayForm.value.sourceAccount = ''
  }
})

function openGroupPay(g: BillGroup) {
  groupPayForm.value = {
    groupName: g.groupName, totalPayment: g.totalPayment, amountPaid: g.totalPayment,
    sourceBank: g.preferredSourceBank || '', sourceAccount: g.preferredSourceAccount || '',
    paymentDate: todayISO(),
  }
  showGroupPayModal.value = true
}

async function markGroupPaid() {
  const f = groupPayForm.value
  const ok = await runMutation(() => doMarkGroupPaid({ variables: {
    groupName: f.groupName, amountPaid: f.amountPaid,
    sourceBank: f.sourceBank || null, sourceAccount: f.sourceAccount || null,
    paymentDate: f.paymentDate || null,
  }}), 'markBillGroupPaid', { failMessage: 'Failed to mark group as paid' })
  if (!ok) return
  showGroupPayModal.value = false
  refetchGroups()
  refetch()
  refetchCredit()
  refetchBanks()
}
</script>


