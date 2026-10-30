import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The API key is read from the repo's .env (one folder up) and added by the dev proxy:
// it never ends up in the browser bundle.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '')
  const target = env.DEMO_API_URL || 'http://localhost:8080'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: true, headers: { 'X-API-Key': env.API_KEY ?? '' } },
      },
    },
  }
})
