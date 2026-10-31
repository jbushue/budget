<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header"><span class="card-title">🔔 Alerts, matching &amp; email</span></div>
    <div v-if="!form" class="loading">Loading settings...</div>
    <template v-else>
      <div class="grid grid-2">
        <div class="form-group">
          <label>Remind me about bills this many days ahead</label>
          <input v-model.number="form.alert_days_before_due" type="number" min="0" max="30" />
        </div>
        <div class="form-group checks">
          <label><input v-model="form.alert_low_balance" type="checkbox" /> Warn when checking is projected to dip below the cushion</label>
          <label><input v-model="form.auto_match_bills" type="checkbox" /> Mark bills paid automatically when a transaction clearly matches</label>
          <label>
            <input v-model="form.browser_notifications" type="checkbox" @change="askPermission" />
            Browser notifications for urgent alerts
            <span v-if="form.browser_notifications && permission !== 'granted'" class="negative">
              ({{ permission === 'denied' ? 'blocked in your browser settings' : 'allow them when asked' }})
            </span>
          </label>
        </div>
      </div>

      <h4 class="sub-h">Daily email digest (optional)</h4>
      <p class="help">
        A morning email with your safe-to-spend, alerts and bills this pay period. Needs an email account's
        SMTP settings — e.g. Gmail: smtp.gmail.com, port 587, your address, and an
        <a href="https://support.google.com/accounts/answer/185833" target="_blank" rel="noopener">app password</a>.
        The app must be running to send it.
      </p>
      <label class="inline"><input v-model="form.email_enabled" type="checkbox" /> Send the daily digest</label>
      <div class="grid grid-3">
        <div class="form-group"><label>Send to</label><input v-model="form.email_to" type="email" placeholder="you@example.com" /></div>
        <div class="form-group"><label>SMTP server</label><input v-model="form.smtp_host" placeholder="smtp.gmail.com" /></div>
        <div class="form-group"><label>Port</label><input v-model.number="form.smtp_port" type="number" /></div>
        <div class="form-group"><label>Username</label><input v-model="form.smtp_user" autocomplete="off" /></div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="smtpPassword" type="password" autocomplete="new-password" :placeholder="passwordSet ? '•••••• (saved — leave blank to keep)' : ''" />
        </div>
        <div class="form-group checks"><label><input v-model="form.smtp_use_tls" type="checkbox" /> Use STARTTLS</label></div>
      </div>

      <div style="display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap">
        <button class="btn btn-primary" :disabled="saving" @click="save">{{ saving ? 'Saving...' : 'Save' }}</button>
        <button class="btn btn-outline" :disabled="sending" @click="sendTest">{{ sending ? 'Sending...' : 'Send a test digest now' }}</button>
        <button class="btn btn-outline" @click="togglePreview">{{ preview ? 'Hide preview' : 'Preview digest' }}</button>
        <span v-if="message" :class="ok ? 'positive' : 'negative'" style="font-size:0.85rem">{{ message }}</span>
      </div>
      <pre v-if="preview" class="preview">{{ preview }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMutation, useQuery, useApolloClient } from '@vue/apollo-composable'
import { GET_SETTINGS, UPDATE_SETTINGS, SEND_DIGEST_EMAIL, GET_DIGEST_PREVIEW } from '../graphql/queries'
import type { AppSettings, MutationPayload } from '../types'

const FIELDS = ['alert_days_before_due', 'alert_low_balance', 'auto_match_bills', 'browser_notifications',
  'email_enabled', 'email_to', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_use_tls'] as const
type Form = Pick<AppSettings, typeof FIELDS[number]>

const { result, refetch } = useQuery<{ settings: string | AppSettings }>(GET_SETTINGS, { fetchPolicy: 'network-only' })
const { mutate: update } = useMutation<{ updateSettings: MutationPayload }>(UPDATE_SETTINGS)
const { mutate: sendDigest } = useMutation<{ sendDigestEmail: MutationPayload }>(SEND_DIGEST_EMAIL)
const { resolveClient } = useApolloClient()

const form = ref<Form | null>(null)
const smtpPassword = ref('')
const passwordSet = ref(false)
const saving = ref(false)
const sending = ref(false)
const message = ref('')
const ok = ref(true)
const preview = ref('')
const permission = ref(typeof Notification !== 'undefined' ? Notification.permission : 'denied')

watch(result, r => {
  if (!r?.settings) return
  const s = (typeof r.settings === 'string' ? JSON.parse(r.settings) : r.settings) as AppSettings
  form.value = Object.fromEntries(FIELDS.map(k => [k, s[k]])) as Form
  passwordSet.value = !!s.smtp_password_set
}, { immediate: true })

async function askPermission() {
  if (form.value?.browser_notifications && typeof Notification !== 'undefined' && Notification.permission === 'default') {
    permission.value = await Notification.requestPermission()
  }
}

function show(text: string, success: boolean) {
  message.value = text
  ok.value = success
}

async function save(): Promise<boolean> {
  if (!form.value) return false
  saving.value = true
  const changes: Record<string, unknown> = { ...form.value }
  if (smtpPassword.value) changes.smtp_password = smtpPassword.value
  try {
    const res = await update({ variables: { changes: JSON.stringify(changes) } })
    const p = res?.data?.updateSettings
    show(p?.success ? 'Saved' : (p?.message || 'Could not save'), !!p?.success)
    if (p?.success) {
      smtpPassword.value = ''
      refetch()
    }
    return !!p?.success
  } catch (e) {
    show(e instanceof Error ? e.message : String(e), false)
    return false
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  if (!(await save())) return
  sending.value = true
  try {
    const res = await sendDigest()
    const p = res?.data?.sendDigestEmail
    show(p?.message || 'Done', !!p?.success)
  } catch (e) {
    show(e instanceof Error ? e.message : String(e), false)
  } finally {
    sending.value = false
  }
}

async function togglePreview() {
  if (preview.value) {
    preview.value = ''
    return
  }
  const res = await resolveClient().query<{ digestPreview: string }>({ query: GET_DIGEST_PREVIEW, fetchPolicy: 'network-only' })
  preview.value = res.data?.digestPreview || ''
}
</script>

<style scoped>
.help { font-size: 0.8rem; color: var(--text-muted); margin: 0 0 0.6rem; }
.sub-h { margin: 0.75rem 0 0.4rem; font-size: 0.9rem; }
.checks { display: flex; flex-direction: column; gap: 0.4rem; justify-content: center; }
.checks label, .inline { display: flex; gap: 0.5rem; align-items: center; font-size: 0.85rem; font-weight: normal; text-transform: none; letter-spacing: normal; color: var(--text); }
.inline { margin-bottom: 0.6rem; }
.preview { background: var(--surface-alt); border: 1px solid var(--border); border-radius: 6px; padding: 0.75rem; font-size: 0.78rem; white-space: pre-wrap; margin-top: 0.75rem; }
</style>
