<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="max-width:520px">
      <h3>Minimum payment: {{ card.accountName }}</h3>
      <p class="help">
        Enter the minimum from your latest statement. The app works out which formula your card issuer uses
        and follows it in every projection. Now: <strong>{{ card.minRuleLabel || 'default' }}</strong>
        ({{ currency(card.minimumPayment ?? 0) }} on today's balance{{ owesPromo ? ', including what clears its promos before they expire' : '' }}).
      </p>

      <div class="grid2">
        <div class="form-group">
          <label>Minimum payment due</label>
          <input v-model.number="form.minimum" type="number" step="0.01" min="0" placeholder="e.g. 135.00" />
        </div>
        <div class="form-group">
          <label>Statement balance</label>
          <input v-model.number="form.balance" type="number" step="0.01" min="0" />
        </div>
        <div class="form-group">
          <label>Interest charged (optional)</label>
          <input v-model.number="form.interest" type="number" step="0.01" min="0" placeholder="estimated from the APR" />
        </div>
      </div>
      <button class="btn btn-outline" :disabled="checking || !(Number(form.minimum) > 0)" @click="check">
        {{ checking ? 'Checking…' : 'Find the formula' }}
      </button>

      <div v-if="result" class="result">
        <p :class="result.best ? '' : 'warn'">{{ result.message }}</p>
        <p v-if="result.interestEstimated" class="help">
          Interest estimated at {{ currency(result.interestUsed) }} from the {{ card.interestRate }}% APR. Enter it from
          the statement if the match looks wrong.
        </p>
        <div v-if="result.matches.length" class="options" role="radiogroup">
          <label v-for="m in result.matches" :key="m.label" class="option">
            <input v-model="picked" type="radio" :value="m.rule" />
            <span>{{ m.label }}</span>
            <span class="muted">{{ currency(m.amount) }}</span>
          </label>
        </div>
        <p class="help">Currently {{ result.currentRuleLabel }}, which gives {{ currency(result.currentMinimum) }} on this statement.</p>
      </div>

      <div class="modal-actions">
        <button v-if="card.minRule" class="btn btn-outline" :disabled="saving" @click="save(null)">Use the default</button>
        <span style="flex:1"></span>
        <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="saving || !picked" @click="save(picked)">Use this formula</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import { apolloClient } from '../graphql/client'
import { MINIMUM_PAYMENT_MATCH, SET_MINIMUM_PAYMENT_RULE } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { notify } from '../utils/dialog'
import { currency } from '../utils/format'
import type { CreditAccount, MutationPayload } from '../types'

const props = defineProps<{ bankName: string; card: CreditAccount }>()
const owesPromo = (props.card.promoOffers ?? []).some(p => (p.promoBalance ?? 0) > 0.005 && !p.interestCharged)
const emit = defineEmits<{ close: []; done: [] }>()

interface Match {
  best: string | null
  bestLabel: string | null
  ambiguous: boolean
  message: string
  balanceUsed: number
  interestUsed: number
  interestEstimated: boolean
  currentRuleLabel: string
  currentMinimum: number
  matches: { rule: string; label: string; amount: number }[]
}

type Num = number | string | null
const form = reactive({ minimum: null as Num, balance: props.card.balance as Num, interest: null as Num })
const result = ref<Match | null>(null)
const picked = ref<string | null>(null)
const checking = ref(false)
const saving = ref(false)
const num = (v: Num) => (v === '' || v === null || Number.isNaN(Number(v)) ? null : Number(v))

async function check() {
  checking.value = true
  try {
    const { data } = await apolloClient.query<{ minimumPaymentMatch: Match }>({
      query: MINIMUM_PAYMENT_MATCH,
      variables: {
        bankName: props.bankName, accountName: props.card.accountName, minimumPayment: num(form.minimum),
        statementBalance: num(form.balance), interestCharged: num(form.interest),
      },
    })
    result.value = data?.minimumPaymentMatch ?? null
    picked.value = result.value?.best ?? null
  } catch (e: unknown) {
    result.value = null
    notify((e instanceof Error ? e.message : String(e)).replace(/^.*?: /, ''), 'error')
  } finally {
    checking.value = false
  }
}

const { mutate } = useMutation<{ setMinimumPaymentRule: MutationPayload }>(SET_MINIMUM_PAYMENT_RULE)
async function save(rule: string | null) {
  saving.value = true
  const res = await runMutation(() => mutate({ variables: { bankName: props.bankName, accountName: props.card.accountName, rule } }),
    'setMinimumPaymentRule', { failMessage: 'Failed to save the minimum payment rule', showSuccess: true })
  saving.value = false
  if (res) {
    emit('done')
    emit('close')
  }
}
</script>

<style scoped>
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 0.75rem; }
@media (max-width: 480px) { .grid2 { grid-template-columns: 1fr; } }
.result { margin-top: 0.9rem; font-size: 0.9rem; }
.result .warn { color: var(--warning, #b45309); }
.options { display: flex; flex-direction: column; gap: 0.35rem; margin: 0.5rem 0; }
.option { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; }
.option span:nth-child(2) { flex: 1; }
.muted { color: var(--text-muted); }
.modal-actions { display: flex; gap: 0.5rem; margin-top: 1rem; align-items: center; }
</style>
