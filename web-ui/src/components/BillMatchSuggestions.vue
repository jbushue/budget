<template>
  <div v-if="matches.length" class="card match-card">
    <div class="card-header">
      <span class="card-title">🔗 Bill payments found in your transactions</span>
      <span class="badge badge-warning">{{ matches.length }} to review</span>
    </div>
    <p class="hint">
      These look like bill payments. Confirming marks the bill paid <strong>without moving money</strong> —
      the payment already happened.
    </p>
    <div v-for="m in shown" :key="m.transaction.id" class="match-row">
      <div class="match-main">
        <div><strong>{{ m.transaction.description }}</strong> · {{ currency(Math.abs(m.transaction.amount)) }} on {{ fmtDateShort(m.transaction.date) }}</div>
        <div class="sub">
          Looks like <strong>{{ m.billName }}</strong> (due {{ fmtDateShort(m.dueDate) }}) — {{ m.reason }}
        </div>
      </div>
      <div class="match-actions">
        <button class="btn btn-success btn-sm" :disabled="busy" @click="confirm(m)">Yes, it's {{ m.billName }}</button>
        <button class="btn btn-outline btn-sm" :disabled="busy" @click="ignore(m)">Not a bill</button>
      </div>
    </div>
    <button v-if="matches.length > limit && !expanded" class="link-btn" @click="expanded = true">
      Show all {{ matches.length }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_BILL_MATCH_SUGGESTIONS, CONFIRM_BILL_MATCH, IGNORE_BILL_MATCH } from '../graphql/goals'
import { runMutation } from '../utils/mutation'
import { currency, fmtDateShort } from '../utils/format'
import type { BillMatch, MutationPayload } from '../types'

const props = withDefaults(defineProps<{ limit?: number }>(), { limit: 3 })
const emit = defineEmits<{ changed: [] }>()

const { result, refetch } = useQuery<{ billMatchSuggestions: BillMatch[] }>(GET_BILL_MATCH_SUGGESTIONS,
  { fetchPolicy: 'network-only' })
const { mutate: confirmM } = useMutation<{ confirmBillMatch: MutationPayload }>(CONFIRM_BILL_MATCH)
const { mutate: ignoreM } = useMutation<{ ignoreBillMatch: MutationPayload }>(IGNORE_BILL_MATCH)

const busy = ref(false)
const expanded = ref(false)
const matches = computed(() => result.value?.billMatchSuggestions ?? [])
const shown = computed(() => expanded.value ? matches.value : matches.value.slice(0, props.limit))

async function confirm(m: BillMatch) {
  busy.value = true
  const res = await runMutation(() => confirmM({ variables: { transactionId: m.transaction.id, billName: m.billName } }),
    'confirmBillMatch')
  busy.value = false
  if (res) {
    refetch()
    emit('changed')
  }
}

async function ignore(m: BillMatch) {
  busy.value = true
  const res = await runMutation(() => ignoreM({ variables: { transactionId: m.transaction.id } }), 'ignoreBillMatch')
  busy.value = false
  if (res) refetch()
}

defineExpose({ refetch })
</script>

<style scoped>
.match-card { border-left: 4px solid var(--warning); }
.hint { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.5rem; }
.match-row { display: flex; gap: 1rem; align-items: center; justify-content: space-between; padding: 0.6rem 0; border-top: 1px solid var(--border); flex-wrap: wrap; }
.match-main { font-size: 0.9rem; }
.sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.15rem; }
.match-actions { display: flex; gap: 0.4rem; }
.link-btn { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 0.82rem; padding: 0.4rem 0 0; }
</style>
