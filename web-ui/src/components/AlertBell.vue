<template>
  <div class="bell-wrap">
    <button class="bell" :class="{ urgent: urgentCount, dark }" :title="alerts.length ? `${alerts.length} alerts` : 'No alerts'"
            :aria-label="alerts.length ? `${alerts.length} alerts` : 'No alerts'" @click.stop="open = !open">
      <Icon name="bell" :size="19" /><span v-if="alerts.length" class="count">{{ alerts.length }}</span>
    </button>
    <div v-if="open" class="panel card" @click.stop>
      <div class="panel-head">
        <strong>Alerts</strong>
        <button class="x" aria-label="Close" @click="open = false"><Icon name="x" :size="16" /></button>
      </div>
      <div v-if="!alerts.length" class="empty"><Icon name="checkCircle" :size="18" /> Nothing needs your attention.</div>
      <div v-for="a in alerts" :key="a.key" class="alert" :class="`sev-${a.severity}`">
        <div class="a-main" @click="go(a)">
          <div class="a-title">{{ a.title }}</div>
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
import Icon from './Icon.vue'
import type { AlertItem, AppSettings } from '../types'

defineProps<{ dark?: boolean }>()
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
.bell {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px; width: 38px; height: 38px;
  cursor: pointer; position: relative; display: grid; place-items: center; color: var(--text-muted);
  box-shadow: var(--shadow); transition: color 0.12s, background 0.12s;
}
.bell:hover { color: var(--text); background: var(--surface-hover); }
.bell.dark { background: transparent; border-color: transparent; color: #fff; box-shadow: none; width: 44px; height: 44px; }
.count {
  position: absolute; top: -5px; right: -5px; background: var(--primary); color: #fff; border-radius: 999px;
  font-size: 0.65rem; min-width: 18px; height: 18px; line-height: 18px; padding: 0 5px; font-weight: 700;
  border: 2px solid var(--bg);
}
.bell.dark .count { top: 4px; right: 4px; border-color: var(--sidebar-bg); }
.bell.urgent .count { background: var(--danger); }
.panel {
  position: absolute; right: 0; top: 46px; width: 380px; max-width: calc(100vw - 2rem); max-height: 70vh;
  overflow-y: auto; z-index: 50; padding: 0.5rem; box-shadow: var(--shadow-lg); border-radius: 12px;
}
.panel-head { display: flex; justify-content: space-between; align-items: center; padding: 0.35rem 0.5rem 0.6rem; font-size: 0.9rem; }
.x { background: none; border: none; cursor: pointer; color: var(--text-light); display: grid; padding: 3px; border-radius: 5px; }
.x:hover { color: var(--text); background: var(--surface-hover); }
.empty { display: flex; gap: 0.5rem; align-items: center; font-size: 0.88rem; color: var(--text-muted); padding: 0.75rem 0.5rem 1rem; }
.empty :deep(svg) { color: var(--success); }
.alert { position: relative; padding: 0.6rem 0.7rem 0.6rem 1.25rem; border-radius: 8px; transition: background 0.1s; }
.alert + .alert { margin-top: 2px; }
.alert:hover { background: var(--surface-hover); }
.alert::before { content: ''; position: absolute; left: 0.55rem; top: 0.95rem; width: 7px; height: 7px; border-radius: 50%; background: var(--primary); }
.sev-danger::before { background: var(--danger); }
.sev-warning::before { background: var(--warning); }
.a-main { cursor: pointer; }
.a-title { font-weight: 600; font-size: 0.86rem; }
.a-detail { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.1rem; }
.a-actions { display: flex; gap: 0.75rem; margin-top: 0.35rem; }
.a-actions button { background: none; border: none; padding: 0; font-size: 0.76rem; font-weight: 550; color: var(--text-light); cursor: pointer; }
.a-actions button:hover { color: var(--primary); }
@media (max-width: 767px) {
  .panel { position: fixed; left: 0.5rem; right: 0.5rem; top: calc(60px + env(safe-area-inset-top)); width: auto; max-width: none; max-height: calc(100dvh - 80px); }
  .a-actions button { font-size: 0.85rem; padding: 0.3rem 0; }
}
</style>
