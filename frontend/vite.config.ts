import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

const headers = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  preview: { headers, proxy: { '/api/v1': { target: loadEnv(mode, process.cwd(), '').SENTINEL_API_TARGET || 'http://127.0.0.1:8000' } } },
  server: {
    headers,
    proxy: { '/api/v1': { target: loadEnv(mode, process.cwd(), '').SENTINEL_API_TARGET || 'http://127.0.0.1:8000' } },
    host: '0.0.0.0',
    allowedHosts: ['homie'],
    port: 5173,
    strictPort: true,
  },
}))
