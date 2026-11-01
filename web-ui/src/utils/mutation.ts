import type { MutationPayload } from '../types'
import { notify } from './dialog'

interface RunMutationOptions {
  /** Message shown when the mutation fails without a server message. */
  failMessage?: string
  /** Show the server's message on success too (e.g. for informational results). */
  showSuccess?: boolean
}

/**
 * Run a GraphQL mutation, check `data[field].success`, and show a toast on failure.
 * Returns the payload on success, or null on failure (GraphQL/network error
 * or `success: false`). Callers should only close modals / refetch on success.
 */
export async function runMutation<TData, K extends keyof TData & string>(
  run: () => Promise<{ data?: TData | null } | null | undefined>,
  field: K,
  opts: RunMutationOptions = {},
): Promise<(TData[K] & MutationPayload) | null> {
  const failMessage = opts.failMessage || 'Operation failed'
  try {
    const res = await run()
    const payload = res?.data?.[field] as (TData[K] & MutationPayload) | null | undefined
    if (!payload) {
      notify(failMessage, 'error')
      return null
    }
    if (payload.success === false) {
      notify(payload.message || failMessage, 'error')
      return null
    }
    if (opts.showSuccess && payload.message) notify(payload.message)
    return payload
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    notify(msg || failMessage, 'error')
    return null
  }
}
