<template>
  <Teleport to="body">
    <div v-if="open" class="cp-overlay" @click.self="close">
      <div class="cp" role="dialog" aria-modal="true" aria-label="Search and jump">
        <div class="cp-search">
          <Icon name="search" :size="18" />
          <input ref="input" v-model="query" placeholder="Search pages, accounts, bills, or type an action..."
                 aria-label="Search" aria-controls="cp-results" :aria-activedescendant="`cp-${active}`"
                 @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="run(results[active])"
                 @keydown.esc.prevent="close" />
          <kbd>Esc</kbd>
        </div>
        <div id="cp-results" class="cp-results" role="listbox">
          <template v-for="(item, i) in results" :key="item.id">
            <div v-if="i === 0 || results[i - 1].group !== item.group" class="cp-group">{{ item.group }}</div>
            <button :id="`cp-${i}`" class="cp-item" :class="{ active: i === active }" role="option" :aria-selected="i === active"
                    @mouseenter="active = i" @click="run(item)">
              <span class="cp-icon"><Icon :name="item.icon" :size="16" /></span>
              <span class="cp-label">{{ item.label }}</span>
              <span v-if="item.hint" class="cp-hint">{{ item.hint }}</span>
            </button>
          </template>
          <div v-if="!results.length" class="cp-empty">Nothing matches “{{ query }}”.</div>
        </div>
        <div class="cp-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> to move</span><span><kbd>Enter</kbd> to open</span>
          <span style="margin-left:auto"><kbd>{{ isMac ? '⌘' : 'Ctrl' }}</kbd><kbd>K</kbd> anywhere</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@vue/apollo-composable'
import Icon from './Icon.vue'
import { NAV } from '../utils/nav'
import { GET_ALL_BANKS, GET_ALL_BILLS, GET_ALL_INCOME } from '../graphql/queries'
import { GET_SAVINGS_GOALS } from '../graphql/goals'
import { billName, currency } from '../utils/format'
import { setTheme, themeState } from '../utils/theme'
import { paletteState } from '../utils/palette'
import type { Bank, BillItem, IncomeItem } from '../types'

interface Item { id: string; group: string; label: string; icon: string; hint?: string; keywords?: string; run: () => void }

const router = useRouter()
const open = computed(() => paletteState.open)
const query = ref('')
const active = ref(0)
const input = ref<HTMLInputElement | null>(null)
const isMac = /Mac|iPhone|iPad/.test(navigator.platform)

// Data is only fetched once the palette has been opened (then it's cached)
const loaded = ref(false)
watch(open, o => { if (o) loaded.value = true })
const opts = () => ({ enabled: loaded.value })
const { result: banksR } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS, opts)
const { result: billsR } = useQuery<{ allBills: BillItem[] }>(GET_ALL_BILLS, opts)
const { result: incomeR } = useQuery<{ allIncome: IncomeItem[] }>(GET_ALL_INCOME, opts)
const { result: goalsR } = useQuery<{ savingsGoals: { id: number; name: string; remaining: number }[] }>(GET_SAVINGS_GOALS, opts)

const go = (path: string) => () => router.push(path)

