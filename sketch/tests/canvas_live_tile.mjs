// The owner's Viewer on a Prototype whose Layout set renders only a hidden element. `test_canvas_live_tile.py` writes
// the Prototype, reads the JSON this prints on stdout and makes the assertions.
//
//   node canvas_live_tile.mjs <playwright entry> <host> <port> <viewer path> <sid>
//
// Opens the canvas on Layout's set, waits for both tiles, clicks the first one and reads what the live tile shows.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const BOOT_MS = 60000
// The live tile follows its set from the second frame after it mounts.
const SETTLE_MS = 1000

const answer = {}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])

try {
	const page = await context.newPage()
	const logs = []
	page.on('console', (m) => m.type() === 'error' && logs.push(m.text().slice(0, 300)))
	page.on('pageerror', (e) => logs.push(String(e).slice(0, 300)))

	await page.goto(`${ORIGIN}${viewerPath}#/?canvas=set:home/layout`, { waitUntil: 'load', timeout: BOOT_MS })
	const frame = await (async () => {
		const deadline = Date.now() + BOOT_MS
		while (Date.now() < deadline) {
			const f = page.frames().find((x) => x.url().includes('frame=1'))
			if (f) return f
			await sleep(250)
		}
		throw new Error('the shell never framed the Prototype')
	})()

	const why = async (e) => {
		const seen = await frame.evaluate(() => ({ hash: location.hash, text: document.body.innerText.slice(0, 1500) })).catch(() => null)
		throw new Error(`${e.message}\nthe frame: ${JSON.stringify(seen)}\nerrors: ${JSON.stringify(logs.slice(0, 20))}`)
	}

	await frame.waitForFunction(() => document.querySelectorAll('[data-tile-id] [inert]').length >= 2, null, { timeout: BOOT_MS }).catch(why)
	await frame.locator('[data-tile-id] [data-tile]').first().click()
	await frame.locator('[data-live]').waitFor({ timeout: BOOT_MS }).catch(why)
	await sleep(SETTLE_MS)
	answer.live = (await frame.locator('[data-live]').count()) > 0
	answer.liveText = await frame.locator('[data-live]').innerText()
	answer.headingVisible = await frame.evaluate(() => document.querySelector('[data-live] h1')?.checkVisibility({ visibilityProperty: true }) ?? false)
	answer.errors = logs
} finally {
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
