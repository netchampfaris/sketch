// Loads the sample Prototype in headless Chromium against the built Runtime,
// waits for the Viewer to report, and prints the payload and the timings.
import { chromium } from '/tmp/pw-runner/node_modules/playwright/index.mjs'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { BASE, VERSION, openViewer, readTree } from './harness.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const out = join(here, '../sketch/public/runtimes', VERSION)
const manifest = JSON.parse(readFileSync(join(out, 'manifest.json'), 'utf8'))

const COMPILERS = ['compiler.js', 'tailwind.js']
const FONT = ['Inter.var.woff2']
const group = (f) => (COMPILERS.includes(f) ? 'compilers' : FONT.includes(f) ? 'font' : 'eager')

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })

const asked = new Set()
context.on('request', (r) => {
	const url = r.url()
	if (url.startsWith(BASE)) asked.add(url.slice(BASE.length + 1).split('?')[0])
})

const t0 = Date.now()
const page = await openViewer(context, readTree(join(here, 'sample-prototype')))
const wallMs = Date.now() - t0
const check = await page.evaluate(() => window.__sketch)

// The route walk, driven through the router the way check drives it.
const nav = {}
for (const route of check.routes) {
	const t = Date.now()
	await page.evaluate((p) => window.__sketchGoto(p), route)
	nav[route] = Date.now() - t
}

// Layer 2 proof: an arbitrary value class the precompiled CSS cannot hold.
await page.evaluate(() => window.__sketchGoto('/about'))
await page.waitForSelector('text=Arbitrary value check')
const arbitrary = await page.evaluate(() => {
	const el = document.querySelector('.h-\\[13px\\]')
	const s = getComputedStyle(el)
	return { width: s.width, height: s.height, background: s.backgroundColor }
})

// Dialog and form round trip. Both need FrappeUIProvider to be mounted.
await page.evaluate(() => window.__sketchGoto('/'))
await page.click('button:has-text("New issue")')
await page.waitForSelector('input[placeholder="What is broken?"]')
await page.fill('input[placeholder="What is broken?"]', 'Runtime proves itself')
await page.click('button:has-text("Create")')
await page.waitForSelector('text=Runtime proves itself', { timeout: 5000 })
const rows = await page.evaluate(() => document.querySelectorAll('[data-slot="list-row"]').length)

const payload = { eager: { bytes: 0, gzip: 0, files: [] }, compilers: { bytes: 0, gzip: 0, files: [] }, font: { bytes: 0, gzip: 0, files: [] } }
for (const file of [...asked].sort()) {
	const asset = manifest.assets[file]
	if (!asset) continue
	const g = payload[group(file)]
	g.bytes += asset.bytes
	g.gzip += asset.gzip
	g.files.push(file)
}

const final = await page.evaluate(() => window.__sketch)
const result = { wallMs, nav, rows, arbitrary, payload, check: final }
writeFileSync(join(here, 'measurements.json'), JSON.stringify(result, null, 2))
console.log(JSON.stringify(result, null, 2))
await browser.close()
