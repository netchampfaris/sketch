// The owner's Viewer with an editor's hostile option in its frame. `test_frame_cannot_act.py` writes the option, reads
// the JSON this prints on stdout and makes the assertions.
//
//   node frame_cannot_act.mjs <playwright entry> <host> <port> <viewer path> <sid> <attack|control> [evidence dir]
//
// attack:  open the canvas, so every option renders and the hostile one runs; wait for its report and a while
//          longer for any effect of its forged messages; record every /api/method/ request by who sent it.
// pick:    the option only lies about the set the canvas shows; the owner opens Hero from the shell's panel.
// control: the same page with the attack disarmed; the owner's own tile menu, Make default on the editor's calm
//          option, then Undo. The shell path must work while the frame path does not.
import { writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid, mode, evidence] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const CANVAS = `${ORIGIN}${viewerPath}#/?canvas=set:home/card`
const BOOT_MS = 60000
// After the report: forged messages are posted with gaps, and a write they caused would take a moment to go out.
const SETTLE_MS = 2500

const answer = { mode, frameRequests: [], otherRequests: [], popups: [] }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const methodOf = (url) => decodeURIComponent(new URL(url).pathname.split('/api/method/')[1] ?? '')

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
// Evidence is for people to read, so it is drawn at twice the pixels.
const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: evidence ? 2 : 1 })
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])
if (mode === 'control') await context.addInitScript(() => (window.__evilDisarmed = true))
if (mode === 'pick') await context.addInitScript(() => (window.__evilPick = true))

try {
	const page = await context.newPage()
	const logs = []
	page.on('console', (m) => m.type() === 'error' && logs.push(m.text().slice(0, 300)))
	page.on('pageerror', (e) => logs.push(String(e).slice(0, 300)))

	// Who sent each API request: the shell's own page, the Prototype's frame (or a frame inside it), or another page.
	const inFrame = (frame) => {
		for (let f = frame; f; f = f.parentFrame()) if (f.url().includes('frame=1')) return true
		return false
	}
	const where = (request) => {
		const frame = request.frame()
		if (frame.page() !== page) return 'other page'
		return inFrame(frame) ? 'frame' : frame === page.mainFrame() ? 'shell' : 'shell child'
	}
	const record = (request, extra) => {
		if (!request.url().includes('/api/method/')) return
		const row = { method: methodOf(request.url()), http: request.method(), from: where(request), ...extra }
		;(row.from === 'frame' ? answer.frameRequests : answer.otherRequests).push(row)
	}
	context.on('response', (r) => record(r.request(), { status: r.status() }))
	context.on('requestfailed', (r) => record(r, { failed: r.failure()?.errorText ?? 'failed' }))
	context.on('page', async (p) => {
		if (p === page) return
		await p.waitForLoadState('domcontentloaded').catch(() => {})
		answer.popups.push({ url: p.url(), origin: await p.evaluate(() => String(window.origin)).catch((e) => `unreadable: ${e.message}`) })
	})

	await page.goto(CANVAS, { waitUntil: 'load', timeout: BOOT_MS })
	answer.shellUrlBefore = page.url()

	const frame = await (async () => {
		const deadline = Date.now() + BOOT_MS
		while (Date.now() < deadline) {
			const f = page.frames().find((x) => x.url().includes('frame=1'))
			if (f) return f
			await sleep(250)
		}
		throw new Error('the shell never framed the Prototype')
	})()
	const report = frame.locator('#evil-report[data-done]').first()
	await report.waitFor({ state: 'attached', timeout: BOOT_MS }).catch(async (e) => {
		// What the frame shows instead, so a failure says why.
		const seen = await frame.evaluate(() => ({ sketch: window.__sketch, text: document.body.innerText.slice(0, 1500) })).catch(() => null)
		throw new Error(`${e.message}\nthe frame: ${JSON.stringify(seen)}\nerrors: ${JSON.stringify(logs.slice(0, 20))}`)
	})
	answer.frameOrigin = await frame.evaluate(() => String(window.origin))

	if (mode === 'attack') {
		answer.report = JSON.parse(await report.textContent())
		await sleep(SETTLE_MS)
		answer.shellUrlAfter = page.url()
		answer.menuItems = await page.getByRole('menuitem').allInnerTexts()
		answer.toasts = await page.locator('[data-sonner-toast]').allInnerTexts()
		// What the forged messages left open in the shell: shown, not acted on.
		answer.commentBoxOpen = (await page.getByPlaceholder('Add a comment…').count()) + (await page.getByPlaceholder('Add a comment...').count()) > 0
		if (evidence) {
			await page.screenshot({ path: `${evidence}/evidence-frame-cannot-act-after.png` })
			await frame.locator('[data-evil]').first().screenshot({ path: `${evidence}/evidence-frame-cannot-act-after-tile.png` })
		}
	} else if (mode === 'pick') {
		await sleep(3000)
		await page.locator('[data-panel-row]', { hasText: 'Hero' }).first().click()
		// The canvas shows Hero, and the seen mark goes out.
		await sleep(SETTLE_MS)
		answer.view = await frame.evaluate(() => location.hash).catch(() => '')
		answer.lied = (await frame.evaluate(() => window.__evil?.report?.lied ?? 0).catch(() => 0))
	} else {
		// The tile under the "Calm" caption, made live, then its ⋯: the menu the shell draws.
		await sleep(3000)
		const tiles = frame.locator('[data-tile-id]')
		let calm = null
		for (let i = 0; i < (await tiles.count()) && !calm; i++)
			if ((await tiles.nth(i).locator('[data-tile-row="1"]').innerText()).includes('Calm')) calm = tiles.nth(i)
		if (!calm) throw new Error('no Calm tile on the canvas')
		await calm.locator('[data-tile]').click()
		await sleep(1200)

		const writes = []
		page.on('response', async (r) => {
			if (r.frame() !== page.mainFrame() || r.request().method() !== 'POST') return
			const method = methodOf(r.url())
			if (!/variant/.test(method)) return
			writes.push([method, r.status()])
			if (method === 'sketch.api.set_variant_default') answer.defaultAfterMake = (await r.json().catch(() => ({}))).message?.option
		})
		await calm.getByRole('button', { name: 'Actions for this variant' }).click()
		// Past the menu's 300 ms guard, as a person's click is.
		await sleep(700)
		answer.menuItems = await page.getByRole('menuitem').allInnerTexts()
		await page.getByRole('menuitem', { name: 'Make default' }).click()
		const toast = page.locator('[data-sonner-toast]')
		await toast.filter({ hasText: 'default' }).first().waitFor({ timeout: 15000 })
		answer.toastAfterMake = await toast.allInnerTexts()
		// The toast slides in; the picture waits for it to settle.
		await sleep(800)
		if (evidence) await page.screenshot({ path: `${evidence}/evidence-frame-cannot-act-control.png` })
		await toast.getByRole('button', { name: 'Undo' }).first().click()
		const deadline = Date.now() + 15000
		while (writes.length < 2 && Date.now() < deadline) await sleep(250)
		await sleep(1000)
		answer.toastAfterUndo = await toast.allInnerTexts()
		answer.writes = writes
	}
} finally {
	await context.close()
	await browser.close()
}

if (evidence) writeFileSync(`${evidence}/evidence-frame-cannot-act-${mode}.json`, JSON.stringify(answer, null, 1))
process.stdout.write(JSON.stringify(answer))
