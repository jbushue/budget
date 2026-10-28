<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header"><span class="card-title">💾 Data &amp; backup</span></div>

    <h4 class="sub-h">Excel</h4>
    <p class="help">
      Export everything to a spreadsheet, or fill in the template and import it. Importing only adds new
      items — anything with the same name is skipped.
    </p>
    <div class="row">
      <a class="btn btn-outline btn-sm" href="/files/export.xlsx">⬇ Export to Excel</a>
      <a class="btn btn-outline btn-sm" href="/files/template.xlsx">⬇ Blank template</a>
      <label class="btn btn-outline btn-sm file-btn">
        ⬆ Import from Excel
        <input type="file" accept=".xlsx,.xlsm" @change="upload($event, '/files/import')" />
      </label>
      <a class="btn btn-outline btn-sm" href="/files/transactions.csv">⬇ Transactions (CSV)</a>
    </div>

    <h4 class="sub-h">Backup</h4>
    <p class="help">
      A backup is a copy of the whole database — keep one somewhere safe. Restoring replaces <strong>all</strong>
      current data with the backup (a copy of the current data is kept in the backups folder first).
    </p>
    <div class="row">
      <a class="btn btn-success btn-sm" href="/files/backup.db">⬇ Download backup</a>
      <label class="btn btn-danger btn-sm file-btn">
        ⬆ Restore from backup
        <input type="file" accept=".db,.sqlite,application/octet-stream" @change="restore" />
      </label>
    </div>

    <div v-if="busy" class="loading" style="margin-top:0.75rem">Working...</div>
    <div v-if="message" class="result" :class="ok ? 'positive' : 'negative'">
      {{ message }}
      <ul v-if="details.length"><li v-for="(d, i) in details" :key="i">{{ d }}</li></ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useApolloClient } from '@vue/apollo-composable'

const { resolveClient } = useApolloClient()
const busy = ref(false)
const message = ref('')
const ok = ref(true)
const details = ref<string[]>([])

async function send(file: File, url: string): Promise<Record<string, unknown> | null> {
  busy.value = true
  message.value = ''
  details.value = []
  const body = new FormData()
  body.append('file', file)
  try {
    const r = await fetch(url, { method: 'POST', body, credentials: 'same-origin' })
    const data = await r.json().catch(() => ({ message: `Server error (${r.status})` }))
    ok.value = r.ok
    message.value = data.message || (r.ok ? 'Done' : 'Failed')
    return r.ok ? data : null
  } catch (e) {
    ok.value = false
    message.value = e instanceof Error ? e.message : String(e)
    return null
  } finally {
    busy.value = false
  }
}

async function upload(e: Event, url: string) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const data = await send(file, url)
  const r = data ?? {}
  details.value = [...((r.errors as string[]) ?? []), ...((r.warnings as string[]) ?? [])].slice(0, 10)
  if (data) await resolveClient().refetchQueries({ include: 'active' })
}

async function restore(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!confirm(`Replace ALL current data with "${file.name}"?\n\nA copy of the current data is kept in the backups folder.`)) return
  const data = await send(file, '/files/restore')
  if (data) {
    details.value = data.previous_saved_to ? [`Previous data saved to ${data.previous_saved_to}`] : []
    await resolveClient().refetchQueries({ include: 'active' })
  }
}
</script>

<style scoped>
.help { font-size: 0.8rem; color: var(--text-muted); margin: 0 0 0.6rem; }
.sub-h { margin: 0.5rem 0 0.4rem; font-size: 0.9rem; }
.row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
.row a { text-decoration: none; }
.file-btn { position: relative; overflow: hidden; cursor: pointer; margin: 0; }
.file-btn input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.result { font-size: 0.85rem; margin-top: 0.5rem; }
.result ul { margin: 0.3rem 0 0 1.1rem; color: var(--text-muted); font-size: 0.8rem; }
</style>
