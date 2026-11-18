// The owner's Viewer on a Prototype whose elements hide when something closes (sketch/tests/reveal_tree.py).
// `test_pins_reveal.py` writes the Prototype and two old-style notes, reads the JSON this prints on stdout and makes
// the assertions.
//
//   node pins_reveal.mjs <playwright entry> <host> <port> <viewer path> <sid> [evidence dir]
//
// The owner leaves a note and a comment on three hidden spots, each with its way open: the "Certificate available"
// checkbox (Filters popover, then its Certificate group), the Documents card's description, the Reviews tab's words.
// Then everything is closed, and for each pin it reports where it sits, whether it is faded, and where it sits after
// the page scrolls. Then each pin is clicked, and each comment's row in the list, with everything closed before each:
// it reports whether the element came back and where the box opened.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid, evidence] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const BOOT_MS = 60000
const SCROLL = 120

// What each spot is in the frame, and what stands in for it while it is hidden.
const SPOTS = {
	cert: { text: 'Certificate available', words: 'cert', stand: (f) => f.getByRole('button', { name: 'Filters' }) },
	docs: { text: 'Signed agreements', words: 'docs', stand: (f) => f.getByRole('button', { name: /^Documents/ }) },
	tab: { text: 'Clear and short', words: 'tab', stand: (f) => f.getByRole('tab', { name: 'Reviews' }) },
}

const answer = { made: {}, closed: {}, scrolled: {}, opened: {}, listed: {}, old: {} }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: evidence ? 2 : 1 })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])

