<template>
  <div class="month-switcher" role="group" aria-label="Month">
    <button class="btn btn-outline btn-sm" :disabled="!canBack" aria-label="Previous month" @click="step(-1)">
      <Icon name="chevronLeft" :size="16" />
    </button>
    <strong class="month-label">{{ label }}</strong>
    <button class="btn btn-outline btn-sm" :disabled="!canForward" aria-label="Next month" @click="step(1)">
      <Icon name="chevronRight" :size="16" />
    </button>
    <button v-if="modelValue !== thisMonth" class="btn btn-ghost btn-sm" @click="emit('update:modelValue', thisMonth)">This month</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'
import { todayISO } from '../utils/format'

/** Month picker: ‹ November 2026 ›, limited to [min, max] (YYYY-MM). */
const props = defineProps<{ modelValue: string; min?: string; max?: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const thisMonth = todayISO().slice(0, 7)

function shift(month: string, by: number): string {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(y, m - 1 + by, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const label = computed(() => {
  const [y, m] = props.modelValue.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' })
})
const canBack = computed(() => !props.min || shift(props.modelValue, -1) >= props.min)
const canForward = computed(() => !props.max || shift(props.modelValue, 1) <= props.max)

function step(by: number) {
  emit('update:modelValue', shift(props.modelValue, by))
}
</script>

<style scoped>
.month-switcher { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.month-label { min-width: 9.5rem; text-align: center; font-size: 1.05rem; }
</style>