const ACTIONS: Item[] = [
  { id: 'a-txn', group: 'Actions', label: 'Add a transaction', icon: 'plus', keywords: 'new spend purchase expense', run: go('/transactions?action=add') },
  { id: 'a-bill', group: 'Actions', label: 'Add a bill', icon: 'bills', keywords: 'new payment recurring', run: go('/bills?action=add') },
  { id: 'a-income', group: 'Actions', label: 'Add income', icon: 'income', keywords: 'paycheck salary new', run: go('/income?action=add') },
  { id: 'a-goal', group: 'Actions', label: 'Start a savings goal', icon: 'goals', keywords: 'new save sinking fund', run: go('/goals?action=add') },
  { id: 'a-move', group: 'Actions', label: 'Move money between accounts', icon: 'repeat', keywords: 'transfer savings checking', run: go('/accounts?action=transfer') },
  { id: 'a-bal', group: 'Actions', label: 'Update all balances', icon: 'pencil', keywords: 'check in balance refresh reconcile', run: go('/accounts?action=balances') },
  { id: 'a-acct', group: 'Actions', label: 'Add an account', icon: 'accounts', keywords: 'new checking savings card cash hsa investment retirement', run: go('/accounts?action=add') },
  { id: 'a-ebt', group: 'Actions', label: 'Add an EBT / SNAP card', icon: 'tag', keywords: 'food stamps benefits wic snap ebt', run: go('/accounts?action=add&q=ebt') },
  { id: 'a-debt', group: 'Actions', label: 'How much extra can I put toward debt?', icon: 'card', keywords: 'pay off faster avalanche snowball extra payment optimizer', run: go('/optimizer?tool=debt') },
  { id: 'a-buy', group: 'Actions', label: 'When can I afford a purchase?', icon: 'banknote', keywords: 'buy big purchase afford spend', run: go('/optimizer?tool=buy') },
  { id: 'a-dates', group: 'Actions', label: 'Find better bill due dates', icon: 'calendar', keywords: 'due date move payday', run: go('/optimizer?tool=dates') },
  { id: 'a-digest', group: 'Actions', label: 'Preview the daily email', icon: 'bell', keywords: 'digest email notification', run: go('/settings?tab=alerts') },
  { id: 'a-ics', group: 'Actions', label: 'Download bills & paydays calendar', icon: 'calendar', keywords: 'ics google apple outlook export', run: () => { window.location.href = '/files/calendar.ics' } },
  { id: 'a-xlsx', group: 'Actions', label: 'Export everything to Excel', icon: 'download', keywords: 'backup spreadsheet xlsx', run: () => { window.location.href = '/files/export.xlsx' } },
  { id: 'a-print', group: 'Actions', label: 'Print or save this page as PDF', icon: 'printer', keywords: 'pdf report', run: () => setTimeout(() => window.print(), 50) },
  { id: 'a-theme', group: 'Actions', label: 'Switch light / dark mode', icon: 'moon', keywords: 'theme dark light appearance', run: () => setTheme(themeState.dark ? 'light' : 'dark') },
]

const PAGES: Item[] = NAV.flatMap(g => g.items.map(i => ({
  id: `p-${i.path}`, group: 'Pages', label: i.label, icon: i.icon, hint: g.label || undefined, run: go(i.path),
})))

const DATA = computed<Item[]>(() => {
  const out: Item[] = []
  for (const b of banksR.value?.allBanks ?? []) {
    const accts = [
      ...b.bankAccounts.map(a => [a.accountName, currency(a.balance)]),
      ...b.creditAccounts.map(a => [a.accountName, `${currency(a.balance)} owed`]),
      ...b.mortgageAccounts.map(a => [a.accountName, `${currency(a.currentPrincipal)} owed`]),
      ...b.helocAccounts.map(a => [a.accountName, `${currency(a.balance)} owed`]),
    ]
    for (const [name, hint] of accts) {
      out.push({ id: `acc-${b.name}-${name}`, group: 'Accounts', label: `${b.name} · ${name}`, icon: 'accounts', hint, run: go('/accounts') })
    }
  }
  for (const bill of billsR.value?.allBills ?? []) {
    out.push({ id: `bill-${bill.billName}`, group: 'Bills', label: billName(bill.billName), icon: 'bills',
      hint: currency(bill.effectiveAmount ?? bill.amount), run: go('/bills') })
  }
  for (const inc of incomeR.value?.allIncome ?? []) {
    out.push({ id: `inc-${inc.sourceName}`, group: 'Income', label: inc.sourceName, icon: 'income', hint: currency(inc.amount), run: go('/income') })
  }
  for (const g of goalsR.value?.savingsGoals ?? []) {
    out.push({ id: `goal-${g.id}`, group: 'Goals', label: g.name, icon: 'goals', hint: `${currency(g.remaining)} to go`, run: go('/goals') })
  }
  return out
})

function score(item: Item, q: string): number {
  const label = item.label.toLowerCase()
  const hay = `${label} ${item.keywords ?? ''} ${item.hint ?? ''}`.toLowerCase()
  if (label.startsWith(q)) return 3
  if (label.split(/[\s·]+/).some(w => w.startsWith(q))) return 2
  if (hay.includes(q)) return 1
  return 0
}

