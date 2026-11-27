// The owner's Viewer on a Prototype whose Card set is drawn as canvas tiles. `test_tile_pins_follow.py` writes the
// Prototype, runs this twice (the card narrow, then wide) and makes the assertions on the JSON it prints on stdout.
//
//   node tile_pins_follow.mjs <playwright entry> <host> <port> <viewer path> <sid> <make|measure> [evidence file]
//
// `make` leaves a note and a comment on the Submit button of the first tile, and a comment on its No button. Both runs
// then report, for those pins and for an old note made without an element, where the pin's tip is, and the boxes of
// Submit, No and their tile.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid, mode, evidence] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const BOOT_MS = 60000

const answer = { pins: {} }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])

// A tile made live, with no tool in hand, and its More opened, so Submit sits lower than in the tile's snapshot. The
// frame is asked where Submit is, as the shell asks for a pin's element (`tile:track`): where the frame says, and where
// the live render and the snapshot each draw it, all from the tile's top left in the canvas's own px.
async function liveTile() {
	const fresh = await browser.newContext({ viewport: { width: 1280, height: 800 } })
	await fresh.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])
	await fresh.addInitScript(() => {
		if (window.top !== window) return
		window.__rects = {}
		window.addEventListener('message', (e) => {
			if (e.data?.channel) window.__channel = e.data.channel
			if (e.data?.type === 'tile:rects') window.__rects[e.data.data.req] = e.data.data.list
		})
	})
	try {
		const page = await fresh.newPage()
		await page.goto(`${ORIGIN}${viewerPath}#/?canvas=set:home/card`, { waitUntil: 'load', timeout: BOOT_MS })
		let frame = null
		for (const deadline = Date.now() + BOOT_MS; !frame && Date.now() < deadline; await sleep(100)) frame = page.frames().find((x) => x.url().includes('frame=1'))
		if (!frame) throw new Error('the shell never framed the Prototype')
		await frame.waitForFunction(() => document.querySelectorAll('[data-tile-id] [inert]').length >= 2, null, { timeout: BOOT_MS })
		await sleep(1000)
		await frame.locator('[data-tile-id] [data-tile]').first().click()
		await frame.locator('[data-live] summary').click({ timeout: BOOT_MS })
		await sleep(1000)
		const tile = await frame.locator('[data-tile-id]').first().getAttribute('data-tile-id')
		const target = { selector: '', x: 0.5, y: 0.5, tag: 'button', text: 'Submit', label: '' }
		await page.evaluate((list) => document.querySelector('iframe').contentWindow.postMessage({ channel: window.__channel, type: 'tile:track', data: { req: 9001, list } }, '*'), [{ tile, fx: 0.5, fy: 0.5, target }])
		await sleep(500)
		const tracked = await page.evaluate(() => window.__rects[9001]?.[0] ?? null)
		const drawn = await frame.evaluate(() => {
			const tile = document.querySelector('[data-tile-id]')
			const t = tile.getBoundingClientRect()
			const k = tile.offsetWidth ? t.width / tile.offsetWidth : 1
			const at = (drawing) => {
				const r = [...drawing.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Submit').getBoundingClientRect()
				return { x: (r.left - t.left) / k, y: (r.top - t.top) / k }
			}
			return { render: at(tile.querySelector('[data-live] [data-tile-drawing]')), snapshot: at(tile.querySelector('[inert][data-tile-drawing]')) }
		})
		return { tracked, ...drawn }
	} finally {
		await fresh.close()
	}
}

try {
	const page = await context.newPage()
	const logs = []
	page.on('pageerror', (e) => logs.push(String(e).slice(0, 300)))

	await page.goto(`${ORIGIN}${viewerPath}#/?canvas=set:home/card`, { waitUntil: 'load', timeout: BOOT_MS })
	let frame = null
	for (const deadline = Date.now() + BOOT_MS; !frame && Date.now() < deadline; await sleep(100)) frame = page.frames().find((x) => x.url().includes('frame=1'))
	if (!frame) throw new Error('the shell never framed the Prototype')
	await frame.waitForFunction(() => document.querySelectorAll('[data-tile-id] [inert]').length >= 2, null, { timeout: BOOT_MS })
	await sleep(1000)
	const iframe = await page.locator('iframe').first().boundingBox()

	const bar = page.getByRole('toolbar', { name: 'Annotate' })
	async function tool(kind) {
		if (!(await bar.isVisible().catch(() => false))) await page.getByRole('button', { name: 'Annotate' }).first().click()
		await bar.getByText(kind === 'note' ? 'Note' : 'Comment', { exact: true }).first().click()
		await sleep(600)
	}
	// Boxes in the shell page's coordinates.
	const inPage = async (loc) => {
		const r = await loc.evaluate((e) => (({ x, y, width: w, height: h }) => ({ x, y, w, h }))(e.getBoundingClientRect()))
		return { ...r, x: r.x + iframe.x, y: r.y + iframe.y }
	}
	const tile = frame.locator('[data-tile-id]').first()
	const button = (name) => tile.locator('[data-tile-drawing] button').getByText(name, { exact: true }).first()
	const submit = button('Submit')
	const no = button('No')

	async function leave(kind, on = submit, words = `${kind} on submit`) {
		await tool(kind)
		const r = await inPage(on)
		await page.mouse.click(r.x + r.w / 2, r.y + r.h / 2)
		const box = page.getByPlaceholder(kind === 'note' ? 'What should change?' : 'Add a comment…').first()
		await box.waitFor({ timeout: 5000 })
		await box.fill(words)
		await box.press('Enter')
		await page.getByLabel(new RegExp(`^(Note \\d+|Comment from .*): ${words}$`)).first().waitFor({ timeout: 10000 })
		await page.keyboard.press('Escape')
		await sleep(400)
	}
	// A pin's tip: the point its wrapper sits at.
	async function tipOf(words) {
		const pin = page.locator(`button[data-annotate-pin][aria-label$=": ${words}"]`).first()
		if (!(await pin.count())) return null
		return pin.evaluate((b) => (({ left: x, top: y }) => ({ x, y }))(b.parentElement.getBoundingClientRect()))
	}

	if (mode === 'make') {
		for (const kind of ['note', 'comment']) await leave(kind)
		await leave('comment', no, 'comment on no')
	}

	answer.tile = await inPage(tile)
	answer.submit = await inPage(submit)
	answer.no = await inPage(no)
	for (const kind of ['note', 'comment']) {
		await tool(kind)
		answer.pins[kind] = await tipOf(`${kind} on submit`)
		if (kind === 'note') answer.pins.old = await tipOf('old note')
		else answer.pins.no = await tipOf('comment on no')
	}
	if (evidence) await page.screenshot({ path: evidence })
	if (mode === 'measure') answer.live = await liveTile()
	answer.errors = logs
} finally {
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
