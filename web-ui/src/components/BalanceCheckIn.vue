<template>
  <div v-if="open" class="modal-overlay" @click.self="emit('close')">
    <div class="modal" style="max-width:640px">
      <h3>Update all balances</h3>
      <p class="muted" style="font-size:0.85rem;margin:-0.25rem 0 1rem">
        Open your bank's app and type in today's balances. Only the ones you change are saved.
        Cards, loans and home equity lines are what you owe.
      </p>
      <div class="checkin">
        <template v-for="b in banks" :key="b.name">
          <div v-if="rowsFor(b.name).length" class="ci-bank">{{ b.name }}</div>
          <label v-for="r in rowsFor(b.name)" :key="r.key" class="ci-row" :class="{ changed: isChanged(r) }">
            <span class="ci-name">
              {{ r.account }}
              <small>{{ r.label }}</small>
            </span>
            <span class="ci-was">was {{ currency(r.original) }}</span>
            <input v-model.number="values[r.key]" type="number" step="0.01" inputmode="decimal" :aria-label="`${r.account} balance`" />
          </label>
        </template>
        <div v-if="!rows.length" class="empty-state"><p>No accounts yet.</p></div>
      </div>
      <div class="modal-actions">
        <span class="muted" style="margin-right:auto;font-size:0.82rem">{{ changedCount }} changed</span>
        <button class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="!changedCount || saving" @click="save">{{ saving ? 'Saving...' : 'Save balances' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation } from '@vue/apollo-composable'
import { UPDATE_BALANCES } from '../graphql/tools'
import { runMutation } from '../utils/mutation'
import { currency, accountTypeLabel } from '../utils/format'
import type { Bank, MutationPayload } from '../types'

const props = defineProps<{ open: boolean; banks: Bank[] }>()
const emit = defineEmits<{ close: []; done: [] }>()

interface Row { key: string; bank: string; account: string; kind: string; label: string; original: number }

const rows = computed<Row[]>(() => props.banks.flatMap(b => [
  ...b.bankAccounts.map(a => ({ kind: 'bank', account: a.accountName, label: accountTypeLabel(a.accountType), original: a.balance })),
  ...b.creditAccounts.filter(a => a.status !== 'closed').map(a => ({ kind: 'credit', account: a.accountName, label: 'Owed', original: a.balance })),
  ...b.mortgageAccounts.map(a => ({ kind: 'mortgage', account: a.accountName, label: `${a.kindLabel ?? 'Mortgage'} owed`, original: a.currentPrincipal })),
  ...b.helocAccounts.map(a => ({ kind: 'heloc', account: a.accountName, label: 'HELOC owed', original: a.balance })),
].map(r => ({ ...r, bank: b.name, key: `${b.name}\u0000${r.kind}\u0000${r.account}` }))))

const values = ref<Record<string, number | string>>({})
const saving = ref(false)

watch(() => props.open, isOpen => {
  if (isOpen) values.value = Object.fromEntries(rows.value.map(r => [r.key, r.original]))
})
// Opened before the accounts loaded (e.g. from a link): fill them in when they arrive
watch(rows, list => {
  if (!props.open) return
  for (const r of list) if (!(r.key in values.value)) values.value[r.key] = r.original
})

const rowsFor = (bank: string) => rows.value.filter(r => r.bank === bank)
function isChanged(r: Row) {
  const v = values.value[r.key]
  return v !== '' && v != null && !Number.isNaN(Number(v)) && Math.abs(Number(v) - r.original) >= 0.005
}
const changedCount = computed(() => rows.value.filter(isChanged).length)

const { mutate } = useMutation<{ updateBalances: MutationPayload }>(UPDATE_BALANCES)

async function save() {
  const updates = rows.value.filter(isChanged).map(r => ({ bank: r.bank, account: r.account, kind: r.kind, balance: Number(values.value[r.key]) }))
  saving.value = true
  const ok = await runMutation(() => mutate({ variables: { updates } }), 'updateBalances',
    { failMessage: 'Could not save the balances', showSuccess: true })
  saving.value = false
  if (ok) { emit('done'); emit('close') }
}
</script>

<style scoped>
.checkin { max-height: min(60vh, 520px); overflow-y: auto; margin: 0 -0.25rem; padding: 0 0.25rem; }
.ci-bank { font-size: 0.75rem; font-weight: 650; color: var(--text-light); letter-spacing: 0.04em; text-transform: uppercase; margin: 0.9rem 0 0.3rem; }
.ci-bank:first-child { margin-top: 0; }
.ci-row {
  display: grid; grid-template-columns: 1fr auto 9.5rem; align-items: center; gap: 0.75rem;
  padding: 0.45rem 0.6rem; border-radius: 8px; margin: 0; cursor: text;
}
.ci-row:hover { background: var(--surface-hover); }
.ci-row.changed { background: var(--primary-light); }
.ci-name { font-weight: 550; display: flex; flex-direction: column; line-height: 1.25; }
.ci-name small { font-weight: 450; color: var(--text-muted); font-size: 0.75rem; }
.ci-was { font-size: 0.78rem; color: var(--text-light); font-variant-numeric: tabular-nums; }
.ci-row input { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 560px) {
  .ci-row { grid-template-columns: 1fr 8rem; }
  .ci-was { display: none; }
}
</style>
