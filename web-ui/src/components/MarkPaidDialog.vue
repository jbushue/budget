<template>
  <div v-if="bill" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="max-width:440px">
      <h3 style="margin-top:0">Mark "{{ bill.name }}" paid</h3>
      <div class="form-group">
        <label>Amount</label>
        <input v-model.number="amount" type="number" step="0.01" min="0" />
      </div>
      <div class="form-group">
        <label>Date paid</label>
        <input v-model="paidOn" type="date" />
      </div>
      <div class="form-group">
        <label>Paid from</label>
        <select v-model="source">
          <option value="">{{ bill.sourceAccount ? `Usual account (${bill.sourceAccount})` : 'Usual account' }}</option>
          <option v-for="a in accounts" :key="a.key" :value="a.key">{{ a.label }}</option>
        </select>
      </div>
      <label style="display:flex;gap:0.5rem;align-items:flex-start;font-size:0.85rem;margin-bottom:0.75rem;cursor:pointer">
        <input v-model="moveMoney" type="checkbox" style="width:auto;margin-top:0.15rem" />
        <span>
          Take the money out of the account in this app now
          <span style="display:block;color:var(--text-muted);font-size:0.78rem">
            Leave this off if your balances are already up to date (e.g. synced with your bank), or the payment would be counted twice.
          </span>
        </span>
      </label>
      <div class="modal-actions">
        <button class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="saving || !(amount >= 0)" @click="save">{{ saving ? 'Saving...' : 'Mark paid' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMutation, useQuery } from '@vue/apollo-composable'
import { GET_ALL_BANKS, GET_SIMPLEFIN_SYNCED_ACCOUNTS, MARK_BILL_PAID } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { todayISO } from '../utils/format'
import type { Bank, MutationPayload, SimplefinSyncedAccount } from '../types'

/** Minimal bill info the dialog needs. */
export interface PayableBill {
  name: string
  billName: string
  amount: number
  sourceAccount?: string
}

const props = defineProps<{ bill: PayableBill | null }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'paid'): void }>()

const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const { result: syncedResult } = useQuery<{ simplefinSyncedAccounts: SimplefinSyncedAccount[] }>(GET_SIMPLEFIN_SYNCED_ACCOUNTS)
const { mutate: markPaid } = useMutation<{ markBillPaid: MutationPayload }>(MARK_BILL_PAID)

const accounts = computed(() => {
  const out: { key: string; label: string }[] = []
  for (const b of banksResult.value?.allBanks ?? []) {
    for (const a of b.bankAccounts) out.push({ key: `${b.name}:${a.accountName}`, label: `${a.accountName} (${b.name})` })
    for (const c of b.creditAccounts) out.push({ key: `${b.name}:${c.accountName}`, label: `${c.accountName} (${b.name}, card)` })
  }
  return out
})

const synced = computed(() => new Set((syncedResult.value?.simplefinSyncedAccounts ?? [])
  .map(s => `${s.bankName}:${s.accountName}`)))

const amount = ref(0)
const paidOn = ref(todayISO())
const source = ref('')
const moveMoney = ref(true)
const saving = ref(false)

watch(() => props.bill, b => {
  if (!b) return
  amount.value = Math.round(b.amount * 100) / 100
  paidOn.value = todayISO()
  source.value = ''
  // Synced accounts already show real payments, so default to "record only"
  moveMoney.value = synced.value.size === 0
}, { immediate: true })

async function save() {
  if (!props.bill) return
  saving.value = true
  const [sourceBank, sourceAccount] = source.value ? source.value.split(/:(.*)/s) : [null, null]
  const ok = await runMutation(() => markPaid({ variables: {
    billName: props.bill!.billName,
    amountPaid: amount.value,
    paymentDate: paidOn.value,
    sourceBank, sourceAccount,
    moveMoney: moveMoney.value,
  } }), 'markBillPaid', { failMessage: 'Could not mark the bill paid' })
  saving.value = false
  if (ok) {
    emit('paid')
    emit('close')
  }
}
</script>
