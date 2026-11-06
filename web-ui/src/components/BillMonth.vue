<template>
  <div>
    <div class="month-bar">
      <MonthSwitcher v-model="month" :min="data?.firstMonth" :max="lastMonth" />
      <span class="muted" style="font-size:0.82rem">Pay ahead, catch up on a missed month, or skip one — the plan only counts what's still owed.</span>
    </div>

    <div v-if="loading && !data" class="loading">Loading {{ monthLabel }}...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="data">
      <div class="grid grid-4" style="margin-bottom:1rem">
        <div class="stat-card">
          <div class="stat-value">{{ currency(data.totals.due) }}</div>
          <div class="stat-label">Due in {{ monthShort }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:var(--success)">{{ currency(data.totals.paid) }}</div>
          <div class="stat-label">Paid</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ currency(data.totals.remaining) }}</div>
          <div class="stat-label">Left to pay</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" :style="data.totals.overdue > 0 ? 'color:var(--danger)' : ''">{{ currency(data.totals.overdue) }}</div>
          <div class="stat-label">Overdue</div>
        </div>
      </div>

      <div v-if="data.overdueBefore > 0" class="card notice">
        <Icon name="alertCircle" :size="16" />
        <span>{{ currency(data.overdueBefore) }} is still owed from earlier months.</span>
        <button class="btn btn-ghost btn-sm" @click="goBack">Go back a month</button>
      </div>

      <div v-if="!data.occurrences.length" class="empty-state">
        <div class="icon"><Icon name="calendar" :size="26" /></div>
        <p>Nothing is due in {{ monthLabel }}.</p>
      </div>

      <div v-else class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Due</th>
                <th>Bill</th>
                <th style="text-align:right">Amount</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="o in data.occurrences" :key="o.billName + o.dueDate" :class="{ settled: settled(o) }">
                <td style="white-space:nowrap">{{ fmtDateShort(o.dueDate) }}</td>
                <td>
                  <div style="font-weight:500">{{ o.displayName }}</div>
                  <div class="muted" style="font-size:0.72rem">{{ o.kindLabel || KIND_LABELS[o.kind] }}<template v-if="o.sourceAccount"> · from {{ o.sourceAccount }}</template></div>
                </td>
                <td style="text-align:right;white-space:nowrap">
                  <div style="font-weight:600">{{ currency(o.amount) }}</div>
                  <div v-if="o.isFloating" class="muted" style="font-size:0.72rem">{{ o.hasActualAmount ? 'actual amount' : 'estimate' }}</div>
                </td>
                <td>
                  <span class="badge" :class="badge(o).cls">{{ badge(o).text }}</span>
                  <div v-if="o.paid > 0" class="muted" style="font-size:0.72rem">
                    {{ currency(o.paid) }} paid<template v-if="o.paidOn"> {{ fmtDateShort(o.paidOn) }}</template><template v-if="o.status === 'partial'"> · {{ currency(o.remaining) }} left</template>
                  </div>
                </td>
                <td style="text-align:right;white-space:nowrap">
                  <button v-if="payable(o)" class="btn btn-success btn-sm" @click="openPay(o)">{{ o.status === 'partial' ? 'Pay rest' : 'Pay' }}</button>
                  <RowMenu :items="[
                    { label: 'Set this month\'s amount', icon: 'pencil', hidden: !o.isFloating || settled(o), action: () => emit('setAmount', o) },
                    { label: 'Undo payment', icon: 'refresh', hidden: !o.payments.length, action: () => undo(o) },
                    { label: 'Skip (not owed)', icon: 'x', hidden: settled(o) || o.status === 'partial', action: () => skip(o, true) },
                    { label: 'Owed after all', icon: 'refresh', hidden: o.status !== 'skipped', action: () => skip(o, false) },
                  ]" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <MarkPaidDialog :bill="paying" @close="paying = null" @paid="changed" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery } from '@vue/apollo-composable'
import Icon from './Icon.vue'
import RowMenu from './RowMenu.vue'
import MonthSwitcher from './MonthSwitcher.vue'
import MarkPaidDialog, { type PayableBill } from './MarkPaidDialog.vue'
import { GET_BILL_MONTH, SKIP_BILL_OCCURRENCE, UNDO_BILL_PAYMENT } from '../graphql/queries'
import { currency, fmtDate, fmtDateShort, todayISO } from '../utils/format'
import { runMutation } from '../utils/mutation'
import { ask } from '../utils/dialog'
import { planDays } from '../utils/plan'
import type { BillMonth, BillOccurrence, MutationPayload } from '../types'

const emit = defineEmits<{ (e: 'setAmount', o: BillOccurrence): void; (e: 'changed'): void }>()

const KIND_LABELS: Record<BillOccurrence['kind'], string> = {
  bill: 'Bill', floating: 'Variable bill', credit: 'Card payment', mortgage: 'Mortgage', heloc: 'HELOC', group: 'Loan group',
}

