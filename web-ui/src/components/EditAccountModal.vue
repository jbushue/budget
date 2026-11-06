<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="max-width:560px">
      <h3>Edit {{ kindTitle }}</h3>
      <p class="help">
        {{ bankName }} / {{ account.accountName }}. Bills, payment history, transactions and SimpleFIN links follow a
        rename or a move to another bank. To change the balance use <strong>Update</strong>, which keeps a history.
      </p>

      <div class="grid2">
        <div class="form-group">
          <label>Name</label>
          <input v-model="form.name" />
        </div>
        <div class="form-group">
          <label>Bank</label>
          <select v-model="form.bank">
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
        </div>
      </div>

      <!-- Checking / savings -->
      <template v-if="isBank">
        <div class="grid2">
          <div class="form-group">
            <label>Type</label>
            <select v-model="form.accountType">
              <optgroup v-for="g in KIND_GROUPS" :key="g.group" :label="g.label">
                <option v-for="k in g.kinds" :key="k.value" :value="k.value">{{ k.label }}</option>
              </optgroup>
            </select>
          </div>
          <div v-if="kindInfo(form.accountType).earns || (num(form.interestRate) ?? 0) > 0" class="form-group">
            <label>{{ rateLabel(form.accountType) }}</label>
            <input v-model.number="form.interestRate" type="number" step="0.01" min="0" />
          </div>
        </div>
        <p class="help" style="margin-top:-0.4rem">{{ kindInfo(form.accountType).hint }}</p>
        <AccountExtrasFields v-model="extras" :type="form.accountType" />
        <div v-if="kindInfo(form.accountType).earns" class="form-group">
          <label>Interest day (1-31, blank = end of month)</label>
          <input v-model.number="form.interestAccrualDate" type="number" min="1" max="31" />
        </div>
      </template>

      <!-- Credit card -->
      <template v-else-if="kind === 'credit'">
        <div class="grid2">
          <div class="form-group">
            <label>APR %</label>
            <input v-model.number="form.interestRate" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>Credit limit</label>
            <input v-model.number="form.creditLimit" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>Payment due day (1-31)</label>
            <input v-model.number="form.paymentDueDate" type="number" min="1" max="31" />
          </div>
          <div class="form-group">
            <label>Statement day (1-31, optional)</label>
            <input v-model.number="form.statementDate" type="number" min="1" max="31" />
          </div>
        </div>
        <div class="form-group">
          <label>Status</label>
          <select v-model="form.status">
            <option value="active">Active</option>
            <option value="frozen">Frozen</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        <p class="help">Promo offers are edited with the card's <strong>Promos</strong> button.</p>
      </template>

      <!-- Loan: mortgage, auto, student, personal, other -->
      <template v-else-if="kind === 'mortgage'">
        <div class="grid2">
          <div class="form-group">
            <label>Kind of loan</label>
            <select v-model="form.loanKind">
              <option v-for="k in LOAN_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Payment from your statement</label>
            <input v-model.number="form.paymentOverride" type="number" step="0.01" min="0" placeholder="blank = calculated" />
          </div>
          <div class="form-group">
            <label>Original loan amount</label>
            <input v-model.number="form.originalPrincipal" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>Current balance owed</label>
            <input v-model.number="form.currentPrincipal" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>APR %</label>
            <input v-model.number="form.interestRate" type="number" step="0.001" min="0" />
          </div>
          <div v-if="form.loanKind === 'mortgage'" class="form-group">
            <label>Loan term (years)</label>
            <input v-model.number="form.termYears" type="number" min="1" max="50" step="0.5" />
          </div>
          <div v-else class="form-group">
            <label>Loan term (months)</label>
            <input v-model.number="form.termMonths" type="number" min="1" max="600" step="1" />
          </div>
          <div class="form-group">
            <label>Loan start date</label>
            <input v-model="form.startDate" type="date" />
          </div>
          <div class="form-group">
            <label>Payment due day (1-31)</label>
            <input v-model.number="form.paymentDueDate" type="number" min="1" max="31" />
          </div>
        </div>
        <div v-if="form.loanKind === 'student'" class="grid2">
          <div class="form-group">
            <label>Payments start (blank = already repaying)</label>
            <input v-model="form.paymentsStart" type="date" />
          </div>
          <div v-if="form.paymentsStart" class="form-group" style="align-self:end">
            <label style="display:flex;align-items:center;gap:0.4rem;font-weight:400">
              <input v-model="form.subsidized" type="checkbox" /> Subsidized (no interest until then)
            </label>
          </div>
        </div>
        <div v-if="form.loanKind === 'auto'" class="grid2">
          <div class="form-group">
            <label>Vehicle value (blank = not set)</label>
            <input v-model.number="form.marketValue" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>Loses (% a year)</label>
            <input v-model.number="form.depreciationRate" type="number" step="0.5" min="0" max="99" />
          </div>
        </div>
        <div v-if="form.loanKind === 'mortgage'" class="form-group">
          <label>Monthly escrow</label>
          <div class="grid2">
            <label class="sub">Property tax <input v-model.number="form.escrowPropertyTax" type="number" step="0.01" min="0" /></label>
            <label class="sub">Insurance <input v-model.number="form.escrowInsurance" type="number" step="0.01" min="0" /></label>
            <label class="sub">PMI <input v-model.number="form.escrowPmi" type="number" step="0.01" min="0" /></label>
            <label class="sub">HOA <input v-model.number="form.escrowHoa" type="number" step="0.01" min="0" /></label>
            <label class="sub">Other <input v-model.number="form.escrowOther" type="number" step="0.01" min="0" /></label>
          </div>
        </div>
        <div v-if="form.loanKind === 'mortgage'" class="form-group">
          <label>Home market value (blank = not set)</label>
          <input v-model.number="form.marketValue" type="number" step="0.01" min="0" />
        </div>
      </template>

      <!-- HELOC -->
      <template v-else-if="kind === 'heloc'">
        <div class="grid2">
          <div class="form-group">
            <label>APR %</label>
            <input v-model.number="form.interestRate" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>Credit limit</label>
            <input v-model.number="form.creditLimit" type="number" step="0.01" min="0" />
          </div>
          <div class="form-group">
            <label>Draw period (years)</label>
            <input v-model.number="form.drawYears" type="number" min="0.5" step="0.5" />
          </div>
          <div class="form-group">
            <label>Total term (years)</label>
            <input v-model.number="form.totalYears" type="number" min="1" step="0.5" />
          </div>
          <div class="form-group">
            <label>Start date</label>
            <input v-model="form.startDate" type="date" />
          </div>
          <div class="form-group">
            <label>Payment due day (1-31)</label>
            <input v-model.number="form.paymentDueDate" type="number" min="1" max="31" />
          </div>
        </div>
      </template>

      <!-- Pay-from account (loans) -->
      <div v-if="kind === 'mortgage' || kind === 'heloc'" class="form-group">
        <label>Pay from</label>
        <div class="grid2">
          <select v-model="form.sourceBank" @change="form.sourceAccount = ''">
            <option value="">Auto (no preference)</option>
            <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
          </select>
          <select v-model="form.sourceAccount" :disabled="!form.sourceBank">
            <option value="">Select account...</option>
            <option v-for="a in sourceAccounts" :key="a.accountName" :value="a.accountName">{{ a.accountName }}</option>
          </select>
        </div>
      </div>

      <p v-if="problem" class="problem">{{ problem }}</p>
      <div class="modal-actions">
        <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="!!problem || saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import { UPDATE_ACCOUNT } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import type { AccountType, Bank, BankAccount, CreditAccount, HELOCAccount, LoanKind, MortgageAccount, MutationPayload } from '../types'
