import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy /api et /media vers le backend Django en développement, pour
// éviter tout souci de CORS/URL en dur : le frontend appelle simplement
// des chemins relatifs ("/api/...").
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/media': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
