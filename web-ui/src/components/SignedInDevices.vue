<template>
  <div>
    <h4 class="sub-h">Signed-in devices</h4>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else class="table-wrap">
      <table>
        <thead><tr><th>Device</th><th>Address</th><th>Last active</th><th>Signed in</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in sessions" :key="s.id">
            <td>{{ s.device }} <span v-if="s.current" class="badge badge-success">this device</span></td>
            <td>{{ s.ip || '-' }}</td>
            <td>{{ when(s.last_seen) }}</td>
            <td>{{ when(s.created_at) }}</td>
            <td class="actions">
              <button v-if="!s.current" class="btn btn-outline btn-sm" @click="signOut(s)">Sign out</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="btn-row" style="margin-top:0.6rem">
      <button v-if="sessions.length > 1" class="btn btn-outline btn-sm" @click="signOutOthers">Sign out all other devices</button>
      <span v-if="message" :class="ok ? 'positive' : 'negative'" class="msg">{{ message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { listSessions, revokeOtherSessions, revokeSession, type DeviceSession, type Result } from '../utils/auth'
import { ask } from '../utils/dialog'

const sessions = ref<DeviceSession[]>([])
const loading = ref(true)
const message = ref('')
const ok = ref(true)

async function load() {
  const res = await listSessions()
  loading.value = false
  if (res.success) sessions.value = res.sessions ?? []
}
onMounted(load)

function when(iso: string | null) {
  if (!iso) return '-'
  try { return formatDistanceToNow(parseISO(iso), { addSuffix: true }) } catch { return iso }
}

async function done(res: Result) {
  ok.value = res.success
  message.value = res.message || (res.success ? 'Done' : 'Failed')
  await load()
}

async function signOut(s: DeviceSession) {
  done(await revokeSession(s.id))
}

async function signOutOthers() {
  if (await ask('Sign out everywhere except this device?', { title: 'Sign out other devices', confirmText: 'Sign them out' })) done(await revokeOtherSessions())
}
</script>

<style scoped>
.sub-h { margin: 1.1rem 0 0.4rem; font-size: 0.9rem; }
.actions { text-align: right; }
.msg { font-size: 0.85rem; }
</style>
