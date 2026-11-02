<template>
  <div class="auto-sync">
    <label class="inline">
      Sync automatically
      <select v-model.number="hours" @change="save">
        <option :value="0">Off — only when I click</option>
        <option :value="1">Every hour</option>
        <option :value="2">Every 2 hours</option>
        <option :value="4">Every 4 hours</option>
        <option :value="6">Every 6 hours</option>
        <option :value="12">Every 12 hours</option>
        <option :value="24">Once a day</option>
      </select>
    </label>
    <label class="inline"><input v-model="importTx" type="checkbox" @change="save" /> also download new transactions</label>
    <span v-if="message" :class="ok ? 'positive' : 'negative'" class="msg">{{ message }}</span>
    <div v-if="hours && lastResult" class="last">Last automatic sync — {{ lastResult }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMutation, useQuery } from '@vue/apollo-composable'
import { GET_SETTINGS, UPDATE_SETTINGS } from '../graphql/queries'
import type { AppSettings, MutationPayload } from '../types'

const { result } = useQuery<{ settings: string | AppSettings }>(GET_SETTINGS, { fetchPolicy: 'network-only' })
const { mutate } = useMutation<{ updateSettings: MutationPayload }>(UPDATE_SETTINGS)

const hours = ref(0)
const importTx = ref(true)
const lastResult = ref('')
const message = ref('')
const ok = ref(true)

watch(result, r => {
  if (!r?.settings) return
  const s = (typeof r.settings === 'string' ? JSON.parse(r.settings) : r.settings) as AppSettings
  hours.value = s.simplefin_auto_sync_hours
  importTx.value = s.simplefin_auto_import
  lastResult.value = s.last_simplefin_result
}, { immediate: true })

async function save() {
  try {
    const res = await mutate({ variables: { changes: JSON.stringify({ simplefin_auto_sync_hours: hours.value, simplefin_auto_import: importTx.value }) } })
    const p = res?.data?.updateSettings
    ok.value = !!p?.success
    message.value = p?.success ? 'Saved' : (p?.message || 'Could not save')
  } catch (e) {
    ok.value = false
    message.value = e instanceof Error ? e.message : 'Could not save'
  }
  setTimeout(() => { message.value = '' }, 2500)
}
</script>

<style scoped>
.auto-sync { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; align-items: center; margin-bottom: 1rem; }
.inline { display: flex; gap: 0.5rem; align-items: center; font-size: 0.85rem; font-weight: normal; text-transform: none; letter-spacing: normal; color: var(--text); margin: 0; }
.inline select { width: auto; }
.msg { font-size: 0.8rem; }
.last { flex-basis: 100%; font-size: 0.8rem; color: var(--text-muted); }
</style>
