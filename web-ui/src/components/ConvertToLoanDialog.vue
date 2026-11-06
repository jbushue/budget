<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="max-width:480px">
      <h3>Convert to a loan: {{ card.accountName }}</h3>
      <p class="help">
        For a loan that was entered as a card. It keeps its name, bank, balance ({{ currency(card.balance) }}),
        {{ pct(card.interestRate) }} APR, due day and loan group, and is paid like a loan from now on: a fixed
        payment instead of a card minimum, with no credit limit.
      </p>
      <div class="form-group">
        <label>Kind of loan</label>
        <select v-model="form.kind">
          <option v-for="k in KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
      </div>
      <div class="form-group">
        <label class="inline"><input v-model="form.keepPayment" type="radio" :value="true" /> Keep about today's payment ({{ currency(minimum) }})</label>
        <label class="inline"><input v-model="form.keepPayment" type="radio" :value="false" /> Set the months left</label>
        <input v-if="!form.keepPayment" v-model.number="form.months" type="number" min="1" max="600" step="1" style="max-width:8rem" />
        <small class="muted">{{ outcome }}</small>
      </div>
      <template v-if="form.kind === 'student'">
        <div class="form-group">
          <label>Payments start (optional)</label>
          <input v-model="form.paymentsStart" type="date" />
          <small class="muted">If it's in school, grace or deferment: nothing is due before this date.</small>
        </div>
        <div v-if="form.paymentsStart" class="form-group">
          <label class="inline"><input v-model="form.subsidized" type="checkbox" /> Subsidized (no interest until then)</label>
        </div>
      </template>
      <div class="modal-actions">
        <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="saving || !!problem" :title="problem" @click="convert">Convert</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import { CONVERT_CREDIT_TO_LOAN } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { currency, pct } from '../utils/format'
import { LOAN_KINDS, amortized, termForPayment } from '../utils/loans'
import type { CreditAccount, LoanKind, MutationPayload } from '../types'

const props = defineProps<{ bankName: string; card: CreditAccount }>()
const emit = defineEmits<{ close: []; done: [] }>()

const KINDS = LOAN_KINDS.filter(k => k.value !== 'mortgage')
const minimum = props.card.minimumPayment ?? 0
const form = reactive({
  kind: 'student' as LoanKind, keepPayment: true, months: 120 as number | string,
  paymentsStart: '', subsidized: false,
})

const keptTerm = computed(() => termForPayment(props.card.balance, props.card.interestRate, minimum))
const months = computed(() => (form.keepPayment ? keptTerm.value : Math.trunc(Number(form.months)) || null))
const problem = computed(() => {
  if (!(props.card.balance > 0)) return 'Nothing is owed on this account'
  if (form.keepPayment && keptTerm.value == null) return `${currency(minimum)} a month doesn't cover the interest; set the months instead`
  if (!form.keepPayment && !(Number(form.months) >= 1)) return 'Enter the months left'
  return ''
})
const outcome = computed(() => {
  if (problem.value || months.value == null) return problem.value
  const pay = amortized(props.card.balance, props.card.interestRate, months.value)
  const years = months.value >= 24 ? ` (${(months.value / 12).toFixed(1)} years)` : ''
  return `${currency(pay)} a month for ${months.value} months${years}.`
})

const saving = ref(false)
const { mutate } = useMutation<{ convertCreditToLoan: MutationPayload }>(CONVERT_CREDIT_TO_LOAN)
async function convert() {
  saving.value = true
  const student = form.kind === 'student'
  const res = await runMutation(() => mutate({ variables: {
    bankName: props.bankName, accountName: props.card.accountName, loanKind: form.kind,
    termMonths: form.keepPayment ? null : months.value,
    paymentsStart: student && form.paymentsStart ? form.paymentsStart : null,
    subsidized: student && !!form.paymentsStart && form.subsidized,
  }}), 'convertCreditToLoan', { failMessage: 'Failed to convert to a loan', showSuccess: true })
  saving.value = false
  if (res) {
    emit('done')
    emit('close')
  }
}
</script>

<style scoped>
.help { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem; }
.inline { display: flex; align-items: center; gap: 0.4rem; font-weight: 400; cursor: pointer; margin-bottom: 0.3rem; }
.muted { color: var(--text-muted); display: block; margin-top: 0.25rem; }
</style>
