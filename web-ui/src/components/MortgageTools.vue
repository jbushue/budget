<template>
  <div v-if="open" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="max-width:820px">
      <div class="mt-head">
        <div>
          <h3 style="margin:0">{{ accountName }}</h3>
          <div class="muted" style="font-size:0.85rem">{{ bankName }} · {{ (d?.kindLabel ?? 'Mortgage').toLowerCase() }}<template v-if="d?.paymentsStart"> · first payment {{ fmtDate(d.paymentsStart) }}</template></div>
        </div>
        <button class="btn btn-ghost btn-icon" aria-label="Close" @click="emit('close')"><Icon name="x" :size="18" /></button>
      </div>

      <div v-if="loading && !d" class="loading">Working out the schedule...</div>
      <div v-else-if="error" class="callout danger">{{ error.message }}</div>
      <template v-else-if="d">
        <div class="mt-stats">
          <div><span>Owed</span><strong>{{ currency(d.balance) }}</strong></div>
          <div><span>Monthly payment</span><strong>{{ currency(d.monthlyPayment) }}</strong>
            <small v-if="d.escrow > 0">{{ currency(d.principalAndInterest) }} loan + {{ currency(d.escrow) }} escrow</small></div>
          <div><span>Paid off</span><strong>{{ fmtMonth(d.payoffDate) }}</strong><small>{{ yearsMonths(d.remainingMonths) }} left</small></div>
          <div><span>Interest still to pay</span><strong>{{ currency(d.interestRemaining) }}</strong><small>at {{ pct(d.rate, 2) }}</small></div>
          <div v-if="d.marketValue"><span>{{ d.kindLabel === 'Auto loan' ? 'Vehicle equity' : 'Equity' }}</span><strong>{{ currency(d.equity) }}</strong><small>{{ pct(d.ltv * 100, 0) }} loan-to-value</small></div>
        </div>

        <div class="tabs" role="tablist" style="margin-top:1.25rem">
          <button v-for="t in TABS" :key="t.key" class="tab" :class="{ active: tab === t.key }" role="tab" @click="tab = t.key">{{ t.label }}</button>
        </div>

        <!-- Early payoff calculator -->
        <div v-if="tab === 'payoff'">
          <label class="extra-label">Extra toward principal each month: <strong>{{ currency(extra) }}</strong></label>
          <input v-model.number="extra" type="range" min="0" :max="sliderMax" :step="25" style="width:100%" />
          <div class="extra-presets">
            <button v-for="v in [100, 250, 500, 1000]" :key="v" class="chip" :class="{ selected: extra === v }" @click="extra = v">{{ currency(v) }}</button>
            <input v-model.number="extra" type="number" min="0" step="25" style="width:7rem" aria-label="Extra per month" />
          </div>
          <div v-if="extra > 0" class="callout success" style="margin-top:1rem">
            <Icon name="sparkles" :size="18" />
            <div>
              Paying {{ currency(extra) }} more a month pays the loan off <strong>{{ yearsMonths(d.monthsSaved) }} sooner</strong>
              ({{ fmtMonth(d.newPayoffDate) }}) and saves <strong>{{ currency(d.interestSaved) }}</strong> in interest.
            </div>
          </div>
          <p v-else class="muted" style="font-size:0.85rem;margin-top:1rem">Slide to see how much sooner extra payments would pay this off.</p>
        </div>

        <!-- Next 12 payments -->
        <div v-else-if="tab === 'schedule'" class="table-wrap">
          <table>
            <thead><tr><th>Date</th><th style="text-align:right">Payment</th><th style="text-align:right">Principal</th><th style="text-align:right">Interest</th><th style="text-align:right">Escrow</th><th style="text-align:right">Owed after</th></tr></thead>
            <tbody>
              <tr v-for="r in d.schedule" :key="r.month">
                <td>{{ fmtDate(r.date) }}</td>
                <td style="text-align:right">{{ currency(r.payment) }}</td>
                <td style="text-align:right">{{ currency(r.principal) }}</td>
                <td style="text-align:right">{{ currency(r.interest) }}</td>
                <td style="text-align:right">{{ currency(r.escrow) }}</td>
                <td style="text-align:right;font-weight:550">{{ currency(r.principalRemaining) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Year by year -->
        <div v-else-if="tab === 'years'" class="table-wrap" style="max-height:340px;overflow-y:auto">
          <table>
            <thead><tr><th>Year</th><th style="text-align:right">Principal</th><th style="text-align:right">Interest</th><th style="text-align:right">Owed at year end</th></tr></thead>
            <tbody>
              <tr v-for="y in d.years" :key="y.year">
                <td>{{ y.year }}</td>
                <td style="text-align:right">{{ currency(y.principal) }}</td>
                <td style="text-align:right">{{ currency(y.interest) }}</td>
                <td style="text-align:right;font-weight:550">{{ currency(y.endBalance) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pay extra principal now -->
        <div v-else-if="tab === 'pay'">
          <p class="muted" style="font-size:0.85rem;margin-top:0">A one-time payment that goes straight to principal.</p>
          <div class="form-row">
            <div class="form-group">
              <label>Amount</label>
              <input v-model.number="payAmount" type="number" min="0" step="0.01" placeholder="0.00" />
            </div>
            <div class="form-group">
              <label>Paid from</label>
              <select v-model="paySource">
                <option value="">Already paid (don't move money)</option>
                <option v-for="a in cashAccounts" :key="a.key" :value="a.key">{{ a.label }} · {{ currency(a.balance) }}</option>
              </select>
            </div>
          </div>
          <div class="modal-actions" style="margin-top:0">
            <button class="btn btn-primary" :disabled="!((payAmount ?? 0) > 0) || paying" @click="payExtra">{{ paying ? 'Paying...' : 'Pay extra principal' }}</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation, useQuery } from '@vue/apollo-composable'
import Icon from './Icon.vue'
import { GET_MORTGAGE_DETAILS, PAY_EXTRA_PRINCIPAL } from '../graphql/tools'
import { runMutation } from '../utils/mutation'
import { currency, fmtDate, pct } from '../utils/format'
import type { Bank, MutationPayload } from '../types'

const props = defineProps<{ open: boolean; bankName: string; accountName: string; banks: Bank[]; initialTab?: string }>()
const emit = defineEmits<{ close: []; done: [] }>()

const TABS = [
  { key: 'payoff', label: 'Pay off sooner' },
  { key: 'schedule', label: 'Next 12' },
  { key: 'years', label: 'By year' },
  { key: 'pay', label: 'Pay extra' },
]
const tab = ref('payoff')
const extra = ref(0)
const debounced = ref(0)
let timer: ReturnType<typeof setTimeout> | undefined
watch(extra, v => {
  clearTimeout(timer)
  timer = setTimeout(() => { debounced.value = Number(v) || 0 }, 250)
})
watch(() => props.open, isOpen => {
  if (isOpen) { tab.value = props.initialTab || 'payoff'; extra.value = 0; debounced.value = 0; payAmount.value = null; paySource.value = '' }
})

interface Details {
  balance: number; rate: number; monthlyPayment: number; principalAndInterest: number; escrow: number
  kindLabel: string; paymentsStart: string | null
  remainingMonths: number; payoffDate: string; interestRemaining: number; equity: number; ltv: number
  marketValue: number | null; monthsSaved: number; interestSaved: number; newPayoffDate: string
  schedule: { month: number; date: string; payment: number; principal: number; interest: number; escrow: number; principalRemaining: number }[]
  years: { year: number; principal: number; interest: number; endBalance: number }[]
}

const { result, loading, error, refetch } = useQuery<{ mortgageDetails: Details }>(GET_MORTGAGE_DETAILS, () => ({
  variables: { bankName: props.bankName, accountName: props.accountName, extraMonthly: debounced.value },
  enabled: props.open && !!props.accountName,
  fetchPolicy: 'cache-and-network',
}))
const d = computed(() => result.value?.mortgageDetails)
const sliderMax = computed(() => Math.max(2000, Math.ceil((d.value?.principalAndInterest ?? 1000) / 500) * 500))

function yearsMonths(months: number) {
  const y = Math.floor(months / 12), m = months % 12
  return [y ? `${y} yr` : '', m ? `${m} mo` : ''].filter(Boolean).join(' ') || '0 mo'
}
function fmtMonth(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

// ── one-time extra payment
const payAmount = ref<number | null>(null)
const paySource = ref('')
const paying = ref(false)
const cashAccounts = computed(() => props.banks.flatMap(b => b.bankAccounts.map(a => ({
  key: `${b.name}\u0000${a.accountName}`, bank: b.name, account: a.accountName, label: `${b.name} · ${a.accountName}`, balance: a.balance,
}))))
const { mutate: payM } = useMutation<{ payExtraPrincipal: MutationPayload }>(PAY_EXTRA_PRINCIPAL)

async function payExtra() {
  const src = cashAccounts.value.find(a => a.key === paySource.value)
  paying.value = true
  const ok = await runMutation(() => payM({ variables: {
    bankName: props.bankName, accountName: props.accountName, amount: payAmount.value ?? 0,
    sourceBank: src?.bank ?? null, sourceAccount: src?.account ?? null,
  } }), 'payExtraPrincipal', { failMessage: 'Could not record the payment', showSuccess: true })
  paying.value = false
  if (ok) { payAmount.value = null; refetch(); emit('done') }
}
</script>

<style scoped>
.mt-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.mt-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; }
.mt-stats > div { display: flex; flex-direction: column; gap: 0.1rem; padding: 0.7rem 0.8rem; border: 1px solid var(--border); border-radius: var(--radius); }
.mt-stats span { font-size: 0.75rem; color: var(--text-muted); font-weight: 550; }
.mt-stats strong { font-size: 1.05rem; font-variant-numeric: tabular-nums; }
.mt-stats small { font-size: 0.72rem; color: var(--text-light); }
.extra-label { display: block; margin-bottom: 0.5rem; font-size: 0.9rem; }
.extra-presets { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-top: 0.6rem; }
</style>
