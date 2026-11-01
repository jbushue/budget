<template>
  <div v-if="showRefill || showSpending" class="extras">
    <div class="extras-title">{{ kind.group === 'benefits' ? 'Benefits and spending' : 'Refills and spending' }} <span class="muted">(optional)</span></div>
    <div v-if="showRefill" class="grid2">
      <div class="form-group">
        <label>{{ refillLabel }} each month</label>
        <input v-model.number="model.refillAmount" type="number" step="0.01" min="0" placeholder="0.00" />
      </div>
      <div class="form-group">
        <label>On day (1-31)</label>
        <input v-model.number="model.refillDay" type="number" min="1" max="31" placeholder="e.g. 5" />
      </div>
    </div>
    <template v-if="showSpending">
      <div class="form-group">
        <label>{{ spendLabel }} per week</label>
        <input v-model.number="model.weeklySpending" type="number" step="0.01" min="0" placeholder="0.00" />
      </div>
      <label class="inline">
        <input v-model="model.offsetsEveryday" type="checkbox" />
        This replaces part of my everyday spending
      </label>
      <small class="muted">
        Checked: on days this account has money, it pays for that part of your everyday spending so it doesn't also
        come out of checking. Once it runs out, checking covers it again until the next refill.
      </small>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { hasRefill, hasSpending, kindInfo } from '../utils/accountKinds'

export interface AccountExtras {
  refillAmount: number | string | null
  refillDay: number | string | null
  weeklySpending: number | string | null
  offsetsEveryday: boolean
}

const props = defineProps<{ type: string }>()
const model = defineModel<AccountExtras>({ required: true })

const kind = computed(() => kindInfo(props.type))
const showRefill = computed(() => hasRefill(props.type))
const showSpending = computed(() => hasSpending(props.type))
const refillLabel = computed(() => ({ ebt: 'Benefits added', hsa: 'Contributions', fsa: 'Contributions',
  investment: 'Contributions', retirement: 'Contributions' } as Record<string, string>)[props.type] ?? 'Money added')
const spendLabel = computed(() => kind.value.purpose === 'food' ? 'Groceries bought with it'
  : kind.value.purpose === 'medical' ? 'Medical costs paid with it' : 'Spent from it')
</script>

<style scoped>
.extras { border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem 0.9rem 0.6rem; margin-bottom: 1rem; background: var(--surface-alt); }
.extras-title { font-size: 0.82rem; font-weight: 650; margin-bottom: 0.6rem; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 0.75rem; }
.inline { display: flex; gap: 0.5rem; align-items: center; font-size: 0.85rem; font-weight: 500; text-transform: none; letter-spacing: normal; color: var(--text); margin-bottom: 0.3rem; }
.inline input { width: auto; }
small { display: block; font-size: 0.75rem; line-height: 1.4; margin-bottom: 0.4rem; }
</style>
