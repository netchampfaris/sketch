import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
// @ts-expect-error frappe-ui/vite ships untyped JS.
import frappeui from 'frappe-ui/vite'

// Runs inside a Frappe site, so the frappeui plugin keeps its Frappe defaults:
// frappeProxy (dev port = 8080 + webserver_port offset, so 8087 here),
// jinjaBootData, buildConfig (outDir sketch/public/frontend, index copied to
// sketch/www/sketch.html, base /assets/sketch/frontend/).
export default defineConfig({
  plugins: [frappeui({ frontendRoute: '/sketch' }), vue()],
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
})
