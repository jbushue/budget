<template>
  <div class="db-info">
    <div v-if="info" class="db-meta">
      <span><Icon name="database" :size="15" /> {{ size(info.sizeBytes) }}</span>
      <code v-if="info.path" :title="info.path">{{ info.path }}</code>
    </div>
    <div v-if="info" class="db-grid">
      <div v-for="t in info.tables" :key="t.table">
        <span>{{ t.label }}</span>
        <strong>{{ t.rows.toLocaleString() }}</strong>
      </div>
    </div>
    <div v-else-if="loading" class="muted" style="font-size:0.85rem">Counting records...</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import Icon from './Icon.vue'
import { GET_DATABASE_INFO } from '../graphql/tools'

interface DbInfo { path: string | null; sizeBytes: number; tables: { table: string; label: string; rows: number }[] }
const { result, loading } = useQuery<{ databaseInfo: DbInfo }>(GET_DATABASE_INFO, () => ({ fetchPolicy: 'cache-and-network' }))
const info = computed(() => result.value?.databaseInfo)

function size(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}
</script>

<style scoped>
.db-info { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); }
.db-meta { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.75rem; }
.db-meta span { display: inline-flex; align-items: center; gap: 0.3rem; font-weight: 600; }
.db-meta code { font-size: 0.76rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.db-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.4rem 1rem; }
.db-grid > div { display: flex; justify-content: space-between; gap: 0.5rem; font-size: 0.84rem; padding: 0.25rem 0; border-bottom: 1px dashed var(--border); }
.db-grid span { color: var(--text-muted); }
.db-grid strong { font-variant-numeric: tabular-nums; font-weight: 600; }
</style>
