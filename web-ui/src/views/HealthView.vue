<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Health check</h2>
        <p class="view-sub">A quick read on savings, debt, and your safety net.</p>
      </div>
    </div>

    <div v-if="loading && !health" class="loading">Checking...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="health">
      <div v-if="health.score == null" class="empty-state">
        <div class="icon"><Icon name="health" :size="26" /></div>
        <p>Add your accounts, income and bills (and ideally a few months of transactions) to get a health check.</p>
      </div>

      <template v-else>
        <div class="card score-card">
          <div class="score-ring" :style="{ '--pct': health.score, '--ring': ringColor(health.score) }">
            <div class="score-inner">
              <div class="score-num">{{ health.score }}</div>
              <div class="score-grade">Grade {{ health.grade }}</div>
            </div>
          </div>
          <div class="score-text">
            <h3 style="margin:0 0 0.35rem">{{ headline }}</h3>
            <p class="muted" style="margin:0 0 0.6rem">
              A score from {{ health.factors.length }} checks of how sturdy your finances are. It's a guide, not a credit score.
            </p>
            <ol v-if="health.topTips.length" class="tips">
              <li v-for="t in health.topTips" :key="t">{{ t }}</li>
            </ol>
          </div>
        </div>

        <div class="factors">
          <div v-for="f in health.factors" :key="f.key" class="card factor" :class="f.status">
            <div class="f-head">
              <span class="f-label">{{ f.label }}</span>
              <span class="badge cap" :class="badge(f.status)">{{ f.status }}</span>
            </div>
            <div class="f-value">{{ f.value }}</div>
            <div class="progress-bar"><div class="progress-fill" :style="{ width: f.score + '%', background: ringColor(f.score) }"></div></div>
            <p class="f-detail">{{ f.detail }}</p>
            <p v-if="f.tip" class="f-tip">{{ f.tip }}</p>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import Icon from '../components/Icon.vue'
import { computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { GET_HEALTH_CHECK } from '../graphql/planning'
import type { HealthCheck } from '../types'

const { result, loading, error } = useQuery<{ healthCheck: HealthCheck }>(GET_HEALTH_CHECK,
  { fetchPolicy: 'cache-and-network' })
const health = computed(() => result.value?.healthCheck)

const headline = computed(() => {
  const s = health.value?.score ?? 0
  if (s >= 85) return 'Excellent — your finances are in great shape'
  if (s >= 70) return 'Good — a few things to tighten up'
  if (s >= 55) return 'Fair — some areas need attention'
  return 'Needs work — start with the tips below'
})

function ringColor(score: number) {
  return score >= 75 ? 'var(--success)' : score >= 45 ? 'var(--warning)' : 'var(--danger)'
}

function badge(status: string) {
  return status === 'good' ? 'badge-success' : status === 'fair' ? 'badge-warning' : 'badge-danger'
}
</script>

<style scoped>
.muted { color: var(--text-muted); }
.score-card { display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; margin-bottom: 1.5rem; }
.score-ring {
  width: 140px; height: 140px; border-radius: 50%; flex: 0 0 140px; display: grid; place-items: center;
  background: conic-gradient(var(--ring) calc(var(--pct) * 1%), var(--border) 0);
}
.score-inner { width: 112px; height: 112px; border-radius: 50%; background: var(--card-bg); display: grid; place-content: center; text-align: center; }
.score-num { font-size: 2.2rem; font-weight: 700; line-height: 1; }
.score-grade { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; }
.score-text { flex: 1 1 280px; }
.tips { margin: 0; padding-left: 1.2rem; font-size: 0.9rem; }
.tips li { margin-bottom: 0.3rem; }
.factors { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
.factor { margin: 0; border-top: 3px solid var(--success); }
.factor.fair { border-top-color: var(--warning); }
.factor.poor { border-top-color: var(--danger); }
.f-head { display: flex; justify-content: space-between; align-items: center; }
.f-label { font-weight: 600; }
.f-value { font-size: 1.5rem; font-weight: 700; margin: 0.35rem 0; }
.f-detail { font-size: 0.82rem; color: var(--text-muted); margin: 0.5rem 0 0; }
.f-tip { font-size: 0.85rem; margin: 0.5rem 0 0; }
@media (max-width: 560px) { .score-card { justify-content: center; text-align: center; } .tips { text-align: left; } }
</style>
