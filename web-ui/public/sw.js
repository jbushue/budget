// Service worker: lets the app be installed and open instantly.
// Only the app's own files are cached — never your financial data
// (/graphql, /files, /auth always go to the server).
const CACHE = 'budget-shell-v1'
const SHELL = ['/', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png']

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.origin !== location.origin) return
  if (/^\/(graphql|files|auth|health)/.test(url.pathname)) return

  // Pages: network first (always the latest app), cached copy when offline
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(res => {
          const copy = res.clone()
          caches.open(CACHE).then(c => c.put('/', copy))
          return res
        })
        .catch(() => caches.match('/')),
    )
    return
  }

  // Built assets have content hashes in their names, so cache-first is safe
  event.respondWith(
    caches.match(event.request).then(hit => hit || fetch(event.request).then(res => {
      if (res.ok && url.pathname.startsWith('/assets/')) {
        const copy = res.clone()
        caches.open(CACHE).then(c => c.put(event.request, copy))
      }
      return res
    })),
  )
})
