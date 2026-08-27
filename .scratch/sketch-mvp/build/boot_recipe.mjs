import { chromium } from 'playwright'
const url = process.argv[2]
const b = await chromium.launch()
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } })
const page = await ctx.newPage()
const failed = [], consoleErrs = []
page.on('requestfailed', r => failed.push(r.url()))
page.on('response', r => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`) })
page.on('console', m => { if (m.type() === 'error') consoleErrs.push(m.text()) })
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForFunction(() => window.__sketch !== undefined, { timeout: 15000 }).catch(() => {})
const s = await page.evaluate(() => window.__sketch)
console.log('window.__sketch:', JSON.stringify(s, null, 1))
console.log('data-theme:', await page.evaluate(() => document.documentElement.dataset.theme))
console.log('h1 text:', await page.evaluate(() => document.querySelector('h1')?.textContent))
console.log('failed requests:', failed)
console.log('console errors:', consoleErrs)
await b.close()
