import { reactive } from 'vue'

/** User accounts (see models/auth.py). Everyone shares the same household budget. */
export interface User {
  id: number
  username: string
  is_admin: boolean
  created_at: string | null
  last_login: string | null
}

export interface Invite {
  id: number
  kind: 'invite' | 'reset'
  make_admin: boolean
  username: string | null
  created_by: string | null
  expires_at: string
  created_at: string | null
}

export const authState = reactive({
  checked: false,
  needsSetup: false,
  authenticated: false,
  local: true,
  user: null as User | null,
})

export interface Result { success: boolean; message?: string; [key: string]: unknown }

export async function checkAuth(): Promise<void> {
  try {
    const r = await fetch('/auth/status', { credentials: 'same-origin' })
    const s = await r.json()
    authState.needsSetup = !!s.needs_setup
    authState.local = !!s.local
    authState.user = s.user ?? null
    // Before the first account exists, this computer may use the API, but the UI asks for an account first
    authState.authenticated = !!s.authenticated
  } catch {
    // API down: let the app load and show its own connection errors
    authState.authenticated = true
  }
  authState.checked = true
}

/** Called when the API answers 401/403: show the sign-in screen. */
export function onAuthFailure(): void {
  if (authState.authenticated) checkAuth()
}

async function call(method: string, path: string, body?: unknown): Promise<Result> {
  try {
    const r = await fetch(path, {
      method, credentials: 'same-origin',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const data = await r.json().catch(() => ({}))
    if (r.status === 401 && path !== '/auth/login') onAuthFailure()
    return { ...data, success: r.ok && data.success !== false, message: data.message }
  } catch (e) {
    return { success: false, message: e instanceof Error ? e.message : String(e) }
  }
}

async function andRefresh(res: Promise<Result>): Promise<Result> {
  const out = await res
  if (out.success) await checkAuth()
  return out
}

export const setupAdmin = (username: string, password: string) =>
  andRefresh(call('POST', '/auth/setup', { username, password }))

export const login = (username: string, password: string) =>
  andRefresh(call('POST', '/auth/login', { username, password }))

export async function logout(): Promise<void> {
  await call('POST', '/auth/logout', {})
  await checkAuth()
}

/** What an invite / reset code from a link is for. */
export const inspectCode = (code: string) =>
  call('GET', `/auth/code/${encodeURIComponent(code)}`) as Promise<Result & { kind?: 'invite' | 'reset'; username?: string }>

export const register = (code: string, username: string, password: string) =>
  andRefresh(call('POST', '/auth/register', { code, username, password }))

export const resetPassword = (code: string, password: string) =>
  andRefresh(call('POST', '/auth/reset', { code, password }))

export const changePassword = (currentPassword: string, newPassword: string) =>
  call('POST', '/auth/password', { current_password: currentPassword, new_password: newPassword })

// Admin

export const listUsers = () =>
  call('GET', '/auth/users') as Promise<Result & { users?: User[]; invites?: Invite[] }>

export const createInvite = (makeAdmin: boolean, days: number) =>
  call('POST', '/auth/invites', { make_admin: makeAdmin, days }) as Promise<Result & { code?: string }>

export const revokeInvite = (id: number) => call('DELETE', `/auth/invites/${id}`)

export const setAdmin = (id: number, isAdmin: boolean) => call('PATCH', `/auth/users/${id}`, { is_admin: isAdmin })

export const deleteUser = (id: number) => call('DELETE', `/auth/users/${id}`)

export const createResetCode = (id: number) =>
  call('POST', `/auth/users/${id}/reset`) as Promise<Result & { code?: string }>

/** The link someone opens to use an invite or reset code. */
export const codeLink = (code: string) => `${window.location.origin}/join?code=${encodeURIComponent(code)}`

// Read at page load, before the router's catch-all redirect drops the query string
let initialCode = new URLSearchParams(window.location.search).get('code') ?? ''

/** The code from the link the page was opened with (/join?code=...), if any — handed out once. */
export function takeCodeFromUrl(): string {
  const code = initialCode
  initialCode = ''
  return code
}
