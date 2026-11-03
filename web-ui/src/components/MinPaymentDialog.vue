<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="max-width:540px">
      <h3>Minimum payment: {{ card.accountName }}</h3>
      <p class="help">
        The app follows this formula in every projection. Now: <strong>{{ card.minRuleLabel || 'default' }}</strong>
        ({{ currency(card.minimumPayment ?? 0) }} on today's balance{{ owesPromo ? ', including what clears its promos before they expire' : '' }}).
      </p>

      <!-- 1. Match a statement -->
      <h4>Match your statement</h4>
      <div class="grid3">
        <div class="form-group">
          <label>Minimum due</label>
          <input v-model.number="form.minimum" type="number" step="0.01" min="0" placeholder="e.g. 135.00" />
        </div>
        <div class="form-group">
          <label>Statement balance</label>
          <input v-model.number="form.balance" type="number" step="0.01" min="0" />
        </div>
        <div class="form-group">
          <label>Interest charged</label>
          <input v-model.number="form.interest" type="number" step="0.01" min="0" placeholder="estimated" />
        </div>
      </div>
      <button class="btn btn-outline btn-sm" :disabled="checking || !(Number(form.minimum) > 0)" @click="check">
        {{ checking ? 'Checking…' : 'Find the formula' }}
      </button>

      <div v-if="result" class="result">
        <p :class="{ warn: !result.best || result.close }">{{ result.message }}</p>
        <p v-if="result.interestEstimated" class="help">
          Interest estimated at {{ currency(result.interestUsed) }} from the {{ card.interestRate }}% APR. Enter it from
          the statement if the match looks wrong.
        </p>
        <div v-if="result.matches.length" class="options" role="radiogroup" aria-label="Formulas that fit">
          <label v-for="m in result.matches" :key="m.label" class="option" :class="{ selected: sameRule(m.rule) }">
            <input type="radio" name="min-match" :checked="sameRule(m.rule)" @change="useRule(m.rule)" />
            <span class="grow">{{ m.label }}</span>
            <span class="muted">{{ currency(m.amount) }}<template v-if="m.off != null && Math.abs(m.off) >= 0.005"> ({{ m.off > 0 ? '+' : '−' }}{{ currency(Math.abs(m.off)) }})</template></span>
          </label>
        </div>
      </div>

      <!-- 2. The formula itself, editable -->
      <h4>Formula</h4>
      <div class="kind" role="radiogroup" aria-label="Kind of formula">
        <label><input v-model="rule.kind" type="radio" value="pct" /> Percentage of the balance</label>
        <label><input v-model="rule.kind" type="radio" value="fixed" /> Fixed amount</label>
      </div>
      <div v-if="rule.kind === 'pct'" class="grid3">
        <div class="form-group">
          <label>% of balance</label>
          <input v-model.number="rule.pct" type="number" step="0.1" min="0" max="100" />
        </div>
        <div class="form-group">
          <label>At least ($)</label>
          <input v-model.number="rule.floor" type="number" step="1" min="0" />
        </div>
        <div class="form-group check">
          <label><input v-model="rule.interest" type="checkbox" /> + the month's interest</label>
        </div>
      </div>
      <div v-else class="form-group" style="max-width:12rem">
        <label>Every month ($)</label>
        <input v-model.number="rule.fixed" type="number" step="0.01" min="0" />
      </div>
      <p v-if="problem" class="problem">{{ problem }}</p>
      <p v-else class="preview">
        {{ ruleLabel }}: <strong>{{ currency(preview) }}</strong> on a {{ currency(previewBalance) }} balance<template v-if="rule.kind === 'pct' && rule.interest"> with {{ currency(previewInterest) }} interest</template>.
        <template v-if="Number(form.minimum) > 0 && Math.abs(preview - Number(form.minimum)) >= 0.005">
          Your statement says {{ currency(Number(form.minimum)) }}.
        </template>
      </p>

      <div class="modal-actions">
        <button v-if="card.minRule" class="btn btn-outline" :disabled="saving" @click="save(null)">Use the default</button>
        <span style="flex:1"></span>
        <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="saving || !!problem" @click="save(currentRule())">Save formula</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import { apolloClient } from '../graphql/client'
import { MINIMUM_PAYMENT_MATCH, SET_MINIMUM_PAYMENT_RULE } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { notify } from '../utils/dialog'
import { currency } from '../utils/format'
import type { CreditAccount, MutationPayload } from '../types'

const props = defineProps<{ bankName: string; card: CreditAccount }>()
const emit = defineEmits<{ close: []; done: [] }>()

interface Rule { pct?: number; interest?: boolean; floor?: number; fixed?: number }
interface Match {
  best: string | null
  bestLabel: string | null
  ambiguous: boolean
  close: boolean
  message: string
  balanceUsed: number
  interestUsed: number
  interestEstimated: boolean
  currentRuleLabel: string
  currentMinimum: number
  matches: { rule: string; label: string; amount: number; off: number | null }[]
}

// Same default as models/min_payment.py
const DEFAULT_RULE: Rule = { pct: 1, interest: true, floor: 25 }
const parse = (r: unknown): Rule | null => {
  if (!r) return null
  try { return (typeof r === 'string' ? JSON.parse(r) : r) as Rule } catch { return null }
}

const promoTotal = (props.card.promoOffers ?? []).reduce((t, p) => t + (p.interestCharged ? 0 : p.promoBalance ?? 0), 0)
const owesPromo = promoTotal > 0.005

type Num = number | string | null
const num = (v: Num) => (v === '' || v === null || Number.isNaN(Number(v)) ? null : Number(v))
const form = reactive({ minimum: null as Num, balance: props.card.balance as Num, interest: null as Num })

// The formula being edited: starts as the card's own (or the default)
const start = parse(props.card.minRule) ?? DEFAULT_RULE
const rule = reactive({
  kind: (start.fixed != null ? 'fixed' : 'pct') as 'pct' | 'fixed',
  pct: (start.pct ?? 1) as Num, interest: start.interest ?? false, floor: (start.floor ?? 0) as Num,
  fixed: (start.fixed ?? null) as Num,
})

function useRule(r: unknown) {
  const p = parse(r)
  if (!p) return
  if (p.fixed != null) Object.assign(rule, { kind: 'fixed', fixed: p.fixed })
  else Object.assign(rule, { kind: 'pct', pct: p.pct ?? 1, interest: !!p.interest, floor: p.floor ?? 0 })
}

function currentRule(): Rule {
  return rule.kind === 'fixed'
    ? { fixed: num(rule.fixed) ?? 0 }
    : { pct: num(rule.pct) ?? 0, interest: !!rule.interest, floor: num(rule.floor) ?? 0 }
}

function sameRule(r: unknown) {
  const a = parse(r), b = currentRule()
  if (!a) return false
  if (a.fixed != null || b.fixed != null) return a.fixed != null && b.fixed != null && Math.abs(a.fixed - b.fixed) < 0.005
  return a.pct === b.pct && !!a.interest === !!b.interest && (a.floor ?? 0) === (b.floor ?? 0)
}

const problem = computed(() => {
  const r = currentRule()
  if (rule.kind === 'fixed') return (r.fixed ?? 0) > 0 ? '' : 'Enter the monthly amount.'
  if (!((r.pct ?? 0) > 0 && (r.pct ?? 0) <= 100)) return 'The percentage must be more than 0 and at most 100.'
  if ((r.floor ?? 0) < 0) return "The minimum can't be negative."
  return ''
})

const money = (x: number) => `$${x.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
const ruleLabel = computed(() => {
  const r = currentRule()
  if (r.fixed != null) return `Fixed ${money(r.fixed)} a month`
  return `${r.pct}% of the balance${r.interest ? ' + interest' : ''}${(r.floor ?? 0) > 0 ? `, at least ${money(r.floor ?? 0)}` : ''}`
})

// Preview on the statement entered, else today's balance (mirrors min_payment.amount)
const previewBalance = computed(() => num(form.balance) ?? props.card.balance)
const previewInterest = computed(() => num(form.interest)
  ?? Math.max(0, previewBalance.value - promoTotal) * (props.card.interestRate || 0) / 1200)
const preview = computed(() => {
  const bal = previewBalance.value
  const r = currentRule()
  if (bal <= 0.005) return 0
  if (r.fixed != null) return Math.min(r.fixed, bal)
  const base = bal * (r.pct ?? 0) / 100 + (r.interest ? previewInterest.value : 0)
  return Math.round(Math.min(bal, Math.max(r.floor ?? 0, base)) * 100) / 100
})

const result = ref<Match | null>(null)
const checking = ref(false)
const saving = ref(false)

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
    if (result.value?.best) useRule(result.value.best)
  } catch (e: unknown) {
    result.value = null
    notify((e instanceof Error ? e.message : String(e)).replace(/^.*?: /, ''), 'error')
  } finally {
    checking.value = false
  }
}

const { mutate } = useMutation<{ setMinimumPaymentRule: MutationPayload }>(SET_MINIMUM_PAYMENT_RULE)
async function save(r: Rule | null) {
  saving.value = true
  const res = await runMutation(
    () => mutate({ variables: { bankName: props.bankName, accountName: props.card.accountName, rule: r ? JSON.stringify(r) : null } }),
    'setMinimumPaymentRule', { failMessage: 'Failed to save the minimum payment formula', showSuccess: true })
  saving.value = false
  if (res) {
    emit('done')
    emit('close')
  }
}
</script>

<style scoped>
h4 { margin: 1rem 0 0.4rem; font-size: 0.9rem; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 0.75rem; align-items: end; }
@media (max-width: 480px) { .grid3 { grid-template-columns: 1fr; } }
.check label { display: flex; align-items: center; gap: 0.4rem; font-weight: 400; }
.kind { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem; font-size: 0.9rem; }
.kind label { display: flex; align-items: center; gap: 0.35rem; cursor: pointer; }
.result { margin-top: 0.75rem; font-size: 0.9rem; }
.warn { color: var(--warning, #b45309); }
.options { display: flex; flex-direction: column; gap: 0.35rem; margin: 0.5rem 0; }
.option { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; }
.option.selected { border-color: var(--primary); }
.grow { flex: 1; }
.muted { color: var(--text-muted); white-space: nowrap; }
.preview { font-size: 0.9rem; margin: 0.25rem 0 0; }
.problem { color: var(--danger); font-size: 0.85rem; }
.modal-actions { display: flex; gap: 0.5rem; margin-top: 1rem; align-items: center; flex-wrap: wrap; }
</style>
