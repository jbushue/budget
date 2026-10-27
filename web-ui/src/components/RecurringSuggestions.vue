<template>
  <div v-if="charges.length" class="card rec-card">
    <div class="card-header">
      <span class="card-title">🔁 Repeating charges that aren't bills yet</span>
      <span class="sub">~{{ currency(totalMonthly) }}/month</span>
    </div>
    <p class="hint">
      Adding them as bills puts them in your projections, so Safe to spend accounts for them.
    </p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Payee</th><th>How often</th><th style="text-align:right">Amount</th><th>Last</th><th>Next expected</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="c in charges" :key="c.key">
            <td>
              <div style="font-weight:500">{{ c.name }}</div>
              <div class="sub">{{ c.description }} · seen {{ c.count }}×</div>
            </td>
            <td>{{ freqLabel(c.frequency) }}</td>
            <td style="text-align:right;white-space:nowrap">
              {{ currency(c.amount) }}
              <div v-if="c.variable" class="sub">{{ currency(c.minAmount) }}–{{ currency(c.maxAmount) }}</div>
            </td>
            <td>{{ fmtDateShort(c.lastDate) }}</td>
            <td>{{ fmtDateShort(c.nextExpected) }}</td>
            <td style="text-align:right;white-space:nowrap">
              <button class="btn btn-primary btn-sm" :disabled="busy" @click="addAsBill(c)">Add as bill</button>
              <button class="btn btn-outline btn-sm" style="margin-left:0.35rem" :disabled="busy" @click="dismiss(c)">Dismiss</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_RECURRING_CHARGES, DISMISS_RECURRING_CHARGE } from '../graphql/goals'
import { CREATE_BILL } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { currency, fmtDateShort } from '../utils/format'
import type { MutationPayload, RecurringCharge } from '../types'

const emit = defineEmits<{ added: [] }>()

const { result, refetch } = useQuery<{ recurringCharges: RecurringCharge[] }>(GET_RECURRING_CHARGES,
  { fetchPolicy: 'network-only' })
const { mutate: dismissM } = useMutation<{ dismissRecurringCharge: MutationPayload }>(DISMISS_RECURRING_CHARGE)
const { mutate: createBill } = useMutation<{ createBill: MutationPayload }>(CREATE_BILL)

const busy = ref(false)
const charges = computed(() => result.value?.recurringCharges ?? [])
const totalMonthly = computed(() => charges.value.reduce((s, c) => s + c.monthlyCost, 0))

const FREQ: Record<string, string> = { weekly: 'Weekly', biweekly: 'Every 2 weeks', monthly: 'Monthly', quarterly: 'Quarterly', yearly: 'Yearly' }
function freqLabel(f: string) { return FREQ[f] ?? f }

async function addAsBill(c: RecurringCharge) {
  const name = prompt('Bill name:', c.name)
  if (!name) return
  busy.value = true
  const next = new Date(c.nextExpected + 'T00:00:00')
  const variables: Record<string, unknown> = {
    billName: name.trim(),
    amount: c.amount,
    dueDate: c.dueDay,
    frequency: c.frequency,
    billType: c.variable ? 'floating' : 'fixed',
  }
  if (c.variable) {
    variables.minAmount = c.minAmount
    variables.maxAmount = c.maxAmount
  }
  if (c.frequency === 'weekly' || c.frequency === 'biweekly') variables.startDate = c.nextExpected
  if (c.frequency === 'quarterly' || c.frequency === 'yearly') variables.dueMonth = next.getMonth() + 1
  const res = await runMutation(() => createBill({ variables }), 'createBill', { failMessage: 'Could not add the bill' })
  busy.value = false
  if (res) {
    refetch()
    emit('added')
  }
}

async function dismiss(c: RecurringCharge) {
  busy.value = true
  const res = await runMutation(() => dismissM({ variables: { key: c.key } }), 'dismissRecurringCharge')
  busy.value = false
  if (res) refetch()
}

defineExpose({ refetch })
</script>

<style scoped>
.rec-card { border-left: 4px solid var(--primary); }
.hint { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.5rem; }
.sub { font-size: 0.78rem; color: var(--text-muted); }
</style>
