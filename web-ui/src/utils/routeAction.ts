import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * Run a page action named in the URL, e.g. /bills?action=add, then drop it from
 * the URL so a refresh doesn't repeat it. Used by the command palette.
 * `q` (a search term) is passed to the handler as well.
 */
export function onRouteAction(handlers: Record<string, (q: string) => void>) {
  const route = useRoute()
  const router = useRouter()
  watch(() => route.query.action, action => {
    const fn = typeof action === 'string' ? handlers[action] : undefined
    if (!fn) return
    fn(typeof route.query.q === 'string' ? route.query.q : '')
    router.replace({ query: { ...route.query, action: undefined, q: undefined } })
  }, { immediate: true })
}
