// The owner's Viewer on a Prototype whose Gate page sends the person home as it mounts. `test_canvas_redirect.py`
// writes the Prototype, reads the JSON this prints on stdout and makes the assertions.
//
//   node canvas_redirect.mjs <playwright entry> <host> <port> <viewer path> <sid> <canvas|direct>
//
// canvas: open the canvas on Gate's set from Home, so the tiles render Gate; wait for them, and a while longer for
//         a redirect to land; read the hash, whether the canvas is still there, and what the tiles show.
// direct: open Gate itself; it must still send the person home.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid, mode] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const URL_OF = { canvas: '#/?canvas=set:gate/banner', direct: '#/gate' }
const BOOT_MS = 60000
// After the tiles: the redirect runs as each offscreen render mounts, and closing the canvas takes a moment.
const SETTLE_MS = 2500

const answer = { mode }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])

try {
	const page = await context.newPage()
	const logs = []
	page.on('console', (m) => m.type() === 'error' && logs.push(m.text().slice(0, 300)))
	page.on('pageerror', (e) => logs.push(String(e).slice(0, 300)))

	await page.goto(`${ORIGIN}${viewerPath}${URL_OF[mode]}`, { waitUntil: 'load', timeout: BOOT_MS })
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
		// What the frame shows instead, so a failure says why.
		const seen = await frame.evaluate(() => ({ hash: location.hash, text: document.body.innerText.slice(0, 1500) })).catch(() => null)
		throw new Error(`${e.message}\nthe frame: ${JSON.stringify(seen)}\nerrors: ${JSON.stringify(logs.slice(0, 20))}`)
	}

	if (mode === 'canvas') {
		// Both of Banner's tiles drawn, so every offscreen render of Gate has mounted. Or the canvas already gone.
		const drawn = () => document.querySelectorAll('[data-tile-id] [inert]').length >= 2 || !location.hash.includes('canvas=')
		await frame.waitForFunction(drawn, null, { timeout: BOOT_MS }).catch(why)
		answer.tiles = await frame.locator('[data-tile-id]').count()
		await sleep(SETTLE_MS)
		answer.hash = await frame.evaluate(() => location.hash)
		answer.canvasOpen = (await frame.locator('[data-sketch-ui="canvas"]').count()) > 0
		answer.tileText = await frame.locator('[data-tile-id]').allInnerTexts()
	} else {
		await frame.getByText('Home page').first().waitFor({ timeout: BOOT_MS }).catch(why)
		await sleep(SETTLE_MS)
		answer.hash = await frame.evaluate(() => location.hash)
		answer.text = await frame.evaluate(() => document.body.innerText.slice(0, 500))
	}
	answer.errors = logs
} finally {
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
