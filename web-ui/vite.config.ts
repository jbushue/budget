import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    // xfwd passes the real client address along, so the API can tell
    // this computer from other devices on the network
    proxy: {
      '/graphql': { target: 'http://127.0.0.1:4000', xfwd: true },
      '/health': { target: 'http://127.0.0.1:4000', xfwd: true },
      '/files': { target: 'http://127.0.0.1:4000', xfwd: true },
      '/auth': { target: 'http://127.0.0.1:4000', xfwd: true },
    },
  },
})
