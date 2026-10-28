<template>
  <div class="bell-wrap">
    <button class="bell" :class="{ urgent: urgentCount }" :title="alerts.length ? `${alerts.length} alerts` : 'No alerts'" @click="open = !open">
      🔔<span v-if="alerts.length" class="count">{{ alerts.length }}</span>
    </button>
    <div v-if="open" class="panel card" @click.stop>
      <div class="panel-head">
        <strong>Alerts</strong>
        <button class="x" @click="open = false">✕</button>
      </div>
      <div v-if="!alerts.length" class="empty">✅ Nothing needs your attention.</div>
      <div v-for="a in alerts" :key="a.key" class="alert" :class="`sev-${a.severity}`">
        <div class="a-main" @click="go(a)">
          <div class="a-title">{{ ICON[a.severity] }} {{ a.title }}</div>
          <div class="a-detail">{{ a.detail }}</div>
        </div>
        <div class="a-actions">
          <button title="Hide for a day" @click="dismiss(a, 1)">Snooze</button>
          <button title="Hide until it changes" @click="dismiss(a)">Dismiss</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_ALERTS, DISMISS_ALERT, GET_SETTINGS } from '../graphql/queries'
import type { AlertItem, AppSettings } from '../types'

const ICON: Record<string, string> = { danger: '🚨', warning: '⚠️', info: 'ℹ️' }
const NOTIFIED_KEY = 'budget-notified-alerts'

const router = useRouter()
const open = ref(false)

const { result, refetch } = useQuery<{ alerts: AlertItem[] }>(GET_ALERTS, { fetchPolicy: 'network-only' })
const { result: settingsResult } = useQuery<{ settings: string | AppSettings }>(GET_SETTINGS)
const { mutate: dismissM } = useMutation(DISMISS_ALERT)

const alerts = computed(() => result.value?.alerts ?? [])
const urgentCount = computed(() => alerts.value.filter(a => a.severity === 'danger').length)
const settings = computed<AppSettings | null>(() => {
  const s = settingsResult.value?.settings
  return s ? (typeof s === 'string' ? JSON.parse(s) : s) : null
})

async function dismiss(a: AlertItem, days?: number) {
  await dismissM({ variables: { key: a.key, days: days ?? null } })
  refetch()
}

function go(a: AlertItem) {
  open.value = false
  router.push(a.link || '/')
}

// Browser notifications for new urgent/warning alerts (Settings → Alerts)
watch(alerts, list => {
  if (!settings.value?.browser_notifications || typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  const seen = new Set<string>(JSON.parse(localStorage.getItem(NOTIFIED_KEY) || '[]'))
  for (const a of list) {
    if (a.severity === 'info' || seen.has(a.key)) continue
    const n = new Notification(a.title, { body: a.detail, tag: a.key })
    n.onclick = () => { window.focus(); router.push(a.link || '/') }
    seen.add(a.key)
  }
  localStorage.setItem(NOTIFIED_KEY, JSON.stringify([...seen].slice(-200)))
})

// Refresh every 5 minutes, and when the tab comes back into view
let timer: ReturnType<typeof setInterval> | undefined
const onVisible = () => { if (document.visibilityState === 'visible') refetch() }
const onClickAway = () => { open.value = false }
onMounted(() => {
  timer = setInterval(() => refetch(), 5 * 60 * 1000)
  document.addEventListener('visibilitychange', onVisible)
  document.addEventListener('click', onClickAway)
})
onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisible)
  document.removeEventListener('click', onClickAway)
})

defineExpose({ refetch })
</script>

<style scoped>
.bell-wrap { position: relative; }
.bell { background: var(--card-bg, #fff); border: 1px solid var(--border); border-radius: 999px; width: 40px; height: 40px; cursor: pointer; font-size: 1.1rem; position: relative; }
.bell.urgent { border-color: var(--danger); }
.count { position: absolute; top: -4px; right: -4px; background: var(--primary); color: #fff; border-radius: 999px; font-size: 0.65rem; min-width: 18px; height: 18px; line-height: 18px; padding: 0 4px; font-weight: 700; }
.bell.urgent .count { background: var(--danger); }
.panel { position: absolute; right: 0; top: 48px; width: 360px; max-width: calc(100vw - 2rem); max-height: 70vh; overflow-y: auto; z-index: 50; padding: 0.75rem; box-shadow: 0 10px 30px rgba(0,0,0,0.15); }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.x { background: none; border: none; cursor: pointer; color: var(--text-muted); }
.empty { font-size: 0.9rem; color: var(--text-muted); padding: 0.5rem 0; }
.alert { border-left: 3px solid var(--border-strong); padding: 0.5rem 0.6rem; margin-bottom: 0.4rem; border-radius: 4px; background: var(--bg, #f8fafc); }
.sev-danger { border-left-color: var(--danger); }
.sev-warning { border-left-color: var(--warning); }
.sev-info { border-left-color: var(--primary); }
.a-main { cursor: pointer; }
.a-title { font-weight: 600; font-size: 0.88rem; }
.a-detail { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.1rem; }
.a-actions { display: flex; gap: 0.6rem; margin-top: 0.3rem; }
.a-actions button { background: none; border: none; padding: 0; font-size: 0.75rem; color: var(--primary); cursor: pointer; }
@media (max-width: 767px) {
  .panel { position: fixed; left: 0.5rem; right: 0.5rem; top: calc(60px + env(safe-area-inset-top)); width: auto; max-width: none; max-height: calc(100dvh - 80px); }
  .a-actions button { font-size: 0.85rem; padding: 0.3rem 0; }
}
</style>
