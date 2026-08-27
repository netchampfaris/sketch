// Builds the icon lookup the browser Tailwind engine masks icons from.
//
// frappe-ui's own lucideIconsPlugin reads each SVG off disk with `node:fs`, so
// it cannot run in the Viewer. This writes the same icons out once, at build
// time, as `name -> data URI`, and `shims/iconPackBrowser.js` reads that map
// instead of the filesystem. Every lucide icon resolves, not only the ~200
// that frappe-ui happens to use in its own source.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const icons = join(here, '../frontend/node_modules/lucide-static/icons')
const out = join(here, 'tailwind/lucide-map.json')

// Lucide ships at stroke-width 2. frappe-ui normalises to 1.5, so the browser
// copy must too, or a Prototype's icons are heavier than the library's own.
const map = {}
for (const file of readdirSync(icons).sort()) {
  if (!file.endsWith('.svg')) continue
  const svg = readFileSync(join(icons, file), 'utf8')
    .replace(/stroke-width="[^"]+"/g, 'stroke-width="1.5"')
    .replace(/\s+/g, ' ')
    .trim()
  map[file.slice(0, -4)] = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

writeFileSync(out, JSON.stringify(map))
console.log(`  ${Object.keys(map).length} lucide icons`)
