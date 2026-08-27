// One manifest per Runtime folder. Names the assets and records their sizes,
// so the SPA can build the Viewer's import map without guessing filenames.
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { dirname, join } from 'node:path'

const [version, out] = process.argv.slice(2)
const dir = dirname(out)
const assets = {}
for (const f of readdirSync(dir).sort()) {
  if (f === 'manifest.json') continue
  const buf = readFileSync(join(dir, f))
  assets[f] = { bytes: statSync(join(dir, f)).size, gzip: gzipSync(buf, { level: 9 }).length }
}
writeFileSync(
  out,
  JSON.stringify(
    {
      frappeUI: version,
      base: `/assets/sketch/runtimes/${version}/`,
      entry: 'viewer.html',
      importMap: {
        vue: 'vue.js',
        'vue-router': 'vue-router.js',
        'frappe-ui': 'frappe-ui.js',
        'frappe-ui/list': 'frappe-ui-list.js',
        'frappe-ui/editor': 'frappe-ui-editor.js',
        'frappe-ui/charts': 'frappe-ui-charts.js',
        'frappe-ui/icons': 'frappe-ui-icons.js',
        dayjs: 'dayjs.js',
        '@vueuse/core': 'vueuse.js',
        'sketch:compiler': 'compiler.js',
        'sketch:tailwind': 'tailwind.js',
      },
      stylesheets: ['frappe-ui.css', 'frappe-ui-components.css'],
      assets,
    },
    null,
    2,
  ),
)
