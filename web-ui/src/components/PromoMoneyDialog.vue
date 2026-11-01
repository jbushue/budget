<template>
  <div v-if="open" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="max-width:460px">
      <h3>{{ mode === 'purchase' ? 'Add a purchase' : 'Pay down promo' }}</h3>
      <p class="muted" style="font-size:0.85rem;margin:-0.25rem 0 1rem">
        <strong>{{ promoName }}</strong> on {{ accountName }} · {{ currency(promoBalance) }} on this promo
      </p>
      <div class="form-group">
        <label>Amount</label>
        <input v-model.number="amount" type="number" min="0" step="0.01" placeholder="0.00" />
        <small v-if="mode === 'pay' && promoBalance > 0" class="muted">
          <a href="#" @click.prevent="amount = promoBalance">Pay it all ({{ currency(promoBalance) }})</a>
        </small>
      </div>
      <div v-if="mode === 'purchase'" class="form-group">
        <label>What was it? (optional)</label>
        <input v-model="description" placeholder="e.g. New laptop" />
      </div>
      <div v-else class="form-group">
        <label>Paid from</label>
        <select v-model="source">
          <option value="">Choose an account...</option>
          <option v-for="a in cashAccounts" :key="a.key" :value="a.key">{{ a.label }} · {{ currency(a.balance) }}</option>
        </select>
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="!canSave || saving" @click="save">
          {{ saving ? 'Saving...' : mode === 'purchase' ? 'Add purchase' : 'Make payment' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import { PAY_PROMO_BALANCE, RECORD_PROMO_PURCHASE } from '../graphql/tools'
import { runMutation } from '../utils/mutation'
import { currency } from '../utils/format'
import type { Bank, MutationPayload } from '../types'

const props = defineProps<{
  open: boolean; mode: 'purchase' | 'pay'; bankName: string; accountName: string
  promoName: string; promoBalance: number; banks: Bank[]
}>()
const emit = defineEmits<{ close: []; done: [] }>()

const amount = ref<number | null>(null)
const description = ref('')
const source = ref('')
const saving = ref(false)

const cashAccounts = computed(() => props.banks.flatMap(b => b.bankAccounts.map(a => ({
  key: `${b.name}\u0000${a.accountName}`, bank: b.name, account: a.accountName, label: `${b.name} · ${a.accountName}`, balance: a.balance,
}))))
const src = computed(() => cashAccounts.value.find(a => a.key === source.value))
const canSave = computed(() => (amount.value ?? 0) > 0 && (props.mode === 'purchase' || !!src.value))

watch(() => props.open, isOpen => {
  if (!isOpen) return
  amount.value = null
  description.value = ''
  source.value = cashAccounts.value.find(a => a.label.toLowerCase().includes('checking'))?.key ?? cashAccounts.value[0]?.key ?? ''
})

const { mutate: buyM } = useMutation<{ recordPromoPurchase: MutationPayload }>(RECORD_PROMO_PURCHASE)
const { mutate: payM } = useMutation<{ payPromoBalance: MutationPayload }>(PAY_PROMO_BALANCE)

async function save() {
  saving.value = true
  const base = { bankName: props.bankName, accountName: props.accountName, promoName: props.promoName, amount: amount.value ?? 0 }
  const ok = props.mode === 'purchase'
    ? await runMutation(() => buyM({ variables: { ...base, description: description.value } }), 'recordPromoPurchase',
      { failMessage: 'Could not add the purchase', showSuccess: true })
    : await runMutation(() => payM({ variables: { ...base, sourceBank: src.value!.bank, sourceAccount: src.value!.account } }),
      'payPromoBalance', { failMessage: 'Could not make the payment', showSuccess: true })
  saving.value = false
  if (ok) { emit('done'); emit('close') }
}
</script>
