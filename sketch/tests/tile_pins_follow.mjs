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
	answer.errors = logs
} finally {
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
