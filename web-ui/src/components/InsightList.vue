<template>
  <div class="insight-list">
    <div v-for="(item, i) in items" :key="i" class="insight" :class="`insight-${item.severity}`">
      <div class="insight-icon"><Icon :name="ICONS[item.severity]" :size="17" /></div>
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
import Icon from './Icon.vue'
import { currency, fmtDateShort } from '../utils/format'
import type { Insight, InsightSeverity } from '../types'

defineProps<{ items: Insight[]; compact?: boolean }>()

const ICONS: Record<InsightSeverity, string> = {
  urgent: 'alertCircle', warning: 'alert', savings: 'bulb', tip: 'trendingUp', good: 'checkCircle',
}
</script>

<style scoped>
.insight-list { display: flex; flex-direction: column; }
.insight { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.7rem 0.15rem; }
.insight + .insight { border-top: 1px solid var(--border); }
.insight-icon {
  flex: 0 0 30px; width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center;
  background: var(--surface-alt); color: var(--text-muted);
}
.insight-urgent .insight-icon { background: var(--danger-light); color: var(--danger-text); }
.insight-warning .insight-icon { background: var(--warning-light); color: var(--warning-text); }
.insight-savings .insight-icon, .insight-tip .insight-icon { background: var(--primary-light); color: var(--primary); }
.insight-good .insight-icon { background: var(--success-light); color: var(--success-text); }
.insight-body { flex: 1; min-width: 0; padding-top: 0.15rem; }
.insight-title { font-weight: 600; font-size: 0.9rem; }
.insight-date { font-weight: 400; font-size: 0.75rem; color: var(--text-muted); margin-left: 0.4rem; }
.insight-detail { font-size: 0.82rem; color: var(--text-muted); margin-top: 0.15rem; line-height: 1.45; }
.insight-impact { font-weight: 650; font-size: 0.82rem; white-space: nowrap; padding-top: 0.2rem; font-variant-numeric: tabular-nums; }
</style>
