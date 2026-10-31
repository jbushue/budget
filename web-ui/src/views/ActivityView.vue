<template>
  <div>
    <div class="view-header">
      <h2>Activity</h2>
      <select v-model="person" class="person" aria-label="Show activity by">
        <option value="">Everyone</option>
        <option v-for="p in people" :key="p" :value="p">{{ p }}</option>
      </select>
    </div>

    <div class="card">
      <p class="help">Every change to the budget, and who made it. Kept for a year.</p>
      <div v-if="loading && !entries.length" class="loading">Loading...</div>
      <div v-else-if="!entries.length" class="empty">Nothing yet.</div>
      <template v-for="day in days" :key="day.date">
        <h4 class="day">{{ day.label }}</h4>
        <ul class="feed">
          <li v-for="e in day.items" :key="e.id">
            <span class="time">{{ time(e.at) }}</span>
            <span class="who" :style="{ background: colorFor(e.username) }" :title="e.username || 'this computer'">
              {{ (e.username || '?').slice(0, 1).toUpperCase() }}
            </span>
            <div class="what">
              <div><strong>{{ e.username || 'This computer' }}</strong> · {{ e.action }}</div>
              <div v-if="e.detail" class="detail">{{ e.detail }}</div>
            </div>
          </li>
        </ul>
      </template>
      <button v-if="more" class="btn btn-outline" style="margin-top:0.75rem" :disabled="loading" @click="loadMore">
        {{ loading ? 'Loading...' : 'Show older' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useApolloClient } from '@vue/apollo-composable'
import { format, isToday, isYesterday, parseISO } from 'date-fns'
import { GET_ACTIVITY } from '../graphql/queries'

interface Entry { id: number; at: string; username: string; action: string; detail: string }

const PAGE = 50
const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

const { resolveClient } = useApolloClient()
const entries = ref<Entry[]>([])
const people = ref<string[]>([])
const person = ref('')
const loading = ref(false)
const more = ref(false)

async function fetchPage(beforeId?: number) {
  loading.value = true
  try {
    const res = await resolveClient().query<{ activity: string | Entry[] }>({
      query: GET_ACTIVITY, fetchPolicy: 'network-only',
      variables: { limit: PAGE, beforeId: beforeId ?? null, username: person.value || null },
    })
    const raw = res.data?.activity
    const page = (typeof raw === 'string' ? JSON.parse(raw) : raw ?? []) as Entry[]
    entries.value = beforeId ? [...entries.value, ...page] : page
    more.value = page.length === PAGE
    for (const e of page) if (e.username && !people.value.includes(e.username)) people.value.push(e.username)
    people.value.sort()
  } finally {
    loading.value = false
  }
}

watch(person, () => fetchPage(), { immediate: true })
const loadMore = () => fetchPage(entries.value[entries.value.length - 1]?.id)

const days = computed(() => {
  const groups: { date: string; label: string; items: Entry[] }[] = []
  for (const e of entries.value) {
    const date = e.at.slice(0, 10)
    let g = groups[groups.length - 1]
    if (!g || g.date !== date) {
      const d = parseISO(e.at)
      g = { date, label: isToday(d) ? 'Today' : isYesterday(d) ? 'Yesterday' : format(d, 'EEEE, MMM d, yyyy'), items: [] }
      groups.push(g)
    }
    g.items.push(e)
  }
  return groups
})

const time = (iso: string) => format(parseISO(iso), 'h:mm a')

function colorFor(name: string) {
  let h = 0
  for (const c of name || '?') h = (h * 31 + c.charCodeAt(0)) >>> 0
  return COLORS[h % COLORS.length]
}
</script>

<style scoped>
.help { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.5rem; }
.person { width: auto; min-width: 10rem; }
.empty { color: var(--text-muted); padding: 1rem 0; }
.day { margin: 1rem 0 0.4rem; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); }
.feed { list-style: none; margin: 0; padding: 0; }
.feed li { display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.55rem 0; border-bottom: 1px solid var(--border); }
.feed li:last-child { border-bottom: none; }
.time { flex: 0 0 4.5rem; font-size: 0.78rem; color: var(--text-muted); padding-top: 0.35rem; }
.who { flex: 0 0 28px; height: 28px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 0.8rem; display: flex; align-items: center; justify-content: center; }
.what { flex: 1; min-width: 0; font-size: 0.88rem; }
.detail { font-size: 0.8rem; color: var(--text-muted); overflow-wrap: anywhere; margin-top: 0.1rem; }
@media (max-width: 767px) {
  .time { flex-basis: 3.8rem; font-size: 0.72rem; }
}
</style>
