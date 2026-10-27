import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/graphql': 'http://127.0.0.1:4000',
      '/health': 'http://127.0.0.1:4000',
    },
  },
})
