<template>
  <div class="insight-list">
    <div v-for="(item, i) in items" :key="i" class="insight" :class="`insight-${item.severity}`">
      <div class="insight-icon">{{ ICONS[item.severity] }}</div>
      <div class="insight-body">
        <div class="insight-title">
          {{ item.title }}
          <span v-if="item.date" class="insight-date">{{ fmtDateShort(item.date) }}</span>
        </div>
        <div v-if="!compact" class="insight-detail">{{ item.detail }}</div>
      </div>
      <div v-if="Math.abs(item.impact) >= 0.01" class="insight-impact" :class="item.impact > 0 ? 'positive' : 'negative'"
           :title="item.impact > 0 ? 'Estimated money saved or gained' : 'Estimated money at risk'">
        {{ item.impact > 0 ? 'saves' : 'risk' }} {{ currency(Math.abs(item.impact)) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { currency, fmtDateShort } from '../utils/format'
import type { Insight, InsightSeverity } from '../types'

defineProps<{ items: Insight[]; compact?: boolean }>()

const ICONS: Record<InsightSeverity, string> = {
  urgent: '🚨', warning: '⚠️', savings: '💡', tip: '📈', good: '✅',
}
</script>

<style scoped>
.insight-list { display: flex; flex-direction: column; gap: 0.5rem; }
.insight {
  display: flex; align-items: flex-start; gap: 0.75rem;
  padding: 0.65rem 0.85rem; border-radius: var(--radius);
  border-left: 4px solid var(--border); background: var(--surface-alt);
}
.insight-urgent { border-left-color: var(--danger); background: var(--danger-light); }
.insight-warning { border-left-color: var(--warning); background: var(--warning-light); }
.insight-savings { border-left-color: var(--primary); background: var(--primary-light); }
.insight-tip { border-left-color: var(--primary); }
.insight-good { border-left-color: var(--success); background: var(--success-light); }
.insight-icon { font-size: 1.1rem; line-height: 1.4; }
.insight-body { flex: 1; min-width: 0; }
.insight-title { font-weight: 600; font-size: 0.9rem; }
.insight-date { font-weight: 400; font-size: 0.75rem; color: var(--text-muted); margin-left: 0.4rem; }
.insight-detail { font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem; line-height: 1.45; }
.insight-impact { font-weight: 700; font-size: 0.85rem; white-space: nowrap; }
</style>
