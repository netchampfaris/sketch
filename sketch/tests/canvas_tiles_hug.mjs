// The canvas tiles fit their variant, and a variant that draws its own card drops the tile frame. `test_canvas_tiles_hug.py`
// reads the JSON this prints on stdout and makes the assertions.
//
//   node canvas_tiles_hug.mjs <playwright entry> <esbuild> <node_modules for the bundle> <runtime/variants folder>
//
// It bundles lift.ts (`ownCard`, what marks a set self-framed) and layout.ts (`layoutPick`, the tile sizes) and runs both in
// a real page, so `ownCard` reads real computed styles. No server is needed.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, esbuild, modules, variants] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const work = mkdtempSync(join(tmpdir(), 'tiles-hug-'))
writeFileSync(
  join(work, 'entry.ts'),
  `import { ownCard } from ${JSON.stringify(join(variants, 'lift.ts'))}\n` +
    `import { layoutPick } from ${JSON.stringify(join(variants, 'layout.ts'))}\n` +
    'window.__tiles = { ownCard, layoutPick }\n',
)
const bundle = join(work, 'bundle.js')
execFileSync(esbuild, [join(work, 'entry.ts'), '--bundle', '--format=iife', '--platform=browser', `--outfile=${bundle}`, '--log-level=error'], {
  env: { ...process.env, NODE_PATH: modules },
})

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)))
await page.setContent(`<body>
  <div id="card" style="width:200px;background:#fff;border:1px solid #ccc;border-radius:12px"></div>
  <div id="shadow" style="width:200px;background:#fff;box-shadow:0 4px 12px rgba(0,0,0,.2);border-radius:8px"></div>
  <div id="border-only" style="width:200px;border:1px solid #ccc"></div>
  <div id="fill-only" style="width:200px;background:#eee"></div>
  <div id="shadow-only" style="width:200px;box-shadow:0 4px 12px rgba(0,0,0,.2)"></div>
  <div id="clear-border" style="width:200px;background:#fff;border:1px solid transparent"></div>
  <p id="one" style="width:100px;background:#fff;border:1px solid #ccc"></p><p id="two" style="width:100px;background:#fff;border:1px solid #ccc"></p>
</body>`)
await page.addScriptTag({ path: bundle })

const answer = await page.evaluate(() => {
  const { ownCard, layoutPick } = window.__tiles
  const el = (id) => document.getElementById(id)
  const own = {
    card: ownCard([el('card')]),
    shadow: ownCard([el('shadow')]),
    borderOnly: ownCard([el('border-only')]),
    fillOnly: ownCard([el('fill-only')]),
    shadowOnly: ownCard([el('shadow-only')]),
    clearBorder: ownCard([el('clear-border')]),
    twoRoots: ownCard([el('one'), el('two')]),
    none: ownCard([]),
  }

  // A set of five options, one twice as wide as the rest and the second the plain kind: what each measured once drawn.
  const sizes = {
    a: { w: 420, h: 400, card: '10px' },
    b: { w: 420, h: 320 },
    c: { w: 420, h: 480, card: '10px' },
    d: { w: 840, h: 360, card: '10px' },
    e: { w: 320, h: 300, card: '10px' },
  }
  const options = Object.keys(sizes).map((value) => ({ value, label: value.toUpperCase() }))
  const page = { path: '/', slug: 'home', title: 'Home', states: [], sets: [{ key: 'k', label: 'K', name: 'K', file: '', options, meta: { x: 0, y: 0, w: 420, h: 400 } }] }
  const run = (width, phone) =>
    layoutPick(
      { kind: 'set', page, key: 'k' },
      { win: { w: 1440, h: 900 }, vp: { w: width, h: 900 }, phone, sizeOf: (id) => sizes[id.split('|').pop()] ?? null, statesOf: () => null },
    )
  const box = (t) => ({ id: t.option, x: t.x, y: t.y, w: t.w, h: t.h, card: t.card ?? null })
  const wide = run(1440, false)
  const phone = run(390, true)
  return {
    own,
    wide: { tiles: wide.tiles.map(box), bounds: wide.bounds },
    phone: { tiles: phone.tiles.map(box), bounds: phone.bounds },
  }
})
answer.errors = errors
console.log(JSON.stringify(answer))
await browser.close()
