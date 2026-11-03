import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import frappeui from 'frappe-ui/vite'

// The Viewer shell's page (viewer.html) is read by sketch/viewer.py, which fills one slot of its own.
// frappe-ui's jinjaBootData adds a Jinja loop to every page it builds, and this one is never rendered
// through Jinja, so it comes out again here.
function viewerShell(): Plugin {
  return {
    name: 'sketch-viewer-shell',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        if (!ctx.filename.endsWith('viewer.html')) return html
        return html.replace(/\s*<script>\s*\{% for key in boot %\}[\s\S]*?<\/script>/, '')
      },
    },
  }
}

// Runs inside a Frappe site, so the frappeui plugin keeps its Frappe defaults:
// frappeProxy (dev port = 8080 + webserver_port offset, so 8087 here),
// jinjaBootData, buildConfig (outDir sketch/public/frontend, index copied to
// sketch/www/sketch.html, base /assets/sketch/frontend/).
export default defineConfig({
  plugins: [frappeui({ frontendRoute: '/sketch' }), vue(), viewerShell()],
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
    // The avatar colour rule is shared with the runtime (runtime/shared), and the Viewer shell's UI
    // lives in runtime/shell.
    fs: { allow: ['..'] },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      // The comment and note components the shell shares with the in-frame toolbar (runtime/annotate) ask
      // `sketch:variants` for the Demo and the canvas; in the shell those answers come from the frame.
      'sketch:variants': path.resolve(__dirname, '../runtime/shell/variants.ts'),
    },
    // runtime/shell and runtime/annotate sit outside this folder, so their imports resolve from here: one of each.
    dedupe: ['vue', 'frappe-ui', 'vue-router', '@vueuse/core'],
  },
  build: {
    rollupOptions: {
      // The SPA, and the Viewer shell (sketch/public/frontend/viewer.html).
      input: {
        index: path.resolve(__dirname, 'index.html'),
        viewer: path.resolve(__dirname, 'viewer.html'),
      },
    },
  },
})
