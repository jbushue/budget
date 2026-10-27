import type { MutationPayload } from '../types'

interface RunMutationOptions {
  /** Message shown when the mutation fails without a server message. */
  failMessage?: string
  /** Alert the server's message on success too (e.g. for informational results). */
  showSuccess?: boolean
}

/**
 * Run a GraphQL mutation, check `data[field].success`, and alert on failure.
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
      alert('Error: ' + failMessage)
      return null
    }
    if (payload.success === false) {
      alert('Error: ' + (payload.message || failMessage))
      return null
    }
    if (opts.showSuccess && payload.message) alert(payload.message)
    return payload
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    alert('Error: ' + (msg || failMessage))
    return null
  }
}
