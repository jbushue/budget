import { reactive } from 'vue'

/**
 * In-app notifications and dialogs (instead of the browser's alert/confirm/prompt).
 * <DialogHost /> in App.vue draws them.
 *
 *   notify('Saved')                         – a toast that fades away
 *   notify('Could not save', 'error')
 *   if (!(await ask('Delete "Rent"?', { danger: true, confirmText: 'Delete' }))) return
 *   const value = await askValue('Monthly budget', { value: '300', inputType: 'number' })
 */

export type ToastKind = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
}

export interface AskOptions {
  title?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

export interface AskValueOptions extends AskOptions {
  message?: string
  value?: string
  placeholder?: string
  inputType?: 'text' | 'number'
}

interface DialogState {
  kind: 'confirm' | 'prompt'
  title: string
  message: string
  confirmText: string
  cancelText: string
  danger: boolean
  value: string
  placeholder: string
  inputType: 'text' | 'number'
  resolve: (v: boolean | string | null) => void
}

export const dialogState = reactive({
  toasts: [] as Toast[],
  dialog: null as DialogState | null,
})

let nextId = 1

export function notify(message: string, kind: ToastKind = 'success') {
  const id = nextId++
  dialogState.toasts.push({ id, kind, message })
  if (dialogState.toasts.length > 4) dialogState.toasts.shift()
  setTimeout(() => dismissToast(id), kind === 'error' || message.length > 120 ? 8000 : 4000)
}

export function dismissToast(id: number) {
  const i = dialogState.toasts.findIndex(t => t.id === id)
  if (i >= 0) dialogState.toasts.splice(i, 1)
}

/** Ask a yes/no question. Resolves true when confirmed. */
export function ask(message: string, opts: AskOptions = {}): Promise<boolean> {
  return new Promise(resolve => {
    dialogState.dialog = {
      kind: 'confirm',
      title: opts.title ?? (opts.danger ? 'Are you sure?' : 'Please confirm'),
      message,
      confirmText: opts.confirmText ?? (opts.danger ? 'Delete' : 'OK'),
      cancelText: opts.cancelText ?? 'Cancel',
      danger: !!opts.danger,
      value: '', placeholder: '', inputType: 'text',
      resolve: v => resolve(v === true),
    }
  })
}

/** Ask for a value. Resolves the text entered, or null when cancelled. */
export function askValue(title: string, opts: AskValueOptions = {}): Promise<string | null> {
  return new Promise(resolve => {
    dialogState.dialog = {
      kind: 'prompt',
      title,
      message: opts.message ?? '',
      confirmText: opts.confirmText ?? 'Save',
      cancelText: opts.cancelText ?? 'Cancel',
      danger: !!opts.danger,
      value: opts.value ?? '',
      placeholder: opts.placeholder ?? '',
      inputType: opts.inputType ?? 'text',
      resolve: v => resolve(typeof v === 'string' ? v : null),
    }
  })
}

export function closeDialog(result: boolean | string | null) {
  const d = dialogState.dialog
  dialogState.dialog = null
  d?.resolve(result)
}
