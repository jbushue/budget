import { reactive } from 'vue'

/** Login state for the optional password (see models/auth.py). */
export const authState = reactive({
  checked: false,
  passwordSet: false,
  authenticated: false,
  local: true,
})

interface Result { success: boolean; message?: string }

export async function checkAuth(): Promise<void> {
  try {
    const r = await fetch('/auth/status', { credentials: 'same-origin' })
    const s = await r.json()
    authState.passwordSet = !!s.password_set
    authState.authenticated = !!s.authenticated
    authState.local = !!s.local
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

async function post(path: string, body: unknown): Promise<Result> {
  try {
    const r = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    const data = await r.json().catch(() => ({}))
    return { success: r.ok && data.success !== false, message: data.message }
  } catch (e) {
    return { success: false, message: e instanceof Error ? e.message : String(e) }
  }
}

export async function login(password: string): Promise<Result> {
  const res = await post('/auth/login', { password })
  if (res.success) await checkAuth()
  return res
}

export async function logout(): Promise<void> {
  await post('/auth/logout', {})
  await checkAuth()
}

/** Set, change, or (newPassword empty) remove the password. */
export async function setPassword(currentPassword: string, newPassword: string): Promise<Result> {
  const res = await post('/auth/password', { current_password: currentPassword, new_password: newPassword })
  if (res.success) await checkAuth()
  return res
}