// The month lives in the URL (?month=2026-11) so it survives a refresh and the back button
const route = useRoute()
const router = useRouter()
const thisMonth = todayISO().slice(0, 7)
const month = computed({
  get: () => (typeof route.query.month === 'string' && /^\d{4}-\d{2}$/.test(route.query.month) ? route.query.month : thisMonth),
  set: (m: string) => { router.replace({ query: { ...route.query, month: m === thisMonth ? undefined : m } }) },
})

function shiftMonth(m: string, by: number): string {
  const [y, mo] = m.split('-').map(Number)
  const d = new Date(y, mo - 1 + by, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function goBack() {
  month.value = shiftMonth(month.value, -1)
}

const { result, loading, error, refetch } = useQuery<{ billMonth: BillMonth }>(GET_BILL_MONTH, () => ({ variables: { month: month.value } }))
const data = computed(() => result.value?.billMonth ?? null)

// Forward as far as the plan looks (Timeline / Plan "how far ahead"), and never past what the server allows
const lastMonth = computed(() => {
  const end = new Date()
  end.setDate(end.getDate() + planDays.value)
  const byPlan = todayISO(end).slice(0, 7)
  const server = data.value?.lastMonth
  const latest = server && server < byPlan ? server : byPlan
  return latest < thisMonth ? thisMonth : latest
})
// Keep the month in range if the plan gets shorter
watch(lastMonth, last => { if (month.value > last) month.value = last })

const monthLabel = computed(() => {
  const [y, m] = month.value.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' })
})
const monthShort = computed(() => monthLabel.value.split(' ')[0])

function settled(o: BillOccurrence): boolean {
  return o.status === 'paid' || o.status === 'skipped' || o.status === 'none'
}
function payable(o: BillOccurrence): boolean {
  return !settled(o)
}

function badge(o: BillOccurrence): { text: string; cls: string } {
  switch (o.status) {
    case 'paid': return { text: 'Paid', cls: 'badge-success' }
    case 'partial': return { text: o.dueDate < todayISO() ? 'Partly paid · late' : 'Partly paid', cls: 'badge-warning' }
    case 'skipped': return { text: 'Skipped', cls: '' }
    case 'none': return { text: 'Nothing due', cls: '' }
    case 'overdue': return { text: 'Overdue', cls: 'badge-danger' }
    case 'untracked': return { text: 'Not tracked', cls: '' }
  }
  const days = Math.round((Date.parse(o.dueDate) - Date.parse(todayISO())) / 86400000)
  if (days === 0) return { text: 'Due today', cls: 'badge-warning' }
  if (days <= 7) return { text: `Due in ${days} day${days === 1 ? '' : 's'}`, cls: 'badge-warning' }
  return { text: 'Upcoming', cls: 'badge-info' }
}

// ── Actions ──
const paying = ref<PayableBill | null>(null)
function openPay(o: BillOccurrence) {
  paying.value = {
    name: o.displayName, billName: o.billName, amount: o.status === 'partial' ? o.remaining : o.amount,
    sourceAccount: o.sourceAccount, dueDate: o.dueDate,
  }
}

const { mutate: doUndo } = useMutation<{ undoBillPayment: MutationPayload }>(UNDO_BILL_PAYMENT)
const { mutate: doSkip } = useMutation<{ skipBillOccurrence: MutationPayload }>(SKIP_BILL_OCCURRENCE)

async function undo(o: BillOccurrence) {
  const moved = o.payments.some(p => p.movedMoney)
  const msg = `Remove the ${currency(o.paid)} recorded for ${o.displayName} (due ${fmtDate(o.dueDate)})?`
    + (moved ? ' The money the app took out goes back to the account it came from.' : '')
  if (!(await ask(msg, { title: 'Undo payment' }))) return
  const ok = await runMutation(() => doUndo({ variables: { billName: o.billName, dueDate: o.dueDate } }),
    'undoBillPayment', { failMessage: 'Could not undo the payment', showSuccess: true })
  if (ok) changed()
}

async function skip(o: BillOccurrence, on: boolean) {
  const ok = await runMutation(() => doSkip({ variables: { billName: o.billName, dueDate: o.dueDate, skip: on } }),
    'skipBillOccurrence', { failMessage: 'Could not update the bill' })
  if (ok) changed()
}

function changed() {
  refetch()
  emit('changed')
}

// Payments made elsewhere (dashboard, bank matches) show up through the
// app-wide refresh (utils/refresh.ts)

defineExpose({ refetch })
</script>

<style scoped>
.month-bar { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }
.notice { display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 0.9rem; margin-bottom: 1rem; color: var(--danger-text); }
.notice .btn { margin-left: auto; }
tr.settled td { opacity: 0.7; }
</style>