try {
	const page = await context.newPage()
	const logs = []
	page.on('pageerror', (e) => logs.push(String(e).slice(0, 300)))
	const shot = (name) => evidence && page.screenshot({ path: `${evidence}/reveal-${name}.png` })

	await page.goto(`${ORIGIN}${viewerPath}#/`, { waitUntil: 'load', timeout: BOOT_MS })
	let frame = null
	for (const deadline = Date.now() + BOOT_MS; !frame && Date.now() < deadline; await sleep(100)) frame = page.frames().find((x) => x.url().includes('frame=1'))
	if (!frame) throw new Error('the shell never framed the Prototype')
	await frame.getByText('Signed agreements').waitFor({ timeout: BOOT_MS })
	const iframe = await page.locator('iframe').first().boundingBox()

	// ---- The toolbar ----------------------------------------------------------------------------
	const bar = page.getByRole('toolbar', { name: 'Annotate' })
	async function tool(kind) {
		if (!(await bar.isVisible().catch(() => false))) await page.getByRole('button', { name: 'Annotate' }).first().click()
		await bar.getByText(kind === 'note' ? 'Note' : 'Comment', { exact: true }).first().click()
		await sleep(300)
	}
	async function toolOff() {
		if (await bar.isVisible().catch(() => false)) await bar.getByRole('button', { name: 'Close toolbar' }).click()
		await sleep(300)
	}

	// ---- The page: open the way to a spot, or close everything ------------------------------------
	const shown = (text) => frame.getByText(text).first().isVisible().catch(() => false)
	async function openTo(key) {
		if (key === 'cert') {
			if (!(await frame.getByRole('dialog').count())) await frame.getByRole('button', { name: 'Filters' }).click()
			await frame.getByRole('button', { name: /^Certificate/ }).waitFor()
			if (!(await shown('Certificate available'))) await frame.getByRole('button', { name: /^Certificate/ }).click()
		} else if (key === 'docs') {
			if (!(await shown('Signed agreements'))) await frame.getByRole('button', { name: /^Documents/ }).click()
		} else await frame.getByRole('tab', { name: 'Reviews' }).click()
		await frame.getByText(SPOTS[key].text).first().waitFor()
	}
	// Each section closed by its own control, so each comes back only when the pin's way presses it again.
	async function closeAll() {
		if (await shown('Certificate available')) await frame.getByRole('button', { name: /^Certificate/ }).click()
		if (await frame.getByRole('dialog').count()) await frame.getByRole('button', { name: 'Filters' }).click()
		if (await shown('Signed agreements')) await frame.getByRole('button', { name: /^Documents/ }).click()
		if (await shown('Clear and short')) await frame.getByRole('tab', { name: 'Overview' }).click()
		await sleep(400)
		for (const s of Object.values(SPOTS)) if (await shown(s.text)) throw new Error(`${s.text} is still shown after closing`)
	}

	// ---- Leave a note or a comment on a spot ------------------------------------------------------
	async function leave(kind, key) {
		await toolOff()
		await openTo(key)
		await tool(kind)
		const r = await frame.getByText(SPOTS[key].text).first().boundingBox()
		const at = { x: r.x + Math.min(20, r.width / 2), y: r.y + r.height / 2 }
		await page.mouse.move(at.x, at.y)
		await sleep(150)
		await page.mouse.click(at.x, at.y)
		const box = page.getByPlaceholder(kind === 'note' ? 'What should change?' : 'Add a comment…').first()
		await box.waitFor({ timeout: 5000 })
		await box.fill(`${kind} ${SPOTS[key].words}`)
		await box.press('Enter')
		await page.getByLabel(new RegExp(`^(Note \\d+|Comment from .*): ${kind} ${SPOTS[key].words}$`)).first().waitFor({ timeout: 10000 })
		await page.keyboard.press('Escape')
		await sleep(300)
	}

	// ---- Pins: where each sits, in the frame's coordinates ----------------------------------------
	const pinOf = (kind, key) => page.locator(`button[data-annotate-pin][aria-label$=": ${kind} ${SPOTS[key].words}"]`).first()
	async function pinState(kind, key) {
		const pin = pinOf(kind, key)
		if (!(await pin.count())) return { shown: false }
		const p = await pin.evaluate((b) => ({ x: parseFloat(b.style.left), y: parseFloat(b.style.top), faded: b.classList.contains('opacity-50') }))
		return { shown: true, x: p.x - iframe.x, y: p.y - iframe.y, faded: p.faded }
	}
	const rectOf = async (loc) => (await loc.count()) && loc.first().evaluate((e) => (({ x, y, width: w, height: h }) => ({ x, y, w, h }))(e.getBoundingClientRect()))
	const inside = (p, r) => !!r && p.shown && p.x >= r.x - 1 && p.x <= r.x + r.w + 1 && p.y >= r.y - 1 && p.y <= r.y + r.h + 1

	async function closedPins(kind) {
		await toolOff()
		await closeAll()
		await tool(kind)
		await sleep(400)
		for (const key of Object.keys(SPOTS)) {
			const pin = await pinState(kind, key)
			const stand = await rectOf(SPOTS[key].stand(frame))
			answer.closed[`${kind}:${key}`] = { ...pin, onStandIn: inside(pin, stand) }
		}
	}

	// The page scrolls a little: each pin moves with its stand-in.
	async function scrolled(kind) {
		const before = Object.fromEntries(await Promise.all(Object.keys(SPOTS).map(async (k) => [k, await pinState(kind, k)])))
		const by = await frame.evaluate((dy) => (window.scrollBy(0, dy), window.scrollY), SCROLL)
		await sleep(500)
		for (const key of Object.keys(SPOTS)) {
			const pin = await pinState(kind, key)
			const stand = await rectOf(SPOTS[key].stand(frame))
			answer.scrolled[`${kind}:${key}`] = { by, moved: Math.round(before[key].y - pin.y), onStandIn: inside(pin, stand) }
		}
		await frame.evaluate(() => window.scrollTo(0, 0))
		await sleep(400)
	}

	// Click the way to an element, and report whether it came back and the box opened on it.
	async function opened(kind, key, how) {
		const box = page.getByRole('dialog', { name: kind === 'note' ? 'Note' : 'Comment' })
		await box.waitFor({ timeout: 6000 }).catch(() => {})
		await sleep(400)
		const target = await rectOf(frame.getByText(SPOTS[key].text))
		const visible = await shown(SPOTS[key].text)
		const pin = await pinState(kind, key)
		const boxRect = await rectOf(box)
		await shot(`${how}-${kind}-${key}`)
		await page.keyboard.press('Escape')
		await sleep(300)
		// The pin sits on its element again, not faded, and the box opened beside it.
		return { visible, boxOpen: !!boxRect, pinOnTarget: inside(pin, target), faded: pin.faded, boxNear: !!boxRect && !!target && Math.abs(boxRect.y - (target.y + iframe.y)) < 260 }
	}
	async function clickPins(kind) {
		for (const key of Object.keys(SPOTS)) {
			await closedPins(kind)
			await pinOf(kind, key).click()
			answer.opened[`${kind}:${key}`] = await opened(kind, key, 'pin')
		}
	}

	// ---- The run ---------------------------------------------------------------------------------
	try {
		for (const kind of ['note', 'comment']) for (const key of Object.keys(SPOTS)) await leave(kind, key)
	} catch (e) {
		await shot('failed')
		throw e
	}

	for (const kind of ['note', 'comment']) {
		await closedPins(kind)
		await shot(`closed-${kind}`)
		await scrolled(kind)
		await clickPins(kind)
	}

	// From the comments list: each comment's row.
	for (const key of Object.keys(SPOTS)) {
		await closedPins('comment')
		const show = page.getByRole('button', { name: 'Show comments' })
		if (await show.count()) await show.first().click()
		await page.locator('button', { hasText: `comment ${SPOTS[key].words}` }).first().click()
		answer.listed[key] = await opened('comment', key, 'list')
	}

	// Old notes, made before a way was kept: one sits on its nearest ancestor on the page, one has none small enough.
	await closedPins('note')
	for (const words of ['old near', 'old gone']) {
		const pin = page.locator(`button[data-annotate-pin][aria-label$=": ${words}"]`).first()
		const state = (await pin.count()) ? await pin.evaluate((b) => ({ x: parseFloat(b.style.left), y: parseFloat(b.style.top), faded: b.classList.contains('opacity-50') })) : null
		const section = await rectOf(frame.locator('section', { hasText: 'Documents' }))
		answer.old[words] = state ? { shown: true, faded: state.faded, onSection: inside({ shown: true, x: state.x - iframe.x, y: state.y - iframe.y }, section) } : { shown: false }
	}
	await shot('old')
	answer.errors = logs
} finally {
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
