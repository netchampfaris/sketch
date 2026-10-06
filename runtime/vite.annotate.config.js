import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const version = '1.0.0-rc.2'
const outDir = path.resolve(here, '../sketch/public/runtimes', version)

// The annotate toolbar: one ES module that boot.js imports for the owner's live tab. Everything the
// Prototype already loads stays external, so the toolbar shares its Vue, router, frappe-ui and
// vueuse through the import map and adds none of them to the download. `frappe-ui/list` is
// matched by the pattern with the main entry.
export default defineConfig({
  root: here,
  plugins: [vue()],
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir,
    emptyOutDir: false,
    minify: true,
    target: 'es2022',
    // Own CSS is not needed: layer 2 generates the toolbar's utilities from the live DOM.
    cssCodeSplit: false,
    lib: {
      entry: { annotate: path.resolve(here, 'annotate/index.ts') },
      formats: ['es'],
    },
    rollupOptions: {
      external: ['vue', 'vue-router', '@vueuse/core', /^frappe-ui(\/.*)?$/],
      output: { entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js' },
    },
  },
})
