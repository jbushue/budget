<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header"><span class="card-title">🔒 Security</span></div>
    <p class="help">
      <template v-if="authState.passwordSet">
        A password is set. Phones and other computers on your network can open the app after signing in;
        sessions last 30 days. Changing or removing the password signs everyone out.
      </template>
      <template v-else>
        No password — only this computer can open the app. Set one to use it from your phone or another
        device on your network — open <code>http://&lt;this computer's address&gt;:3000</code> there.
      </template>
    </p>
    <div class="grid grid-3">
      <div v-if="authState.passwordSet" class="form-group">
        <label>Current password</label>
        <input v-model="current" type="password" autocomplete="current-password" />
      </div>
      <div class="form-group">
        <label>{{ authState.passwordSet ? 'New password' : 'Password' }}</label>
        <input v-model="next" type="password" autocomplete="new-password" placeholder="At least 8 characters" />
      </div>
      <div class="form-group">
        <label>Confirm</label>
        <input v-model="confirmPw" type="password" autocomplete="new-password" />
      </div>
    </div>
    <div style="display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap">
      <button class="btn btn-primary" :disabled="!next || next !== confirmPw || busy" @click="save">
        {{ authState.passwordSet ? 'Change password' : 'Set password' }}
      </button>
      <button v-if="authState.passwordSet" class="btn btn-outline" :disabled="!current || busy" @click="remove">Remove password</button>
      <button v-if="authState.passwordSet" class="btn btn-outline" @click="logout()">Sign out</button>
      <span v-if="next && confirmPw && next !== confirmPw" class="negative" style="font-size:0.85rem">Passwords don't match</span>
      <span v-if="message" :class="ok ? 'positive' : 'negative'" style="font-size:0.85rem">{{ message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { authState, logout, setPassword } from '../utils/auth'

const current = ref('')
const next = ref('')
const confirmPw = ref('')
const busy = ref(false)
const message = ref('')
const ok = ref(true)

async function run(newPassword: string) {
  busy.value = true
  const res = await setPassword(current.value, newPassword)
  busy.value = false
  ok.value = res.success
  message.value = res.message || (res.success ? 'Saved' : 'Failed')
  if (res.success) current.value = next.value = confirmPw.value = ''
}

function save() { run(next.value) }

function remove() {
  if (confirm('Remove the password? Only this computer will be able to open the app.')) run('')
}
</script>

<style scoped>
.help { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.75rem; }
</style>
