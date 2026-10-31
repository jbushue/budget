<template>
  <div class="login-wrap">
    <div class="card login-card">
      <h1 class="logo">💰 Budget</h1>

      <!-- No accounts yet, opened somewhere other than the computer running the app -->
      <template v-if="mode === 'blocked'">
        <p><strong>This app isn't set up yet.</strong></p>
        <p class="muted">
          Open it on the computer that runs it and create the first account there. Then come back here and sign in.
        </p>
        <button class="btn btn-outline" style="margin-top:0.5rem" @click="checkAuth()">Try again</button>
      </template>

      <template v-else-if="mode === 'checking'">
        <p class="muted">Checking your link...</p>
      </template>

      <form v-else @submit.prevent="submit">
        <p class="intro">{{ INTRO[mode] }}</p>

        <div v-if="mode === 'join' && !codeFromLink" class="form-group">
          <label for="f-code">Invite code</label>
          <input id="f-code" v-model.trim="code" autocomplete="off" spellcheck="false" />
        </div>

        <div v-if="mode !== 'reset'" class="form-group">
          <label for="f-user">Username</label>
          <input id="f-user" v-model.trim="username" autocomplete="username" autocapitalize="none" spellcheck="false"
                 :placeholder="mode === 'login' ? '' : 'Letters, numbers, . - _'" autofocus />
        </div>
        <p v-else class="muted">Account: <strong>{{ resetFor }}</strong></p>

        <div class="form-group">
          <label for="f-pw">{{ mode === 'reset' ? 'New password' : 'Password' }}</label>
          <input id="f-pw" v-model="password" type="password"
                 :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
                 :placeholder="mode === 'login' ? '' : 'At least 8 characters'" />
        </div>
        <div v-if="mode !== 'login'" class="form-group">
          <label for="f-pw2">Confirm password</label>
          <input id="f-pw2" v-model="confirmPw" type="password" autocomplete="new-password" />
        </div>

        <button class="btn btn-primary submit" :disabled="!canSubmit || busy">
          {{ busy ? 'One moment...' : BUTTON[mode] }}
        </button>
        <p v-if="mismatch" class="negative msg">Passwords don't match</p>
        <p v-if="error" class="negative msg">{{ error }}</p>

        <div class="switch">
          <template v-if="mode === 'login'">
            <a href="#" @click.prevent="switchTo('join')">Have an invite code? Create an account</a>
            <span class="muted">Forgot your password? Ask an admin for a reset link.</span>
          </template>
          <a v-else-if="mode === 'join' || mode === 'reset'" href="#" @click.prevent="switchTo('login')">
            Already have an account? Sign in
          </a>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { authState, checkAuth, takeCodeFromUrl, inspectCode, login, register, resetPassword, setupAdmin } from '../utils/auth'

type Mode = 'setup' | 'login' | 'join' | 'reset'

const INTRO: Record<Mode, string> = {
  setup: 'Welcome! Create the first account. It will be the admin: it can invite other people and manage accounts.',
  login: 'Sign in to continue.',
  join: "You've been invited to share this budget. Pick a username and password.",
  reset: 'Choose a new password.',
}
const BUTTON: Record<Mode, string> = {
  setup: 'Create account', login: 'Sign in', join: 'Create account', reset: 'Save new password',
}

const chosen = ref<Mode | 'checking' | null>(null)
const code = ref('')
const codeFromLink = ref(false)
const resetFor = ref('')
const username = ref('')
const password = ref('')
const confirmPw = ref('')
const error = ref('')
const busy = ref(false)

const mode = computed(() => {
  if (authState.needsSetup) return authState.local ? 'setup' : 'blocked'
  return chosen.value ?? 'login'
})
const mismatch = computed(() => mode.value !== 'login' && !!confirmPw.value && password.value !== confirmPw.value)
const canSubmit = computed(() => {
  if (!password.value) return false
  if (mode.value === 'login') return !!username.value
  if (password.value !== confirmPw.value) return false
  if (mode.value === 'join') return !!username.value && !!code.value
  return mode.value === 'reset' || !!username.value
})

onMounted(async () => {
  const fromUrl = authState.needsSetup ? '' : takeCodeFromUrl()
  if (!fromUrl) return
  chosen.value = 'checking'
  const info = await inspectCode(fromUrl)
  if (info.success) {
    code.value = fromUrl
    codeFromLink.value = true
    chosen.value = info.kind === 'reset' ? 'reset' : 'join'
    resetFor.value = info.username ?? ''
  } else {
    chosen.value = 'login'
    error.value = info.message || "That link isn't valid"
  }
})

function switchTo(m: Mode) {
  chosen.value = m
  error.value = ''
  password.value = confirmPw.value = ''
  if (m === 'login') codeFromLink.value = false
}

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  const res = mode.value === 'setup' ? await setupAdmin(username.value, password.value)
    : mode.value === 'join' ? await register(code.value, username.value, password.value)
      : mode.value === 'reset' ? await resetPassword(code.value, password.value)
        : await login(username.value, password.value)
  busy.value = false
  if (!res.success) {
    error.value = res.message || 'Something went wrong'
    password.value = confirmPw.value = ''
  }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; min-height: 100dvh; display: flex; align-items: center; justify-content: center; padding: 1rem; background: var(--bg); }
.login-card { width: 100%; max-width: 400px; }
.logo { font-size: 1.6rem; margin: 0 0 0.75rem; text-align: center; }
.intro { font-size: 0.92rem; margin: 0 0 1rem; text-align: center; }
.muted { color: var(--text-muted); font-size: 0.88rem; }
.form-group { text-align: left; }
input { width: 100%; }
.submit { width: 100%; margin-top: 0.5rem; }
.msg { font-size: 0.85rem; margin: 0.75rem 0 0; text-align: center; }
.switch { display: flex; flex-direction: column; gap: 0.4rem; align-items: center; margin-top: 1.1rem; font-size: 0.85rem; text-align: center; }
.switch a { color: var(--primary); }
</style>
