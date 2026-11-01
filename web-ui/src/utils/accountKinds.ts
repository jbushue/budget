// Kinds of bank account and how the planner treats each (mirrors models/types.py ACCOUNT_KINDS)
import type { AccountGroup, AccountType } from '../types'

export interface KindInfo {
  value: AccountType
  label: string
  group: AccountGroup
  paysBills: boolean
  earns: boolean
  purpose?: 'food' | 'medical'
  hint: string
}

export const BANK_KINDS: KindInfo[] = [
  { value: 'checking', label: 'Checking', group: 'cash', paysBills: true, earns: false, hint: 'Your everyday account. Bills and Safe to spend come from here.' },
  { value: 'savings', label: 'Savings', group: 'savings', paysBills: true, earns: true, hint: 'Earns interest. The optimizer can move spare cash here and back.' },
  { value: 'money_market', label: 'Money market', group: 'savings', paysBills: true, earns: true, hint: 'Treated like savings.' },
  { value: 'cd', label: 'CD', group: 'savings', paysBills: false, earns: true, hint: 'Locked until it matures, so it’s never used to pay bills.' },
  { value: 'cash', label: 'Cash', group: 'cash', paysBills: false, earns: false, hint: 'Cash on hand. Counted in your net worth, not used for bills.' },
  { value: 'prepaid', label: 'Prepaid card', group: 'cash', paysBills: true, earns: false, hint: 'A reloadable card that can pay bills.' },
  { value: 'wallet', label: 'PayPal / Venmo / Cash App', group: 'cash', paysBills: true, earns: false, hint: 'Money sitting in a payment app.' },
  { value: 'ebt', label: 'EBT / SNAP', group: 'benefits', paysBills: false, earns: false, purpose: 'food', hint: 'Food benefits. Never counted as spending money or used for bills; it can pay for part of your groceries.' },
  { value: 'hsa', label: 'HSA', group: 'benefits', paysBills: false, earns: true, purpose: 'medical', hint: 'Health savings. Only for medical costs, so it isn’t spending money.' },
  { value: 'fsa', label: 'FSA', group: 'benefits', paysBills: false, earns: false, purpose: 'medical', hint: 'Flexible spending for medical (or dependent care) costs.' },
  { value: 'investment', label: 'Brokerage', group: 'invested', paysBills: false, earns: true, hint: 'Investments. The rate is the growth you expect per year.' },
  { value: 'retirement', label: 'Retirement', group: 'invested', paysBills: false, earns: true, hint: '401(k), IRA and similar. The rate is the growth you expect per year.' },
  { value: 'other', label: 'Other', group: 'other', paysBills: false, earns: false, hint: 'Anything else. Counted in your net worth only.' },
]

export const GROUP_LABELS: Record<AccountGroup, string> = {
  cash: 'Spending money', savings: 'Savings', benefits: 'Benefits', invested: 'Investments', other: 'Other',
}

export const KIND_GROUPS = (Object.keys(GROUP_LABELS) as AccountGroup[]).map(g => ({
  group: g, label: GROUP_LABELS[g], kinds: BANK_KINDS.filter(k => k.group === g),
}))

export const isBankKind = (v: string) => BANK_KINDS.some(k => k.value === v)
export const kindInfo = (v: string): KindInfo => BANK_KINDS.find(k => k.value === v) ?? BANK_KINDS[BANK_KINDS.length - 1]

/** Label for the rate input of a kind. */
export function rateLabel(v: string): string {
  const k = kindInfo(v)
  if (k.group === 'invested') return 'Expected growth % per year'
  return 'APY %'
}

/** Kinds where a monthly refill / weekly spending make sense. */
export const hasRefill = (v: string) => ['ebt', 'hsa', 'fsa', 'prepaid', 'wallet', 'cash', 'investment', 'retirement', 'other'].includes(v)
export const hasSpending = (v: string) => ['ebt', 'hsa', 'fsa', 'prepaid', 'wallet', 'cash'].includes(v)

export const GROUP_BADGE: Record<AccountGroup, string> = {
  cash: 'badge-info', savings: 'badge-success', benefits: 'badge-warning', invested: 'badge-violet', other: '',
}
