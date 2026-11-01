<template>
  <div v-if="open" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="max-width:480px">
      <h3>Move money</h3>
      <p class="muted" style="font-size:0.85rem;margin:-0.25rem 0 1rem">
        Record a transfer between your checking and savings accounts, at the same bank or different ones.
      </p>
      <div class="form-group">
        <label>From</label>
        <select v-model="from">
          <option value="">Choose an account...</option>
          <option v-for="a in cashAccounts" :key="a.key" :value="a.key">{{ a.label }} · {{ currency(a.balance) }}</option>
        </select>
      </div>
      <div class="swap-row">
        <button class="btn btn-ghost btn-icon btn-sm" title="Swap" aria-label="Swap from and to" @click="swap">
          <Icon name="repeat" :size="15" />
        </button>
      </div>
      <div class="form-group">
        <label>To</label>
        <select v-model="to">
          <option value="">Choose an account...</option>
          <option v-for="a in cashAccounts" :key="a.key" :value="a.key" :disabled="a.key === from">{{ a.label }} · {{ currency(a.balance) }}</option>
        </select>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Amount</label>
          <input v-model.number="amount" type="number" min="0" step="0.01" placeholder="0.00" />
          <small v-if="fromAcc && (amount ?? 0) > fromAcc.balance" class="field-error">Only {{ currency(fromAcc.balance) }} available</small>
        </div>
        <div class="form-group">
          <label>Note (optional)</label>
          <input v-model="note" placeholder="e.g. Emergency fund" />
        </div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="!canSave || saving" @click="save">{{ saving ? 'Moving...' : 'Move money' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import Icon from './Icon.vue'
import { TRANSFER_MONEY } from '../graphql/tools'
import { runMutation } from '../utils/mutation'
import { currency } from '../utils/format'
import type { Bank, MutationPayload } from '../types'

const props = defineProps<{ open: boolean; banks: Bank[] }>()
const emit = defineEmits<{ close: []; done: [] }>()

const from = ref('')
const to = ref('')
const amount = ref<number | null>(null)
const note = ref('')
const saving = ref(false)

const cashAccounts = computed(() => props.banks.flatMap(b => b.bankAccounts.map(a => ({
  key: `${b.name}\u0000${a.accountName}`, bank: b.name, account: a.accountName,
  label: `${b.name} · ${a.accountName}`, balance: a.balance,
}))))
const fromAcc = computed(() => cashAccounts.value.find(a => a.key === from.value))
const toAcc = computed(() => cashAccounts.value.find(a => a.key === to.value))
const canSave = computed(() => !!fromAcc.value && !!toAcc.value && from.value !== to.value
  && (amount.value ?? 0) > 0 && (amount.value ?? 0) <= (fromAcc.value?.balance ?? 0))

function pickDefaults() {
  if (!cashAccounts.value.some(a => a.key === from.value)) from.value = cashAccounts.value[0]?.key ?? ''
  if (!cashAccounts.value.some(a => a.key === to.value) || to.value === from.value) {
    to.value = cashAccounts.value.find(a => a.key !== from.value)?.key ?? ''
  }
}
watch(() => props.open, isOpen => {
  if (!isOpen) return
  from.value = ''
  to.value = ''
  amount.value = null
  note.value = ''
  pickDefaults()
})
// Opened before the accounts loaded (e.g. from a link): pick defaults when they arrive
watch(cashAccounts, () => { if (props.open) pickDefaults() })

function swap() {
  [from.value, to.value] = [to.value, from.value]
}

const { mutate } = useMutation<{ transferMoney: MutationPayload }>(TRANSFER_MONEY)

async function save() {
  if (!fromAcc.value || !toAcc.value) return
  saving.value = true
  const ok = await runMutation(() => mutate({ variables: { fromBank: fromAcc.value!.bank, fromAccount: fromAcc.value!.account,
    toBank: toAcc.value!.bank, toAccount: toAcc.value!.account, amount: amount.value ?? 0, note: note.value } }),
  'transferMoney', { failMessage: 'Could not move the money', showSuccess: true })
  saving.value = false
  if (ok) { emit('done'); emit('close') }
}
</script>

<style scoped>
.swap-row { display: flex; justify-content: center; margin: -0.6rem 0 -0.3rem; }
.field-error { color: var(--danger-text); font-size: 0.78rem; }
</style>
