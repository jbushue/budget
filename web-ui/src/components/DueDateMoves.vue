<template>
  <div>
    <p class="intro">
      Bills due just before payday squeeze checking. Most companies will move your due date if you ask. These are the
      moves that would help most, tested against your real paydays<template v-if="r?.payday_days?.length"> (the
      {{ r.payday_days.map(ordinal).join(', ') }})</template>.
    </p>
    <div v-if="loading" class="loading">Trying each bill on the days after your paydays...</div>
    <div v-else-if="error" class="callout danger">{{ error.message }}</div>
    <div v-else-if="r && !r.suggestions.length" class="empty-state" style="padding:1rem">
      <p>Your due dates already line up well with your paydays. Nothing to change.</p>
    </div>
    <p v-if="r?.suggestions.length && r.lowest > r.cushion + 500" class="callout success" style="font-size:0.82rem">
      Checking already stays well above your cushion ({{ currency(r.lowest) }} at its lowest), so these are optional:
      they'd just give you more breathing room.
    </p>
    <ul v-else-if="r" class="moves">
      <li v-for="s in r.suggestions" :key="s.bill">
        <div class="mv-main">
          <div class="mv-title">{{ billName(s.bill) }} <span class="muted">{{ currency(s.amount) }}</span></div>
          <div class="mv-days">
            <span class="day old">{{ ordinal(s.current_day) }}</span>
            <Icon name="chevronRight" :size="14" />
            <span class="day new">{{ ordinal(s.suggested_day) }}</span>
            <span class="mv-why" :class="s.fixes_late ? 'negative' : 'positive'">{{ s.why }}</span>
          </div>
          <div class="muted" style="font-size:0.75rem">Lowest checking {{ currency(s.lowest_before) }} → {{ currency(s.lowest_after) }}</div>
        </div>
        <button class="btn btn-outline btn-sm" :disabled="applying === s.bill" @click="apply(s)">
          {{ applying === s.bill ? 'Saving...' : 'I moved it' }}
        </button>
      </li>
    </ul>
    <p v-if="r?.suggestions.length" class="muted" style="font-size:0.78rem;margin:0.6rem 0 0">
      Call or log in to the company first. Once they confirm, click <strong>I moved it</strong> to update the bill here.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMutation, useQuery } from '@vue/apollo-composable'
import Icon from './Icon.vue'
import { GET_DUE_DATE_MOVES } from '../graphql/tools'
import { UPDATE_BILL } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { billName, currency } from '../utils/format'
import type { MutationPayload } from '../types'

interface Move { bill: string; amount: number; current_day: number; suggested_day: number; lowest_before: number
  lowest_after: number; gain: number; fixes_late: number; why: string }

const emit = defineEmits<{ changed: [] }>()
const { result, loading, error, refetch } = useQuery<{ dueDateMoves: string }>(GET_DUE_DATE_MOVES, () => ({
  variables: { days: 100 }, fetchPolicy: 'cache-and-network',
}))
const r = computed<{ suggestions: Move[]; payday_days: number[]; lowest: number; cushion: number } | null>(() => {
  const raw = result.value?.dueDateMoves
  return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : null
})

function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

const applying = ref('')
const { mutate } = useMutation<{ updateBill: MutationPayload }>(UPDATE_BILL)
async function apply(s: Move) {
  applying.value = s.bill
  const ok = await runMutation(() => mutate({ variables: { billName: s.bill, dueDate: s.suggested_day } }), 'updateBill',
    { failMessage: 'Could not update the bill', showSuccess: true })
  applying.value = ''
  if (ok) { refetch(); emit('changed') }
}
</script>

<style scoped>
.intro { font-size: 0.85rem; color: var(--text-muted); margin: 0 0 0.9rem; }
.moves { list-style: none; margin: 0; padding: 0; }
.moves li { display: flex; align-items: center; gap: 1rem; padding: 0.75rem 0; border-bottom: 1px solid var(--border); }
.moves li:last-child { border-bottom: none; }
.mv-main { flex: 1; min-width: 0; }
.mv-title { font-weight: 600; margin-bottom: 0.25rem; }
.mv-days { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; font-size: 0.85rem; margin-bottom: 0.15rem; }
.day { padding: 1px 8px; border-radius: 6px; font-weight: 650; font-variant-numeric: tabular-nums; }
.day.old { background: var(--surface-alt); color: var(--text-muted); text-decoration: line-through; }
.day.new { background: var(--success-light); color: var(--success-text); }
.mv-why { font-weight: 550; margin-left: 0.3rem; }
</style>
