// The Viewer, driven headless: the owner's shell with the Prototype in its sandboxed frame.
// `test_viewer_live_reload.py` reads the JSON this prints on stdout and makes the assertions.
//
// Two questions, one browser, one page load:
//
//   1. Does the real built frame still boot under the sandbox CSP? The frame lands in an opaque
//      origin, so every Runtime request is cross-origin and localStorage throws.
//   2. Does the owner's live reload still work? The shell is Sketch's own page, so it polls
//      `sketch.api.prototype_revision` with the session (runtime/shell/liveReload.ts) and reloads
//      the frame alone when the revision moves.
//
// The reload is provoked the way an agent provokes it: a file appears in the tree on disk, so
// `prototype_files.revision` moves.
//
//   node viewer_live_reload.mjs <playwright entry> <host> <port> <viewer path> <sid> <tree dir>
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { get } from 'node:http'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, sid, treeDir] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const ORIGIN = `http://${host}:${port}`
const URL_UNDER_TEST = `${ORIGIN}${viewerPath}`
const NEW_FILE = 'src/pages/D2tLater.vue'
const BOOT_MS = 60000
const RELOAD_MS = 30000

/** The revision reads the shell made, in order. The proof the poll ran. */
const polls = []
const answer = { url: URL_UNDER_TEST }

/** Wait until the shell has polled at least `count` times, or give up. */
async function untilPolled(page, count, timeout) {
	const deadline = Date.now() + timeout
	while (polls.length < count && Date.now() < deadline) await page.waitForTimeout(250)
}

/** The status of a GET to `url` with no cookie at all. */
function statusWithoutSession(url) {
	const { pathname, search } = new URL(url)
	return new Promise((resolve, reject) => {
		get({ host: '127.0.0.1', port, path: pathname + search, headers: { Host: host } }, (r) => {
			r.resume()
			resolve(r.statusCode)
		}).on('error', reject)
	})
}

/** The shell's frame, once it has a document of its own. */
async function frameOf(page) {
	const deadline = Date.now() + BOOT_MS
	while (Date.now() < deadline) {
		const frame = page.frames().find((f) => f.url().includes('frame=1'))
		if (frame) return frame
		await page.waitForTimeout(250)
	}
	throw new Error('the shell never framed the Prototype')
}

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext()
// The owner's own session, the way they arrive from the Sketch UI.
await context.addCookies([{ name: 'sid', value: sid, url: ORIGIN }])

try {
	const page = await context.newPage()
	page.on('response', (response) => {
		const url = response.url()
		if (url.includes('prototype_revision')) polls.push({ url, status: response.status() })
		if (url.includes('frame=1')) {
			answer.frameStatus = response.status()
			answer.frameCsp = response.headers()['content-security-policy'] ?? ''
		}
	})

	const response = await page.goto(URL_UNDER_TEST, { waitUntil: 'load', timeout: BOOT_MS })
	answer.status = response?.status() ?? 0
	answer.csp = response?.headers()['content-security-policy'] ?? ''

	// 1. the boot. window.__sketch is the contract `check` reads, inside the frame.
	const frame = await frameOf(page)
	await frame.waitForFunction(() => window.__sketch !== undefined, null, { timeout: BOOT_MS })
	await frame.waitForFunction(() => window.__sketch.status !== 'booting', null, { timeout: BOOT_MS }).catch(() => {})
	Object.assign(
		answer,
		await frame.evaluate(() => {
			const data = JSON.parse(document.getElementById('sketch-data').textContent)
			return {
				// "null" is the proof the sandbox landed. A same-origin document prints the site origin here.
				origin: String(window.origin),
				// The session's token stays in the shell. The frame has none.
				csrf: typeof window.csrf_token,
				bootStatus: window.__sketch.status,
				errors: window.__sketch.errors,
				consoleErrors: window.__sketch.consoleErrors,
				frameKeys: Object.keys(data).sort(),
				heading: document.querySelector('h1')?.textContent ?? '',
			}
		}),
	)
	answer.shellOrigin = await page.evaluate(() => String(window.origin))

	// 2. the shell polls with the session.
	await untilPolled(page, 1, RELOAD_MS)
	answer.pollsBeforeWrite = polls.length

	// 3. the session is what authorises the read: the same URL with no cookie is refused.
	const good = polls.at(-1)?.url ?? ''
	answer.withoutSession = good ? await statusWithoutSession(good) : null

	// 4. the reload. A new file moves the revision, the way an agent write does. The frame reloads and the
	//    shell stays put.
	await page.evaluate(() => {
		window.__d2tShell = true
	})
	await frame.evaluate(() => {
		window.__d2tMark = true
	})
	mkdirSync(join(treeDir, 'src', 'pages'), { recursive: true })
	writeFileSync(join(treeDir, NEW_FILE), '<template><p>later</p></template>\n', 'utf-8')

	try {
		const deadline = Date.now() + RELOAD_MS
		let fresh = false
		while (!fresh && Date.now() < deadline) {
			await page.waitForTimeout(250)
			const now = page.frames().find((f) => f.url().includes('frame=1'))
			fresh = Boolean(
				now && (await now.evaluate(() => window.__d2tMark === undefined && window.__sketch !== undefined).catch(() => false)),
			)
		}
		answer.reloaded = fresh
	} catch {
		answer.reloaded = false
	}
	answer.shellKept = await page.evaluate(() => window.__d2tShell === true).catch(() => false)

	answer.polls = polls
	answer.pollStatuses = [...new Set(polls.map((p) => p.status))]
} finally {
	rmSync(join(treeDir, NEW_FILE), { force: true })
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
