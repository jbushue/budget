<template>
  <div class="server-backups">
    <h4 class="sub-h">Automatic backups on the server</h4>
    <p class="help">
      A copy of the database is made once a day and kept in <code>{{ folder || 'the backups folder' }}</code>
      next to it. Restores also save the data they replace there first.
    </p>
    <div class="btn-row auto-row">
      <label class="inline"><input v-model="auto" type="checkbox" /> Back up every day</label>
      <label class="inline">
        after
        <select v-model.number="hour">
          <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ hourLabel(h - 1) }}</option>
        </select>
      </label>
      <label class="inline">
        keep the last
        <input v-model.number="keep" type="number" min="1" max="365" class="keep" />
      </label>
      <button class="btn btn-outline btn-sm" :disabled="busy" @click="saveSettings">Save</button>
      <button class="btn btn-success btn-sm" :disabled="busy" @click="backupNow">Back up now</button>
    </div>
    <p v-if="lastDate" class="help">Last automatic backup: {{ fmtDate(lastDate) }}</p>

    <div v-if="list.length" class="table-wrap">
      <table>
        <thead><tr><th>Backup</th><th>Kind</th><th>Made</th><th style="text-align:right">Size</th><th></th></tr></thead>
        <tbody>
          <tr v-for="b in shown" :key="b.name">
            <td class="mono">{{ b.name }}</td>
            <td>{{ KIND[b.kind] || b.kind }}</td>
            <td>{{ fmtDateTime(b.created) }}</td>
            <td style="text-align:right">{{ size(b.size) }}</td>
            <td class="actions">
              <a class="btn btn-outline btn-sm" :href="`/files/backups/${encodeURIComponent(b.name)}`">Download</a>
              <button class="btn btn-outline btn-sm" :disabled="busy" @click="restore(b)">Restore</button>
              <button class="btn btn-danger btn-sm" :disabled="busy" @click="remove(b)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <button v-if="list.length > shown.length" class="btn btn-outline btn-sm more" @click="showAll = true">
      Show all {{ list.length }}
    </button>
    <p v-if="!list.length && !loading" class="help">No backups on the server yet.</p>
    <p v-if="message" :class="ok ? 'positive' : 'negative'" class="msg">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApolloClient, useMutation } from '@vue/apollo-composable'
import { format, parseISO } from 'date-fns'
import { UPDATE_SETTINGS } from '../graphql/queries'
import { authState, checkAuth } from '../utils/auth'
import { fmtDate } from '../utils/format'
import type { MutationPayload } from '../types'

interface Backup { name: string; kind: string; size: number; created: string }

const KIND: Record<string, string> = { auto: 'Automatic', manual: 'Manual', 'before-restore': 'Before a restore' }

const { resolveClient } = useApolloClient()
const { mutate: updateSettings } = useMutation<{ updateSettings: MutationPayload }>(UPDATE_SETTINGS)

const list = ref<Backup[]>([])
const folder = ref('')
const auto = ref(true)
const hour = ref(3)
const keep = ref(14)
const lastDate = ref('')
const loading = ref(true)
const busy = ref(false)
const message = ref('')
const ok = ref(true)
const showAll = ref(false)
const shown = computed(() => (showAll.value ? list.value : list.value.slice(0, 8)))

const hourLabel = (h: number) => format(new Date(2000, 0, 1, h), 'h a')
const fmtDateTime = (iso: string) => { try { return format(parseISO(iso), 'MMM d, yyyy h:mm a') } catch { return iso } }
const size = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)

async function call(method: string, url: string) {
  const r = await fetch(url, { method, credentials: 'same-origin' })
  const data = await r.json().catch(() => ({ message: `Server error (${r.status})` }))
  return { ok: r.ok, data }
}

async function load() {
  const { ok: good, data } = await call('GET', '/files/backups')
  loading.value = false
  if (!good) return show(false, data.message)
  list.value = data.backups
  folder.value = data.folder
  auto.value = data.auto_backup
  hour.value = data.backup_hour
  keep.value = data.backup_keep
  lastDate.value = data.last_backup_date
}
onMounted(load)

function show(success: boolean, text: string) {
  ok.value = success
  message.value = text
}

async function run(method: string, url: string) {
  busy.value = true
  message.value = ''
  try {
    const { ok: good, data } = await call(method, url)
    show(good, data.message || (good ? 'Done' : 'Failed'))
    if (good) await load()
    return good ? data : null
  } finally {
    busy.value = false
  }
}

async function saveSettings() {
  busy.value = true
  try {
    const res = await updateSettings({ variables: { changes: JSON.stringify({ auto_backup: auto.value, backup_hour: hour.value, backup_keep: keep.value }) } })
    const p = res?.data?.updateSettings
    show(!!p?.success, p?.success ? 'Backup settings saved' : (p?.message || 'Could not save'))
  } finally {
    busy.value = false
  }
}

const backupNow = () => run('POST', '/files/backups')

function remove(b: Backup) {
  if (confirm(`Delete the backup ${b.name}?`)) run('DELETE', `/files/backups/${encodeURIComponent(b.name)}`)
}

async function restore(b: Backup) {
  if (!confirm(`Replace ALL current data with the backup from ${fmtDateTime(b.created)}?\n\n`
    + 'A copy of the current data is saved first. User accounts come from the backup too, so you may need to sign in again.')) return
  const data = await run('POST', `/files/backups/${encodeURIComponent(b.name)}/restore`)
  if (data) {
    await checkAuth()
    if (authState.authenticated) await resolveClient().refetchQueries({ include: 'active' })
  }
}
</script>

<style scoped>
.server-backups { margin-top: 1rem; }
.help { font-size: 0.8rem; color: var(--text-muted); margin: 0 0 0.6rem; }
.sub-h { margin: 0.5rem 0 0.4rem; font-size: 0.9rem; }
.inline { display: flex; gap: 0.4rem; align-items: center; font-size: 0.85rem; font-weight: normal; text-transform: none; letter-spacing: normal; color: var(--text); margin: 0; }
.inline select, .inline .keep { width: auto; }
.inline .keep { width: 4.5rem; }
.auto-row { align-items: center; gap: 0.6rem 1rem; margin-bottom: 0.6rem; }
.mono { font-family: ui-monospace, monospace; font-size: 0.78rem; word-break: break-all; }
.actions { text-align: right; white-space: nowrap; }
.actions .btn { margin: 0.1rem 0 0.1rem 0.3rem; text-decoration: none; }
.more { margin-top: 0.5rem; }
.msg { font-size: 0.85rem; margin: 0.5rem 0 0; }
</style>
