import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import frappeui from 'frappe-ui/vite'

// Runs inside a Frappe site, so the frappeui plugin keeps its Frappe defaults:
// frappeProxy (dev port = 8080 + webserver_port offset, so 8087 here) and
// jinjaBootData.
//
// Its buildConfig is off, because it copies index.html to sketch/www/, outside
// public/. Pilot installs prebuilt assets by extracting a tarball into public/
// only, so the page has to live there. sketch/www/sketch.html is a committed
// stub that extends public/frontend/index.html.
export default defineConfig(({ command }) => ({
  plugins: [frappeui({ frontendRoute: '/sketch', buildConfig: false }), vue()],
  base: command === 'build' ? '/assets/sketch/frontend/' : '/',
  build: {
    outDir: '../sketch/public/frontend',
    emptyOutDir: true,
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
}))