import { KIND_GROUPS, isBankKind, kindInfo, rateLabel } from '../utils/accountKinds'
import AccountExtrasFields, { type AccountExtras } from './AccountExtrasFields.vue'
import { LOAN_KINDS, loanKindLabel } from '../utils/loans'

export type AccountKind = AccountType | 'credit' | 'mortgage' | 'heloc'
export type AnyAccount = BankAccount | CreditAccount | MortgageAccount | HELOCAccount

const props = defineProps<{ kind: AccountKind; bankName: string; account: AnyAccount; banks: Bank[] }>()
const emit = defineEmits<{ close: []; saved: [name: string] }>()

const a = props.account as Partial<BankAccount & CreditAccount & MortgageAccount & HELOCAccount>
const KIND_LABEL: Record<string, string> = {
  checking: 'Checking Account', savings: 'Savings Account', credit: 'Credit Card', mortgage: 'Mortgage', heloc: 'HELOC',
}
const kindTitle = computed(() => (props.kind === 'mortgage' ? loanKindLabel(a.loanKind ?? 'mortgage')
  : KIND_LABEL[props.kind] ?? `${kindInfo(props.kind).label} account`))

const isBank = computed(() => isBankKind(props.kind))
const years = (months?: number | null) => (months ? Math.round((months / 12) * 100) / 100 : null)

