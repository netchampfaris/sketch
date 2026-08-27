import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const version = '1.0.0-beta.55'
const outDir = path.resolve(here, '../sketch/public/runtimes', version)

// Runtime asset build. vue and vue-router stay external: they are copied in
// from their own esm-browser.prod builds, so a Prototype and frappe-ui share
// one Vue instance through the import map.
export default defineConfig({
  // Vite reads the nearest package.json from `root`, and a lib build needs a
  // name. Without this it takes the caller's working directory.
  root: here,
  plugins: [
    frappeui({ frappeProxy: false, jinjaBootData: false, buildConfig: false }),
    vue(),
  ],
  // reka-ui (and other deps) guard dev-only code with `process.env.NODE_ENV`.
  // Vite's lib build does not substitute it, so `process` is undefined in the
  // browser and the guarded component throws inside setup().
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir,
    emptyOutDir: false,
    minify: true,
    target: 'es2022',
    lib: {
      entry: {
        'frappe-ui': path.resolve(here, 'runtime-entry/frappe-ui.js'),
        'frappe-ui-list': path.resolve(here, 'runtime-entry/frappe-ui-list.js'),
        'frappe-ui-editor': path.resolve(here, 'runtime-entry/frappe-ui-editor.js'),
        'frappe-ui-charts': path.resolve(here, 'runtime-entry/frappe-ui-charts.js'),
        'frappe-ui-icons': path.resolve(here, 'runtime-entry/frappe-ui-icons.js'),
        dayjs: path.resolve(here, 'runtime-entry/dayjs.js'),
      },
      formats: ['es'],
    },
    rollupOptions: {
      external: ['vue', 'vue-router'],
      output: { entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js', assetFileNames: 'frappe-ui-components[extname]' },
    },
  },
})
