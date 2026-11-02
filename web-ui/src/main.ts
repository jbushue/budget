import { createApp, h, provide } from 'vue'
import { DefaultApolloClient } from '@vue/apollo-composable'
import { apolloClient } from './graphql/client'
import { router } from './router'
import App from './App.vue'
import { startTableLabels } from './utils/stackTables'
import { startTheme } from './utils/theme'
import { startOverlayGuard } from './utils/overlay'
import '@fontsource-variable/inter'
import './style.css'

startTheme()

const app = createApp({
  setup() {
    provide(DefaultApolloClient, apolloClient)
  },
  render: () => h(App),
})

app.use(router)
app.mount('#app')
startTableLabels()
startOverlayGuard()

// Installable app (PWA). Browsers only allow service workers on localhost or HTTPS.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* not available here */ })
  })
}