type Num = number | string | null
const form = reactive({
  name: a.accountName ?? '',
  bank: props.bankName,
  accountType: props.kind,
  interestRate: (a.interestRate ?? 0) as Num,
  interestAccrualDate: (a.interestAccrualDate ?? null) as Num,
  creditLimit: (a.creditLimit ?? null) as Num,
  paymentDueDate: (a.paymentDueDate ?? null) as Num,
  statementDate: (a.statementDate ?? null) as Num,
  status: (a.status as string) ?? 'active',
  originalPrincipal: (a.originalPrincipal ?? null) as Num,
  currentPrincipal: (a.currentPrincipal ?? null) as Num,
  termYears: years(a.loanTermMonths) as Num,
  startDate: a.startDate ?? '',
  escrowPropertyTax: (a.escrowPropertyTax ?? 0) as Num,
  escrowInsurance: (a.escrowInsurance ?? 0) as Num,
  escrowPmi: (a.escrowPmi ?? 0) as Num,
  escrowHoa: (a.escrowHoa ?? 0) as Num,
  escrowOther: (a.escrowOther ?? 0) as Num,
  marketValue: (a.marketValue ?? null) as Num,
  loanKind: (a.loanKind ?? 'mortgage') as LoanKind,
  termMonths: (a.loanTermMonths ?? null) as Num,
  paymentOverride: (a.paymentOverride ?? null) as Num,
  paymentsStart: a.paymentsStart ?? '',
  subsidized: !!a.subsidized,
  depreciationRate: (a.depreciationRate ?? 15) as Num,
  drawYears: years(a.drawPeriodMonths) as Num,
  totalYears: years(a.totalTermMonths) as Num,
  sourceBank: a.preferredSourceBank ?? '',
  sourceAccount: a.preferredSourceAccount ?? '',
})

const extras = ref<AccountExtras>({
  refillAmount: a.refillAmount || null, refillDay: a.refillDay ?? null,
  weeklySpending: a.weeklySpending || null, offsetsEveryday: !!a.offsetsEveryday,
})

const sourceAccounts = computed(() => props.banks.find(b => b.name === form.sourceBank)?.bankAccounts ?? [])

/** Empty inputs give '' — treat as "not set". */
const num = (v: Num): number | null => (v === '' || v == null || !Number.isFinite(Number(v)) ? null : Number(v))
const day = (v: Num) => { const n = num(v); return n == null ? null : Math.trunc(n) }
const badDay = (v: Num, optional = true) => { const d = day(v); return d == null ? !optional : d < 1 || d > 31 }

const problem = computed(() => {
  if (!form.name.trim()) return 'Enter a name.'
  if ((num(form.interestRate) ?? 0) < 0) return "The interest rate can't be negative."
  if (isBank.value && badDay(form.interestAccrualDate)) return 'The interest day must be between 1 and 31.'
  if (isBank.value && badDay(extras.value.refillDay)) return 'The refill day must be between 1 and 31.'
  if (isBank.value && ((num(extras.value.refillAmount) ?? 0) < 0 || (num(extras.value.weeklySpending) ?? 0) < 0)) {
    return "Amounts can't be negative."
  }
  if (props.kind === 'credit' || props.kind === 'heloc') {
    if (!((num(form.creditLimit) ?? 0) > 0)) return 'The credit limit must be greater than 0.'
  }
  if (props.kind === 'credit' && (badDay(form.paymentDueDate) || badDay(form.statementDate))) {
    return 'Days must be between 1 and 31.'
  }
  if ((props.kind === 'mortgage' || props.kind === 'heloc') && badDay(form.paymentDueDate, false)) {
    return 'The payment due day must be between 1 and 31.'
  }
  if (props.kind === 'mortgage') {
    const orig = num(form.originalPrincipal) ?? 0, cur = num(form.currentPrincipal) ?? -1
    if (!(orig > 0)) return 'The original loan amount must be greater than 0.'
    if (cur < 0 || cur > orig) return 'The current principal must be between 0 and the original amount.'
    if (!(loanMonths() > 0)) return 'Enter the loan term.'
    const dep = num(form.depreciationRate)
    if (form.loanKind === 'auto' && dep != null && (dep < 0 || dep >= 100)) return 'The yearly loss must be between 0 and 100%.'
  }
  if (props.kind === 'heloc' && !((num(form.totalYears) ?? 0) > (num(form.drawYears) ?? 0) && (num(form.drawYears) ?? 0) > 0)) {
    return 'The total term must be longer than the draw period.'
  }
  if ((props.kind === 'mortgage' || props.kind === 'heloc') && !!form.sourceBank !== !!form.sourceAccount) {
    return 'Pick both a bank and an account to pay from (or Auto).'
  }
  return ''
})

