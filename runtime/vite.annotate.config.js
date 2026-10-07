import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
// build.sh runs this from a work folder and names the output folder.
const outDir = process.env.RUNTIME_OUT
if (!outDir) throw new Error('RUNTIME_OUT is not set. Run runtime/build.sh <version>.')

// The annotate toolbar (imported by boot.js for the owner's live tab) and `sketch:variants` (imported
// by Prototypes): one ES module each. Everything the Prototype already loads stays external, so both
// share its Vue, router, frappe-ui and vueuse through the import map and add none of them to the download. `frappe-ui/list` is
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
      entry: {
        annotate: path.resolve(here, 'annotate/index.ts'),
        variants: path.resolve(here, 'variants/index.ts'),
      },
      formats: ['es'],
    },
    rollupOptions: {
      external: ['vue', 'vue-router', '@vueuse/core', 'sketch:variants', /^frappe-ui(\/.*)?$/],
      output: { entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js' },
    },
  },
})
