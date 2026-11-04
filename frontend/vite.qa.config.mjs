import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import frappeui from 'frappe-ui/vite'
const root = path.resolve(import.meta.dirname, '..')
function viewerShell() {
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
export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/sketch',
      frappeProxy: false,
      buildConfig: { outDir: path.join(root, 'sketch/public/frontend'), indexHtmlPath: path.join(root, 'sketch/www/sketch.html'), baseUrl: '/assets/sketch/frontend/' },
    }),
    vue(),
    viewerShell(),
  ],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') }, dedupe: ['vue', 'frappe-ui', 'vue-router', '@vueuse/core'] },
  build: { rollupOptions: { input: { index: path.resolve(import.meta.dirname, 'index.html'), viewer: path.resolve(import.meta.dirname, 'viewer.html') } } },
})
