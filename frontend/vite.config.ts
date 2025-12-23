import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['kb.studyninja.ru', 'kb.xteam.pro', 'dev.kb.studyninja.ru', 'dev.kb.xteam.pro'],
    proxy: {
      '/v1': {
        target: 'https://api.kb.xteam.pro',
        changeOrigin: true,
        secure: true,
      },
      '/ws': {
        target: 'wss://api.kb.xteam.pro',
        ws: true,
        changeOrigin: true,
        secure: true,
      },
      '/health': {
        target: 'https://api.kb.xteam.pro',
        changeOrigin: true,
        secure: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  }
})