const results = computed<Item[]>(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return [...ACTIONS.slice(0, 6), ...PAGES]
  const ranked = [...ACTIONS, ...PAGES, ...DATA.value]
    .map(item => ({ item, s: score(item, q) }))
    .filter(r => r.s > 0)
  const order = ['Pages', 'Actions', 'Accounts', 'Bills', 'Income', 'Goals']
  ranked.sort((a, b) => order.indexOf(a.item.group) - order.indexOf(b.item.group) || b.s - a.s)
  const items = ranked.slice(0, 40).map(r => r.item)
  items.push({ id: 'search-txn', group: 'Transactions', label: `Search transactions for “${query.value.trim()}”`, icon: 'search',
    run: go(`/transactions?action=search&q=${encodeURIComponent(query.value.trim())}`) })
  return items
})

watch(results, () => { active.value = 0 })
watch(open, async o => {
  if (!o) return
  query.value = ''
  active.value = 0
  await nextTick()
  input.value?.focus()
})

function move(step: number) {
  const n = results.value.length
  if (!n) return
  active.value = (active.value + step + n) % n
  document.getElementById(`cp-${active.value}`)?.scrollIntoView({ block: 'nearest' })
}

function run(item?: Item) {
  if (!item) return
  close()
  item.run()
}

function close() {
  paletteState.open = false
}

function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    paletteState.open = !paletteState.open
  } else if (e.key === '/' && !paletteState.open && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement)) {
    e.preventDefault()
    paletteState.open = true
  }
}
onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>

<style scoped>
.cp-overlay { position: fixed; inset: 0; z-index: 300; background: var(--backdrop); display: flex; justify-content: center; align-items: flex-start; padding: 12vh 1rem 1rem; animation: fade-in 0.12s ease; }
.cp { width: min(620px, 100%); background: var(--surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: var(--shadow-lg); overflow: hidden; display: flex; flex-direction: column; max-height: 72vh; animation: pop-in 0.14s ease; }
.cp-search { display: flex; align-items: center; gap: 0.6rem; padding: 0.85rem 1rem; border-bottom: 1px solid var(--border); color: var(--text-light); }
.cp-search input { flex: 1; border: none; outline: none; background: none; box-shadow: none; padding: 0; font-size: 1rem; color: var(--text); }
.cp-search input:focus { box-shadow: none; }
.cp-results { overflow-y: auto; padding: 0.35rem; }
.cp-group { font-size: 0.7rem; font-weight: 650; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em; padding: 0.6rem 0.65rem 0.25rem; }
.cp-item { display: flex; align-items: center; gap: 0.65rem; width: 100%; border: none; background: none; text-align: left; cursor: pointer; padding: 0.5rem 0.65rem; border-radius: 8px; color: var(--text); font: inherit; font-size: 0.9rem; }
.cp-item.active { background: var(--primary-light); }
.cp-icon { width: 28px; height: 28px; flex: 0 0 28px; border-radius: 7px; display: grid; place-items: center; background: var(--surface-alt); color: var(--text-muted); }
.cp-item.active .cp-icon { background: var(--primary); color: #fff; }
.cp-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.cp-hint { font-size: 0.78rem; color: var(--text-light); font-variant-numeric: tabular-nums; white-space: nowrap; }
.cp-empty { padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }
.cp-foot { display: flex; gap: 1rem; padding: 0.55rem 1rem; border-top: 1px solid var(--border); font-size: 0.75rem; color: var(--text-light); }
kbd { display: inline-block; min-width: 1.4em; padding: 0.05rem 0.35rem; margin-right: 0.2rem; border: 1px solid var(--border); border-bottom-width: 2px; border-radius: 5px; font: inherit; font-size: 0.72rem; text-align: center; color: var(--text-muted); background: var(--surface-alt); }
@media (max-width: 560px) {
  .cp-overlay { padding-top: 0.75rem; }
  .cp-foot { display: none; }
}
</style>
