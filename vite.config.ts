import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import pkg from './package.json';

const repoBase = process.env.VITE_BASE_PATH || './';

export default defineConfig({
  base: repoBase,
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Local AI Image Search',
        short_name: 'Image Search',
        description: 'A local-first AI image search PWA for private photo libraries.',
        theme_color: '#101820',
        background_color: '#f6f4ef',
        display: 'standalone',
        start_url: '.',
        scope: '.',
        icons: [
          {
            src: 'pwa-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any maskable'
          },
          {
            src: 'pwa-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable'
          }
        ]
      }
    })
  ],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version)
  },
  test: {
    environment: 'jsdom'
  }
});
