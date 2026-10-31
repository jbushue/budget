<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header"><span class="card-title">👥 Users</span></div>
    <p class="help">
      People join with a one-time invite link that you create here. Admins can invite people, manage accounts,
      and back up or restore the database.
    </p>

    <div v-if="loading" class="loading">Loading users...</div>
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr><th>User</th><th>Role</th><th>Last sign-in</th><th>Joined</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }} <span v-if="u.id === me" class="muted">(you)</span></td>
            <td><span v-if="u.is_admin" class="badge badge-info">Admin</span><template v-else>Member</template></td>
            <td>{{ fmtDate(u.last_login) }}</td>
            <td>{{ fmtDate(u.created_at) }}</td>
            <td class="actions">
              <template v-if="u.id !== me">
                <button class="btn btn-outline btn-sm" @click="toggleAdmin(u)">{{ u.is_admin ? 'Remove admin' : 'Make admin' }}</button>
                <button class="btn btn-outline btn-sm" @click="reset(u)">Reset password</button>
                <button class="btn btn-danger btn-sm" @click="remove(u)">Delete</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <h4 class="sub-h">Invite someone</h4>
    <div class="btn-row invite-form">
      <label class="inline"><input v-model="inviteAdmin" type="checkbox" /> Make them an admin</label>
      <label class="inline">
        Link works for
        <select v-model.number="inviteDays">
          <option :value="1">1 day</option>
          <option :value="7">7 days</option>
          <option :value="30">30 days</option>
        </select>
      </label>
      <button class="btn btn-primary" :disabled="busy" @click="invite">Create invite link</button>
    </div>

    <div v-if="link" class="link-box">
      <div class="link-title">{{ link.title }}</div>
      <div class="link-row">
        <input ref="linkInput" :value="link.url" readonly @focus="($event.target as HTMLInputElement).select()" />
        <button class="btn btn-outline btn-sm" @click="copy">{{ copied ? 'Copied ✓' : 'Copy' }}</button>
      </div>
      <div class="muted">
        {{ link.note }} You won't be able to see this link again; if it gets lost, revoke it and make a new one.
      </div>
    </div>

    <template v-if="invites.length">
      <h4 class="sub-h">Unused links</h4>
      <div class="table-wrap">
        <table>
          <thead><tr><th>For</th><th>Created by</th><th>Expires</th><th></th></tr></thead>
          <tbody>
            <tr v-for="i in invites" :key="i.id">
              <td>{{ i.kind === 'reset' ? `Password reset: ${i.username}` : i.make_admin ? 'New admin' : 'New member' }}</td>
              <td>{{ i.created_by || '-' }}</td>
              <td>{{ fmtDate(i.expires_at) }}</td>
              <td class="actions"><button class="btn btn-outline btn-sm" @click="revoke(i)">Revoke</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <p v-if="message" :class="ok ? 'positive' : 'negative'" class="msg">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import {
  authState, codeLink, createInvite, createResetCode, deleteUser, listUsers, revokeInvite, setAdmin,
  type Invite, type Result, type User,
} from '../utils/auth'
import { fmtDate } from '../utils/format'

const users = ref<User[]>([])
const invites = ref<Invite[]>([])
const loading = ref(true)
const busy = ref(false)
const message = ref('')
const ok = ref(true)
const inviteAdmin = ref(false)
const inviteDays = ref(7)
const link = ref<{ title: string; url: string; note: string } | null>(null)
const linkInput = ref<HTMLInputElement | null>(null)
const copied = ref(false)
const me = computed(() => authState.user?.id)

async function load() {
  const res = await listUsers()
  loading.value = false
  if (res.success) {
    users.value = res.users ?? []
    invites.value = res.invites ?? []
  } else {
    show(res)
  }
}
onMounted(load)

function show(res: Result, success = '') {
  ok.value = res.success
  message.value = res.success ? success : (res.message || 'Something went wrong')
}

async function run(action: Promise<Result>, success = '') {
  busy.value = true
  const res = await action
  busy.value = false
  show(res, success)
  if (res.success) await load()
  return res
}

async function showLink(title: string, code: string | undefined, note: string) {
  if (!code) return
  link.value = { title, url: codeLink(code), note }
  copied.value = false
  await nextTick()
  linkInput.value?.select()
}

async function invite() {
  const res = await run(createInvite(inviteAdmin.value, inviteDays.value))
  const days = inviteDays.value === 1 ? '1 day' : `${inviteDays.value} days`
  if (res.success) {
    await showLink(inviteAdmin.value ? 'Invite link (admin)' : 'Invite link', res.code as string | undefined,
      `Send this to the person you're inviting. It works once, for ${days}.`)
  }
}

async function reset(u: User) {
  if (!confirm(`Make a password reset link for ${u.username}? They'll be signed out on all their devices.`)) return
  const res = await run(createResetCode(u.id))
  if (res.success) {
    await showLink(`Password reset link for ${u.username}`, res.code as string | undefined,
      'Send this to them. It works once, for 2 days.')
  }
}

function toggleAdmin(u: User) {
  run(setAdmin(u.id, !u.is_admin), u.is_admin ? `${u.username} is no longer an admin` : `${u.username} is now an admin`)
}

function remove(u: User) {
  if (confirm(`Delete ${u.username}'s account? The budget itself isn't affected.`)) {
    run(deleteUser(u.id), `Deleted ${u.username}`)
  }
}

function revoke(i: Invite) {
  run(revokeInvite(i.id), 'Link revoked')
  link.value = null
}

async function copy() {
  if (!link.value) return
  try {
    await navigator.clipboard.writeText(link.value.url)
    copied.value = true
  } catch {
    // Clipboard needs HTTPS or localhost; fall back to a selected field
    linkInput.value?.select()
    message.value = 'Press Ctrl+C (or long-press → Copy) to copy the selected link'
    ok.value = true
  }
}
</script>

<style scoped>
.help { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.75rem; }
.sub-h { margin: 1rem 0 0.5rem; font-size: 0.9rem; }
.muted { color: var(--text-muted); font-size: 0.8rem; }
.actions { text-align: right; }
.actions .btn { margin: 0.1rem 0 0.1rem 0.35rem; }
.inline { display: flex; gap: 0.5rem; align-items: center; font-size: 0.85rem; font-weight: normal; text-transform: none; letter-spacing: normal; color: var(--text); margin: 0; }
.inline select { width: auto; }
.invite-form { align-items: center; gap: 0.75rem 1.5rem; }
.link-box { margin-top: 0.85rem; padding: 0.85rem; border: 1px solid var(--primary); border-radius: 8px; background: var(--bg, #f8fafc); }
.link-title { font-weight: 600; font-size: 0.88rem; margin-bottom: 0.4rem; }
.link-row { display: flex; gap: 0.5rem; margin-bottom: 0.4rem; }
.link-row input { flex: 1 1 auto; min-width: 0; font-family: ui-monospace, monospace; font-size: 0.8rem; }
.msg { font-size: 0.85rem; margin: 0.75rem 0 0; }
</style>
