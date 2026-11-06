import type { LoanKind } from '../types'

/** Kinds of installment loan (models/mortgage_account.py LOAN_KINDS). */
export const LOAN_KINDS: { value: LoanKind; label: string; term: number; hint: string }[] = [
  { value: 'mortgage', label: 'Mortgage', term: 360, hint: 'Home loan; escrow (taxes, insurance, PMI) can be added to the payment.' },
  { value: 'auto', label: 'Auto loan', term: 60, hint: "The vehicle's value counts toward net worth and loses value each year." },
  { value: 'student', label: 'Student loan', term: 120, hint: "Nothing is due until payments start; unsubsidized loans add the interest from until then when they do." },
  { value: 'personal', label: 'Personal loan', term: 36, hint: 'A fixed payment until it is paid off. 0% installment plans: APR 0.' },
  { value: 'other', label: 'Other loan', term: 24, hint: 'Any other loan with a fixed monthly payment.' },
]

export function loanKindLabel(kind: string | null | undefined): string {
  return LOAN_KINDS.find(k => k.value === kind)?.label ?? 'Loan'
}

/** Amortized monthly payment (mirrors MortgageAccount.base_monthly_payment). */
export function amortized(principal: number, aprPct: number, months: number): number {
  if (!(principal > 0) || !(months > 0)) return 0
  const r = (aprPct || 0) / 1200
  return r === 0 ? principal / months : principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)
}

/** Months for `payment` to pay off `balance` (mirrors account_edit.term_for_payment); null if it never does. */
export function termForPayment(balance: number, aprPct: number, payment: number): number | null {
  if (!(payment > 0) || !(balance > 0)) return null
  const r = (aprPct || 0) / 1200
  if (r === 0) return Math.max(1, Math.ceil(balance / payment))
  if (payment <= r * balance) return null
  return Math.max(1, Math.ceil(-Math.log(1 - (r * balance) / payment) / Math.log(1 + r)))
}