function loanMonths(): number {
  return form.loanKind === 'mortgage' ? Math.round((num(form.termYears) ?? 0) * 12) : Math.trunc(num(form.termMonths) ?? 0)
}

const saving = ref(false)
const { mutate } = useMutation<{ updateAccount: MutationPayload & { name?: string } }>(UPDATE_ACCOUNT)

async function save() {
  const v: Record<string, unknown> = {
    bankName: props.bankName, accountName: props.account.accountName, accountType: props.kind,
    interestRate: num(form.interestRate) ?? 0,
  }
  if (form.name.trim() !== props.account.accountName) v.newName = form.name.trim()
  if (form.bank !== props.bankName) v.newBankName = form.bank
  if (isBank.value) {
    v.newAccountType = form.accountType
    v.interestAccrualDate = day(form.interestAccrualDate) ?? 0
    Object.assign(v, {
      refillAmount: num(extras.value.refillAmount) ?? 0, refillDay: day(extras.value.refillDay) ?? 0,
      weeklySpending: num(extras.value.weeklySpending) ?? 0, offsetsEveryday: extras.value.offsetsEveryday,
    })
  } else if (props.kind === 'credit') {
    Object.assign(v, { creditLimit: num(form.creditLimit), paymentDueDate: day(form.paymentDueDate),
      statementDate: day(form.statementDate) ?? 0, status: form.status })
  } else if (props.kind === 'mortgage') {
    const k = form.loanKind
    Object.assign(v, {
      originalPrincipal: num(form.originalPrincipal), currentPrincipal: num(form.currentPrincipal),
      loanTermMonths: loanMonths(), paymentDueDate: day(form.paymentDueDate),
      startDate: form.startDate || null,
      loanKind: k, paymentOverride: num(form.paymentOverride) ?? 0,
    })
    if (k === 'mortgage') {
      Object.assign(v, {
        escrowPropertyTax: num(form.escrowPropertyTax) ?? 0, escrowInsurance: num(form.escrowInsurance) ?? 0,
        escrowPmi: num(form.escrowPmi) ?? 0, escrowHoa: num(form.escrowHoa) ?? 0, escrowOther: num(form.escrowOther) ?? 0,
      })
    }
    if (k === 'mortgage' || k === 'auto') v.marketValue = num(form.marketValue) ?? 0
    if (k === 'auto') v.depreciationRate = num(form.depreciationRate) ?? 0
    if (k === 'student') Object.assign(v, { paymentsStart: form.paymentsStart || '', subsidized: !!form.paymentsStart && form.subsidized })
  } else {
    Object.assign(v, {
      creditLimit: num(form.creditLimit), drawPeriodMonths: Math.round((num(form.drawYears) ?? 0) * 12),
      totalTermMonths: Math.round((num(form.totalYears) ?? 0) * 12), paymentDueDate: day(form.paymentDueDate),
      startDate: form.startDate || null,
    })
  }
  if (props.kind === 'mortgage' || props.kind === 'heloc') {
    v.preferredSourceBank = form.sourceBank
    v.preferredSourceAccount = form.sourceAccount
  }
  saving.value = true
  const res = await runMutation(() => mutate({ variables: v }), 'updateAccount', { failMessage: 'Failed to save the account' })
  saving.value = false
  if (res) emit('saved', res.name ?? form.name.trim())
}
</script>

<style scoped>
.help { font-size: 0.8rem; color: var(--text-muted); margin: 0 0 0.9rem; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 0.75rem; }
.sub { display: flex; flex-direction: column; font-size: 0.75rem; color: var(--text-muted); gap: 0.2rem; margin-bottom: 0.5rem; }
.problem { color: var(--danger); font-size: 0.85rem; margin: 0.25rem 0 0; }
@media (max-width: 480px) { .grid2 { grid-template-columns: 1fr; } }
</style>
