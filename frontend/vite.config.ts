import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/ai': {
        target: 'http://localhost:5004',
        changeOrigin: true
      },
      '/api': {
        target: 'http://localhost',
        changeOrigin: true
      },
      '/ws': {
        target: 'http://localhost',
        changeOrigin: true,
        ws: true
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
