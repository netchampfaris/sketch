// FileUploader is the one component that calls a server on its own. The
// Viewer stubs /api/method/upload_file over XMLHttpRequest, so it resolves
// with no backend.
import { chromium } from '/tmp/pw-runner/node_modules/playwright/index.mjs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { openViewer, readTree } from './harness.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
const page = await openViewer(context, readTree(join(here, 'sample-prototype')))
page.on('pageerror', (e) => console.log('[pageerror]', e.message))

await page.evaluate(() => window.__sketchGoto('/about'))
await page.waitForSelector('text=Attach a file')
await page.setInputFiles('input[type=file]', {
	name: 'notes.txt',
	mimeType: 'text/plain',
	buffer: Buffer.from('hello sketch'),
})
await page.waitForSelector('#uploaded', { timeout: 8000 })
console.log('upload stub:', await page.textContent('#uploaded'))
console.log('errors:', JSON.stringify(await page.evaluate(() => window.__sketch.errors)))
await browser.close()
