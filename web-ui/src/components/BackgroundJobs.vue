<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header">
      <span class="card-title">⏱ Background jobs</span>
      <button class="btn btn-outline btn-sm" @click="refetch()">Refresh</button>
    </div>
    <p class="help">
      While the app is running it checks every couple of minutes for work: rolling bill periods over and recording net
      worth each day, the daily backup, SimpleFIN sync, the email digest and phone notifications.
    </p>
    <div v-if="!rows.length" class="help">Nothing has run since the server started.</div>
    <div v-else class="table-wrap">
      <table>
        <thead><tr><th>Job</th><th>Last run</th><th>Result</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.job">
            <td>{{ LABEL[r.job] || r.job }}</td>
            <td>{{ when(r.at) }}</td>
            <td :class="r.ok ? '' : 'negative'">{{ r.ok ? '' : '⚠ ' }}{{ r.message }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { format, parseISO } from 'date-fns'
import { GET_JOB_STATUS } from '../graphql/queries'
import type { JobStatus } from '../types'

const LABEL: Record<string, string> = {
  maintenance: 'Daily upkeep', backup: 'Automatic backup', simplefin: 'SimpleFIN sync',
  digest: 'Email digest', push: 'Phone notifications', push_summary: 'Morning summary',
}

const { result, refetch } = useQuery<{ jobStatus: string | Record<string, JobStatus> }>(GET_JOB_STATUS, { fetchPolicy: 'network-only' })

const rows = computed(() => {
  const raw = result.value?.jobStatus
  const data = (typeof raw === 'string' ? JSON.parse(raw) : raw) as Record<string, JobStatus> | undefined
  return Object.entries(data ?? {}).map(([job, s]) => ({ job, ...s })).sort((a, b) => b.at.localeCompare(a.at))
})

const when = (iso: string) => { try { return format(parseISO(iso), 'MMM d, h:mm a') } catch { return iso } }
</script>

<style scoped>
.help { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.75rem; }
</style>
