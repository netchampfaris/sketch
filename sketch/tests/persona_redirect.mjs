// The owner's Viewer on a Prototype with an app-wide persona, whose Old page sends the person home and opens a panel
// that closes on any route change. `test_persona_redirect.py` writes the Prototype, reads the JSON this prints on
// stdout and makes the assertions.
//
//   node persona_redirect.mjs <playwright entry> <host> <port> <viewer path> <sid> <link|hash|bare>
//
// link: open Home as Grace (`?s=`), click the link to Old, wait for the redirect and a while longer; read the hash
//       and whether the panel is open. Then go Back, and read where that lands.
// hash: the same, but type the old route in the address (a hash change, as Back and Forward are).
// bare: no persona; click the link to Old. The page's own behaviour, for comparison.
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid, mode] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const BOOT_MS = 60000
// After the redirect: Sketch's mirror runs a tick after a navigation lands, and a second navigation takes a moment.
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

	const start = mode === 'bare' ? '#/' : '#/?s=view-as.grace'
	await page.goto(`${ORIGIN}${viewerPath}${start}`, { waitUntil: 'load', timeout: BOOT_MS })
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
	const read = async () => ({
		hash: await frame.evaluate(() => location.hash),
		panelOpen: (await frame.getByText('Notifications panel').count()) > 0,
		text: await frame.evaluate(() => document.body.innerText.slice(0, 500)),
	})

	await frame.getByText('Home page').first().waitFor({ timeout: BOOT_MS }).catch(why)
	answer.before = await read()
	if (mode === 'hash') await frame.evaluate(() => (location.hash = '#/old'))
	else await frame.getByText('Old link').click()
	// Old sends the person home; the panel may already be shut again, which is what the test catches.
	await frame.waitForFunction(() => !location.hash.includes('old'), null, { timeout: BOOT_MS }).catch(why)
	await frame.getByText('Home page').first().waitFor({ timeout: BOOT_MS }).catch(why)
	await sleep(SETTLE_MS)
	answer.after = await read()

	if (mode === 'link') {
		await frame.evaluate(() => history.back())
		await sleep(SETTLE_MS)
		answer.back = await read()
	}
	answer.errors = logs
} finally {
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
