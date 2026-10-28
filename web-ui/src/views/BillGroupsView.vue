<template>
  <div>
    <div class="view-header">
      <h2>🎓 Bill Groups</h2>
      <button class="btn btn-primary btn-sm" @click="openCreateGroup()">+ New Group</button>
    </div>

    <div v-if="loading" class="loading">Loading bill groups...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else>
      <div v-if="groups.length === 0" class="empty-state">
        <div class="icon">🎓</div>
        <p>No bill groups yet.</p>
        <p style="font-size:0.85rem;margin-top:0.5rem">
          Create a group to bundle multiple loan accounts into a single payment &mdash;
          perfect for student loans, consolidated bills, or family phone plans.
        </p>
      </div>

      <!-- Group cards -->
      <div v-for="g in groups" :key="g.groupName" class="card" style="margin-bottom:1.25rem">
        <div class="card-header" style="border-bottom:2px solid var(--bg)">
          <div>
            <span class="card-title" style="font-size:1.05rem">{{ groupTypeIcon(g.groupType) }} {{ g.groupName }}</span>
            <span class="badge badge-info" style="margin-left:0.5rem">{{ frequencyLabel(g.frequency) }}</span>
            <span v-if="g.isPaidThisPeriod" class="badge badge-success" style="margin-left:0.35rem">PAID</span>
            <span v-else class="badge badge-warning" style="margin-left:0.35rem">DUE</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.4rem;align-items:center">
            <template v-if="!g.isPaidThisPeriod">
              <button class="btn btn-success btn-sm" @click="openPayGroup(g)">Mark Paid</button>
            </template>
            <button class="btn btn-outline btn-sm" @click="openEditGroup(g)">Edit</button>
            <button class="btn btn-outline btn-sm" @click="openAddMember(g)">+ Member</button>
            <button class="btn btn-danger btn-sm" @click="deleteGroup(g.groupName)">Delete</button>
          </div>
        </div>

        <!-- Summary row -->
        <div class="grid grid-4" style="margin-bottom:1rem">
          <div class="stat-card" style="padding:0.75rem;text-align:center">
            <div class="stat-value" style="font-size:1.25rem">{{ currency(g.totalPayment) }}</div>
            <div class="stat-label">Monthly Payment</div>
          </div>
          <div class="stat-card" style="padding:0.75rem;text-align:center">
            <div class="stat-value negative" style="font-size:1.25rem">{{ currency(g.totalBalance) }}</div>
            <div class="stat-label">Total Balance</div>
          </div>
          <div class="stat-card" style="padding:0.75rem;text-align:center">
            <div class="stat-value" style="font-size:1.25rem">{{ g.memberCount }}</div>
            <div class="stat-label">Sub-Loans</div>
          </div>
          <div class="stat-card" style="padding:0.75rem;text-align:center">
            <div class="stat-value" style="font-size:1.25rem">Day {{ g.dueDate }}</div>
            <div class="stat-label">Due Date</div>
          </div>
        </div>

        <div v-if="g.preferredSourceBank" style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.75rem">
          Pays from: <strong>{{ g.preferredSourceBank }}</strong> / {{ g.preferredSourceAccount }}
        </div>

        <!-- Member accounts table -->
        <div v-if="g.members.length > 0" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Bank</th>
                <th>Account</th>
                <th>APR</th>
                <th style="text-align:right">Balance</th>
                <th>Allocation</th>
                <th style="text-align:right">Est. Payment</th>
                <th style="text-align:right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in g.members" :key="`${m.bankName}:${m.accountName}`">
                <td>{{ m.bankName }}</td>
                <td style="font-weight:500">{{ m.accountName }}</td>
                <td>{{ pct(m.interestRate) }}</td>
                <td style="text-align:right;font-weight:600;color:var(--danger)">{{ currency(m.balance) }}</td>
                <td>
                  <span class="badge badge-info">{{ allocationLabel(m.allocationMethod) }}</span>
                  <span v-if="m.allocationMethod === 'fixed'" style="margin-left:0.25rem;font-size:0.8rem">
                    {{ currency(m.fixedAmount) }}
                  </span>
                </td>
                <td style="text-align:right;font-weight:500">
                  {{ currency(estimatedPayment(g, m)) }}
                </td>
                <td style="text-align:right">
                  <button class="btn btn-danger btn-sm" @click="removeMember(g.groupName, m.bankName, m.accountName)">Remove</button>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr style="font-weight:600">
                <td colspan="3">Total</td>
                <td style="text-align:right;color:var(--danger)">{{ currency(g.totalBalance) }}</td>
                <td></td>
                <td style="text-align:right">{{ currency(g.totalPayment) }}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div v-else style="color:var(--text-muted);font-size:0.85rem;padding:1rem 0">
          No member accounts yet. Click "+ Member" to add credit/loan accounts.
        </div>
      </div>
    </template>

    <!-- Create / Edit Group Modal -->
    <div v-if="showGroupModal" class="modal-overlay" @click.self="showGroupModal = false">
      <div class="modal">
        <h3>{{ editingGroup ? 'Edit Bill Group' : 'Create Bill Group' }}</h3>
        <div class="form-group">
          <label>Group Name</label>
          <input v-model="groupForm.groupName" placeholder='e.g. "Federal Student Loans"' :disabled="!!editingGroup" />
        </div>
        <div class="form-group">
          <label>Total Monthly Payment</label>
          <input v-model.number="groupForm.totalPayment" type="number" step="0.01" />
        </div>
        <div class="form-group">
          <label>Due Day (1-31)</label>
          <input v-model.number="groupForm.dueDate" type="number" min="1" max="31" />
        </div>
        <div class="form-group">
          <label>Frequency</label>
          <select v-model="groupForm.frequency">
            <option value="monthly">Monthly</option>
            <option value="biweekly">Bi-weekly</option>
            <option value="quarterly">Quarterly</option>
          </select>
        </div>
        <div class="form-group">
          <label>Group Type</label>
          <select v-model="groupForm.groupType">
            <option value="student_loan">Student Loan</option>
            <option value="bundled_bill">Bundled Bill</option>
            <option value="consolidated_loan">Consolidated Loan</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div class="form-group">
          <label>Payment Source Bank</label>
          <select v-model="groupForm.preferredSourceBank">
            <option value="">Auto (no preference)</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Payment Source Account</label>
          <select v-model="groupForm.preferredSourceAccount" :disabled="!groupForm.preferredSourceBank">
            <option value="">Auto (no preference)</option>
            <option v-for="acc in bankAccountsFor(groupForm.preferredSourceBank)" :key="acc.name" :value="acc.name">
              {{ acc.name }} ({{ acc.type }})
            </option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showGroupModal = false">Cancel</button>
          <button class="btn btn-primary" @click="saveGroup" :disabled="!groupForm.groupName || !groupForm.totalPayment">
            {{ editingGroup ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add Member Modal -->
    <div v-if="showMemberModal" class="modal-overlay" @click.self="showMemberModal = false">
      <div class="modal">
        <h3>Add Account to "{{ memberForm.groupName }}"</h3>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Select a credit / loan account to include in this bundled payment.
        </p>
        <div class="form-group">
          <label>Bank</label>
          <select v-model="memberForm.bankName" @change="memberForm.accountName = ''">
            <option value="">Select bank...</option>
            <option v-for="b in banksWithCredit" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Credit / Loan Account</label>
          <select v-model="memberForm.accountName" :disabled="!memberForm.bankName">
            <option value="">Select account...</option>
            <option
              v-for="acc in creditAccountsFor(memberForm.bankName)"
              :key="acc.accountName"
              :value="acc.accountName"
            >
              {{ acc.accountName }} ({{ currency(acc.balance) }} @ {{ pct(acc.interestRate) }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>Allocation Method</label>
          <select v-model="memberForm.allocationMethod">
            <option value="proportional">Proportional (by balance)</option>
            <option value="equal">Equal split</option>
            <option value="fixed">Fixed amount</option>
          </select>
        </div>
        <div v-if="memberForm.allocationMethod === 'fixed'" class="form-group">
          <label>Fixed Amount Per Period</label>
          <input v-model.number="memberForm.fixedAmount" type="number" step="0.01" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showMemberModal = false">Cancel</button>
          <button class="btn btn-primary" @click="addMember" :disabled="!memberForm.bankName || !memberForm.accountName">
            Add to Group
          </button>
        </div>
      </div>
    </div>

    <!-- Mark Paid Modal -->
    <div v-if="showPayModal" class="modal-overlay" @click.self="showPayModal = false">
      <div class="modal">
        <h3>Pay "{{ payForm.groupName }}"</h3>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
          Scheduled payment: {{ currency(payForm.totalPayment) }} &mdash; distributed across member accounts.
        </p>
        <div class="form-group">
          <label>Amount Paid</label>
          <input v-model.number="payForm.amountPaid" type="number" step="0.01" />
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
            <option v-for="acc in bankAccountsFor(payForm.sourceBank)" :key="acc.name" :value="acc.name">
              {{ acc.name }} ({{ acc.type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>Payment Date</label>
          <input v-model="payForm.paymentDate" type="date" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showPayModal = false">Cancel</button>
          <button class="btn btn-success" @click="markGroupPaid" :disabled="!payForm.amountPaid || payForm.amountPaid <= 0">Mark Paid</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import {
  GET_ALL_BILL_GROUPS, GET_ALL_BANKS,
  CREATE_BILL_GROUP, UPDATE_BILL_GROUP, DELETE_BILL_GROUP,
  ADD_BILL_GROUP_MEMBER, REMOVE_BILL_GROUP_MEMBER,
  MARK_BILL_GROUP_PAID,
} from '../graphql/queries'
import { currency, pct, frequencyLabel, todayISO } from '../utils/format'
import { runMutation } from '../utils/mutation'
import type { BillGroup, BillGroupMember, Bank, CreditAccount, MutationPayload } from '../types'

// ── Data ──
const { result, loading, error, refetch } = useQuery<{ allBillGroups: BillGroup[] }>(GET_ALL_BILL_GROUPS)
const groups = computed(() => result.value?.allBillGroups ?? [])

const { result: banksResult, refetch: refetchBanks } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const banks = computed(() => banksResult.value?.allBanks ?? [])
const banksWithCredit = computed(() => banks.value.filter(b => b.creditAccounts.length > 0))

function bankAccountsFor(bankName: string) {
  if (!bankName) return []
  const bank = banks.value.find(b => b.name === bankName)
  if (!bank) return []
  return bank.bankAccounts.map(a => ({ name: a.accountName, type: a.accountType }))
}

function creditAccountsFor(bankName: string): CreditAccount[] {
  if (!bankName) return []
  const bank = banks.value.find(b => b.name === bankName)
  return bank?.creditAccounts ?? []
}

function groupTypeIcon(t: string): string {
  const map: Record<string, string> = {
    student_loan: '🎓',
    bundled_bill: '📦',
    consolidated_loan: '🏦',
    other: '📋',
  }
  return map[t] || '📋'
}

function allocationLabel(method: string): string {
  const map: Record<string, string> = {
    proportional: 'Proportional',
    equal: 'Equal',
    fixed: 'Fixed',
  }
  return map[method] || method
}

/**
 * Mirror of the backend allocation (models/bill_group.py _compute_allocations):
 * fixed members are paid first (scaled down proportionally if they exceed the
 * total), then the remainder is split among the other members — equally among
 * members with a balance if they all use "equal", otherwise by balance.
 */
function computeAllocations(group: BillGroup): number[] {
  const members = group.members
  const alloc = members.map(() => 0)
  const total = Math.max(group.totalPayment, 0)

  const fixedIdx = members.map((m, i) => (m.allocationMethod === 'fixed' ? i : -1)).filter(i => i >= 0)
  const otherIdx = members.map((m, i) => (m.allocationMethod !== 'fixed' ? i : -1)).filter(i => i >= 0)

  const fixedTotal = fixedIdx.reduce((s, i) => s + Math.max(members[i].fixedAmount || 0, 0), 0)
  const scale = fixedTotal > total && fixedTotal > 0 ? total / fixedTotal : 1
  for (const i of fixedIdx) alloc[i] = Math.max(members[i].fixedAmount || 0, 0) * scale
  const remaining = Math.max(total - fixedTotal * scale, 0)

  if (otherIdx.length === 0 || remaining <= 0) return alloc

  const allEqual = otherIdx.every(i => members[i].allocationMethod === 'equal')
  if (allEqual) {
    const payable = otherIdx.filter(i => members[i].balance > 0)
    if (payable.length === 0) return alloc
    const per = remaining / payable.length
    for (const i of payable) alloc[i] = per
    return alloc
  }

  const totalBal = otherIdx.reduce((s, i) => s + Math.max(members[i].balance, 0), 0)
  for (const i of otherIdx) {
    alloc[i] = totalBal > 0
      ? (Math.max(members[i].balance, 0) / totalBal) * remaining
      : remaining / otherIdx.length
  }
  return alloc
}

const allocationsByGroup = computed(() => {
  const map = new Map<string, number[]>()
  for (const g of groups.value) map.set(g.groupName, computeAllocations(g))
  return map
})

function estimatedPayment(group: BillGroup, member: BillGroupMember): number {
  const idx = group.members.indexOf(member)
  return allocationsByGroup.value.get(group.groupName)?.[idx] ?? 0
}

// ── Create / Edit Group ──
const showGroupModal = ref(false)
const editingGroup = ref<string | null>(null)
const groupForm = ref({
  groupName: '',
  totalPayment: 0,
  dueDate: 1,
  frequency: 'monthly',
  groupType: 'student_loan',
  preferredSourceBank: '',
  preferredSourceAccount: '',
})

// Only clear the account when it doesn't belong to the chosen bank, so that
// populating the form from Edit doesn't wipe the saved preference.
function keepAccountIfValid(bankName: string, account: string): string {
  if (!account || !bankName) return ''
  if (banks.value.length === 0) return account
  return bankAccountsFor(bankName).some(a => a.name === account) ? account : ''
}

watch(() => groupForm.value.preferredSourceBank, (newVal) => {
  groupForm.value.preferredSourceAccount = keepAccountIfValid(newVal, groupForm.value.preferredSourceAccount)
})

function openCreateGroup() {
  editingGroup.value = null
  groupForm.value = { groupName: '', totalPayment: 0, dueDate: 1, frequency: 'monthly', groupType: 'student_loan', preferredSourceBank: '', preferredSourceAccount: '' }
  showGroupModal.value = true
}

function openEditGroup(g: BillGroup) {
  editingGroup.value = g.groupName
  groupForm.value = {
    groupName: g.groupName,
    totalPayment: g.totalPayment,
    dueDate: g.dueDate,
    frequency: g.frequency,
    groupType: g.groupType,
    preferredSourceBank: g.preferredSourceBank || '',
    preferredSourceAccount: g.preferredSourceAccount || '',
  }
  showGroupModal.value = true
}

const { mutate: doCreateGroup } = useMutation<{ createBillGroup: MutationPayload }>(CREATE_BILL_GROUP)
const { mutate: doUpdateGroup } = useMutation<{ updateBillGroup: MutationPayload }>(UPDATE_BILL_GROUP)
const { mutate: doDeleteGroup } = useMutation<{ deleteBillGroup: MutationPayload }>(DELETE_BILL_GROUP)

async function saveGroup() {
  const vars = {
    groupName: groupForm.value.groupName,
    totalPayment: groupForm.value.totalPayment,
    dueDate: groupForm.value.dueDate,
    frequency: groupForm.value.frequency,
    groupType: groupForm.value.groupType,
    preferredSourceBank: groupForm.value.preferredSourceBank || null,
    preferredSourceAccount: groupForm.value.preferredSourceAccount || null,
  }
  const ok = editingGroup.value
    ? await runMutation(() => doUpdateGroup({ variables: vars }), 'updateBillGroup', { failMessage: 'Failed to update group' })
    : await runMutation(() => doCreateGroup({ variables: vars }), 'createBillGroup', { failMessage: 'Failed to create group' })
  if (!ok) return
  showGroupModal.value = false
  refetch()
}

async function deleteGroup(name: string) {
  if (!confirm(`Delete bill group "${name}" and unlink all member accounts?`)) return
  const ok = await runMutation(() => doDeleteGroup({ variables: { groupName: name }}), 'deleteBillGroup', { failMessage: 'Failed to delete group' })
  if (ok) refetch()
}

// ── Add / Remove Members ──
const showMemberModal = ref(false)
const memberForm = ref({ groupName: '', bankName: '', accountName: '', allocationMethod: 'proportional', fixedAmount: 0 })

function openAddMember(g: BillGroup) {
  memberForm.value = { groupName: g.groupName, bankName: '', accountName: '', allocationMethod: 'proportional', fixedAmount: 0 }
  showMemberModal.value = true
}

const { mutate: doAddMember } = useMutation<{ addBillGroupMember: MutationPayload }>(ADD_BILL_GROUP_MEMBER)
const { mutate: doRemoveMember } = useMutation<{ removeBillGroupMember: MutationPayload }>(REMOVE_BILL_GROUP_MEMBER)

async function addMember() {
  const ok = await runMutation(() => doAddMember({ variables: {
    groupName: memberForm.value.groupName,
    bankName: memberForm.value.bankName,
    accountName: memberForm.value.accountName,
    allocationMethod: memberForm.value.allocationMethod,
    fixedAmount: memberForm.value.fixedAmount,
  }}), 'addBillGroupMember', { failMessage: 'Failed to add member' })
  if (!ok) return
  showMemberModal.value = false
  refetch()
}

async function removeMember(groupName: string, bankName: string, accountName: string) {
  if (!confirm(`Remove "${accountName}" from this group?`)) return
  const ok = await runMutation(
    () => doRemoveMember({ variables: { groupName, bankName, accountName }}),
    'removeBillGroupMember', { failMessage: 'Failed to remove member' },
  )
  if (ok) refetch()
}

// ── Mark Paid ──
const { mutate: doMarkPaid } = useMutation<{ markBillGroupPaid: MutationPayload }>(MARK_BILL_GROUP_PAID)
const showPayModal = ref(false)
const payForm = ref({ groupName: '', totalPayment: 0, amountPaid: 0, sourceBank: '', sourceAccount: '', paymentDate: '' })

watch(() => payForm.value.sourceBank, (newVal) => {
  payForm.value.sourceAccount = keepAccountIfValid(newVal, payForm.value.sourceAccount)
})

function openPayGroup(g: BillGroup) {
  payForm.value = {
    groupName: g.groupName, totalPayment: g.totalPayment, amountPaid: g.totalPayment,
    sourceBank: g.preferredSourceBank || '', sourceAccount: g.preferredSourceAccount || '',
    paymentDate: todayISO(),
  }
  showPayModal.value = true
}

async function markGroupPaid() {
  const f = payForm.value
  const ok = await runMutation(() => doMarkPaid({ variables: {
    groupName: f.groupName, amountPaid: f.amountPaid,
    sourceBank: f.sourceBank || null, sourceAccount: f.sourceAccount || null,
    paymentDate: f.paymentDate || null,
  }}), 'markBillGroupPaid', { failMessage: 'Failed to mark group as paid' })
  if (!ok) return
  showPayModal.value = false
  refetch()
  refetchBanks()
}
</script>

