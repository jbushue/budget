<template>
  <div class="login-wrap">
    <div class="card login-card">
      <h1 class="logo">💰 Budget</h1>
      <template v-if="authState.passwordSet">
        <p class="muted">Enter your password to continue.</p>
        <form @submit.prevent="submit">
          <input v-model="password" type="password" placeholder="Password" autocomplete="current-password" autofocus />
          <button class="btn btn-primary" style="width:100%;margin-top:0.75rem" :disabled="!password || busy">
            {{ busy ? 'Signing in...' : 'Sign in' }}
          </button>
        </form>
        <p v-if="error" class="negative" style="font-size:0.85rem;margin-top:0.75rem">{{ error }}</p>
      </template>
      <template v-else>
        <p><strong>This device can't open the app yet.</strong></p>
        <p class="muted">
          To use Budget from your phone or another computer, open it on the computer that runs it and set a
          password in <strong>Settings → Security</strong>. Then come back here and sign in.
        </p>
        <button class="btn btn-outline" style="margin-top:0.5rem" @click="checkAuth()">Try again</button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { authState, checkAuth, login } from '../utils/auth'

const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  const res = await login(password.value)
  busy.value = false
  if (!res.success) error.value = res.message || 'Could not sign in'
  password.value = ''
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1rem; background: var(--bg, #f1f5f9); }
.login-card { width: 100%; max-width: 380px; text-align: center; }
.logo { font-size: 1.6rem; margin: 0 0 0.75rem; }
.muted { color: var(--text-muted); font-size: 0.9rem; }
input { width: 100%; }
</style>
