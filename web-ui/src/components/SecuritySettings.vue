<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header">
      <span class="card-title">🔒 Your account</span>
      <button class="btn btn-outline btn-sm" @click="logout()">Sign out</button>
    </div>
    <p class="help">
      Signed in as <strong>{{ authState.user?.username }}</strong>
      <span v-if="authState.user?.is_admin" class="badge badge-info">admin</span>.
      Everyone with an account shares this budget. Sign-ins last 30 days on each device. To use the app from a
      phone or another computer, open <code>http://&lt;this computer's address&gt;:3000</code> there.
    </p>

    <h4 class="sub-h">Change password</h4>
    <div class="grid grid-3">
      <div class="form-group">
        <label>Current password</label>
        <input v-model="current" type="password" autocomplete="current-password" />
      </div>
      <div class="form-group">
        <label>New password</label>
        <input v-model="next" type="password" autocomplete="new-password" placeholder="At least 8 characters" />
      </div>
      <div class="form-group">
        <label>Confirm</label>
        <input v-model="confirmPw" type="password" autocomplete="new-password" />
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" :disabled="!current || !next || next !== confirmPw || busy" @click="save">
        Change password
      </button>
      <span v-if="next && confirmPw && next !== confirmPw" class="negative" style="font-size:0.85rem">Passwords don't match</span>
      <span v-if="message" :class="ok ? 'positive' : 'negative'" style="font-size:0.85rem">{{ message }}</span>
    </div>
  </div>

  <UsersAdmin v-if="authState.user?.is_admin" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { authState, changePassword, checkAuth, logout } from '../utils/auth'
import UsersAdmin from './UsersAdmin.vue'

const current = ref('')
const next = ref('')
const confirmPw = ref('')
const busy = ref(false)
const message = ref('')
const ok = ref(true)

async function save() {
  busy.value = true
  const res = await changePassword(current.value, next.value)
  busy.value = false
  ok.value = res.success
  message.value = res.message || (res.success ? 'Saved' : 'Failed')
  if (res.success) {
    current.value = next.value = confirmPw.value = ''
    await checkAuth()  // clears the generated-password reminder
  }
}
</script>

<style scoped>
.help { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.75rem; }
.sub-h { margin: 0.75rem 0 0.4rem; font-size: 0.9rem; }
</style>
