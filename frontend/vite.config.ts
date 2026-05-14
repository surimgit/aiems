import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devProxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:9080'

  return {
    plugins: [vue()],
    server: {
      proxy: {
        '/api': {
          target: devProxyTarget,
          changeOrigin: true,
          timeout: 8000,
          proxyTimeout: 8000
        },
        '/healthz': {
          target: devProxyTarget,
          changeOrigin: true,
          timeout: 8000,
          proxyTimeout: 8000
        },
        '/ws': {
          target: devProxyTarget,
          ws: true,
          changeOrigin: true,
          timeout: 8000,
          proxyTimeout: 8000
        },
        '/socket.io': {
          target: devProxyTarget,
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
  }
})
