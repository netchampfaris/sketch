// The sandboxed Viewer, driven headless. `test_viewer_live_reload.py` reads the
// JSON this prints on stdout and makes the assertions.
//
// Two questions, one browser, one page load:
//
//   1. Does the real built viewer.html still boot under the sandbox CSP? The
//      document lands in an opaque origin, so every Runtime request is
//      cross-origin and localStorage throws.
//   2. Does the owner's live reload still work there? The page sends no cookie,
//      so the poller authenticates with the signature the renderer minted into
//      the payload (sketch/api.py signed_revision).
//
// The reload is provoked the way an agent provokes it: a file appears in the
// tree on disk, so `prototype_files.revision` moves.
//
//   node viewer_live_reload.mjs <playwright entry> <host> <port> <viewer path>
//                               <authorization> <tree dir>
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const [, , playwrightEntry, host, port, viewerPath, authorization, treeDir] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

const URL_UNDER_TEST = `http://${host}:${port}${viewerPath}`
const NEW_FILE = 'src/pages/D2tLater.vue'
const BOOT_MS = 60000
const RELOAD_MS = 30000

/** The revision reads the browser made, in order. The proof the poll ran. */
const polls = []
const answer = { url: URL_UNDER_TEST }

/** Wait until the page has polled at least `count` times, or give up. */
async function untilPolled(page, count, timeout) {
	const deadline = Date.now() + timeout
	while (polls.length < count && Date.now() < deadline) await page.waitForTimeout(250)
}

const browser = await chromium.launch({ args: [`--host-resolver-rules=MAP ${host} 127.0.0.1`] })
const context = await browser.newContext()

// The owner's own tab. A real owner arrives with a session cookie; the suite
// has API keys, so the header stands in for the cookie.
//
// It is put on the document request alone, and never on the whole context. A
// context header rides on the module script request as well, which makes that
// request non-simple and buys it a CORS preflight that /sketch-runtime does
// not answer. That is a property of this harness, not of the shipped page: a
// real cookie never triggers a preflight.
await context.route(URL_UNDER_TEST, (route) =>
	route.continue({ headers: { ...route.request().headers(), authorization } }),
)

try {
	const page = await context.newPage()
	page.on('response', (response) => {
		const url = response.url()
		if (url.includes('signed_revision')) polls.push({ url, status: response.status() })
	})

	const response = await page.goto(URL_UNDER_TEST, { waitUntil: 'load', timeout: BOOT_MS })
	answer.status = response?.status() ?? 0
	answer.csp = response?.headers()['content-security-policy'] ?? ''

	// 1. the boot. window.__sketch is the contract `check` reads.
	await page.waitForFunction(() => window.__sketch !== undefined, null, { timeout: BOOT_MS })
	Object.assign(
		answer,
		await page.evaluate(() => {
			const data = JSON.parse(document.getElementById('sketch-data').textContent)
			return {
				// "null" is the proof the sandbox landed. A same-origin document
				// prints the site origin here.
				origin: String(window.origin),
				// The SPA's token, which the token theft read. Out of reach from
				// an opaque origin, and not in this document either way.
				csrf: typeof window.csrf_token,
				bootStatus: window.__sketch.status,
				errors: window.__sketch.errors,
				consoleErrors: window.__sketch.consoleErrors,
				// What the renderer minted into the page for the poller.
				live: Boolean(data.live),
				hasCredential: Boolean(data.sig),
				heading: document.querySelector('h1')?.textContent ?? '',
			}
		}),
	)

	// 2. the poller reaches the endpoint from the opaque origin.
	await untilPolled(page, 1, RELOAD_MS)
	answer.pollsBeforeWrite = polls.length

	// 3. the credential is what authorises the read. One character changed must
	//    404, from the same page that just read a 200.
	const good = polls.at(-1)?.url ?? ''
	const forgedUrl = good.replace(/&sig=(.)/, (m, c) => '&sig=' + (c === '0' ? '1' : '0'))
	// `null` when the page never polled. The poll cases above are what say so;
	// this one must not fail the whole run with a fetch of an empty URL.
	answer.forged = good
		? await page.evaluate(async (url) => {
				const r = await fetch(url, { cache: 'no-store', credentials: 'omit' })
				return r.status
			}, forgedUrl)
		: null

	// 4. the reload. A new file moves the revision, the way an agent write does.
	await page.evaluate(() => {
		window.__d2tMark = true
	})
	mkdirSync(join(treeDir, 'src', 'pages'), { recursive: true })
	writeFileSync(join(treeDir, NEW_FILE), '<template><p>later</p></template>\n', 'utf-8')

	try {
		// The mark is gone and the Runtime booted again: this is a new document.
		await page.waitForFunction(
			() => window.__d2tMark === undefined && window.__sketch !== undefined,
			null,
			{ timeout: RELOAD_MS },
		)
		answer.reloaded = true
	} catch {
		answer.reloaded = false
	}

	// The forged read above went to the same method, so it is dropped here.
	// `polls` is the poller's own traffic and nothing else.
	answer.polls = polls.filter((p) => p.url !== forgedUrl)
	answer.pollStatuses = [...new Set(answer.polls.map((p) => p.status))]
} finally {
	rmSync(join(treeDir, NEW_FILE), { force: true })
	await context.close()
	await browser.close()
}

process.stdout.write(JSON.stringify(answer))
