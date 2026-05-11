import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1',
        changeOrigin: true,
        timeout: 8000,
        proxyTimeout: 8000
      },
      '/healthz': {
        target: 'http://127.0.0.1',
        changeOrigin: true,
        timeout: 8000,
        proxyTimeout: 8000
      },
      '/ws': {
        target: 'http://127.0.0.1',
        ws: true,
        changeOrigin: true,
        timeout: 8000,
        proxyTimeout: 8000
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
