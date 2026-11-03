import { apolloClient } from '../graphql/client'

// Every query on screen refetches after any change (not just the page's own
// main query, so side panels never show old numbers), and when you come back
// to the tab (background jobs such as SimpleFIN sync may have changed things).
// The server caches the plan, so this is cheap.

const AWAY_MS = 30 * 1000
let timer: ReturnType<typeof setTimeout> | undefined
let hiddenAt = 0

function refreshAll() {
  clearTimeout(timer)
  // A moment's wait lets a page's own refetch start first; identical
  // queries in flight are merged
  timer = setTimeout(() => { apolloClient.refetchQueries({ include: 'active' }).catch(() => { /* shown by the query */ }) }, 50)
}

export function startRefresh() {
  window.addEventListener('budget:changed', refreshAll)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') hiddenAt = Date.now()
    else if (hiddenAt && Date.now() - hiddenAt > AWAY_MS) refreshAll()
  })
}
