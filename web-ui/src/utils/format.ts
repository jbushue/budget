import { format, parseISO, differenceInDays } from 'date-fns'

export function currency(val: number | null | undefined): string {
  if (val == null) return '$0.00'
  return val.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export function pct(val: number | null | undefined, decimals = 1): string {
  if (val == null) return '0%'
  return `${val.toFixed(decimals)}%`
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    return format(parseISO(iso), 'MMM d, yyyy')
  } catch {
    return iso
  }
}

export function fmtDateShort(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    return format(parseISO(iso), 'MMM d')
  } catch {
    return iso
  }
}

export function daysFromNow(iso: string | null | undefined): number {
  if (!iso) return 0
  try {
    return differenceInDays(parseISO(iso), new Date())
  } catch {
    return 0
  }
}

export function frequencyLabel(freq: string): string {
  const map: Record<string, string> = {
    once: 'One-time',
    weekly: 'Weekly',
    biweekly: 'Bi-weekly',
    monthly: 'Monthly',
    semimonthly: 'Semi-monthly',
    bimonthly: 'Bi-monthly',
    quarterly: 'Quarterly',
    semi_annual: 'Semi-annual',
    yearly: 'Yearly',
  }
  return map[freq] || freq
}

export function accountTypeLabel(type: string): string {
  const map: Record<string, string> = {
    checking: 'Checking',
    savings: 'Savings',
    credit: 'Credit',
    mortgage: 'Mortgage',
    heloc: 'HELOC',
  }
  return map[type] || type
}

export function billTypeLabel(type: string): string {
  const map: Record<string, string> = {
    fixed: 'Fixed',
    floating: 'Variable',
    credit_payment: 'Credit Payment',
    mortgage_payment: 'Mortgage Payment',
    heloc_payment: 'HELOC Payment',
  }
  return map[type] || type
}

export function statusBadge(status: string): string {
  const map: Record<string, string> = {
    active: 'badge-success',
    closed: 'badge-danger',
    frozen: 'badge-warning',
  }
  return map[status] || 'badge-info'
}

/** Today's date as YYYY-MM-DD in the user's local timezone (not UTC). */
export function todayISO(d: Date = new Date()): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
