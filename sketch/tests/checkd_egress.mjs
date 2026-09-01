// The check browser's egress allowlist, driven headless. `test_checkd_egress.py`
// reads the JSON this prints on stdout and makes the assertions.
//
// A Prototype is JavaScript one user wrote, and the check runs it in a browser
// on the server. Seven cases, two browsers, because a resolver rule is a launch
// argument:
//
//   filtered      the shipped pair: resolver rule and route filter
//   resolverOnly  the resolver rule alone stops an unknown hostname
//   routeOnly     the route filter alone stops another origin on loopback
//   control       neither: the same request reaches the network
//   sockets       the filter against a WebSocket and a remote picture
//   socketsOpen   the same two targets with no filter at all
//   report        one whole `runCheck`, read for what it says about the block
//
// `control` and `socketsOpen` are what make the others mean something. Without
// them, a "blocked" answer could be a target that was never reachable.
//
// The last three cases run against two throwaway HTTP servers this file starts
// on loopback, one for the origin under test and one for the neighbour. They
// count what reached them, which is the ground truth: a WebSocket the browser
// thinks it opened against a Playwright stub never touches the server.
//
//   node checkd_egress.mjs <playwright entry> <site host> <port>
import { createHash } from 'node:crypto'
import { createServer } from 'node:http'
import { pathToFileURL } from 'node:url'

import { egressWarnings, restrictEgress, runCheck } from '../../checkd/check-lib.mjs'

const [, , playwrightEntry, host, port] = process.argv
const { chromium } = await import(pathToFileURL(playwrightEntry).href)

// The Viewer is not used here. It needs a Prototype and a Runtime, and this is
// about the network layer, which is the same for any document on the origin.
const PATH = '/api/method/frappe.ping'
const DOCUMENT = `http://${host}:${port}${PATH}`
// The same web server on another origin. This is the SSRF shape: a neighbouring
// service on loopback that the check browser must not reach.
const CROSS_ORIGIN = `http://127.0.0.1:${port}${PATH}`
const UNKNOWN_HOST = 'http://d2t-nowhere.example/'

const MAP = `MAP ${host} 127.0.0.1`
const CATCH_ALL = `${MAP},MAP * ~NOTFOUND`

/** `ok` when the request reached the network, `blocked` when it did not. */
async function probe(page, target) {
	return await page.evaluate(async (u) => {
		try {
			// no-cors, so a cross-origin answer without CORS headers still counts
			// as reached. The question is the network, not the response body.
			await fetch(u, { mode: 'no-cors', cache: 'no-store' })
			return 'ok'
		} catch {
			return 'blocked'
		}
	}, target)
}

/** One case: open the document, then probe each target from inside it. */
async function measure(browser, { filter }) {
	const context = await browser.newContext()
	const aborted = []
	if (filter) {
		await restrictEgress(context, DOCUMENT)
		context.on('requestfailed', (request) => aborted.push(request.url()))
	}

	try {
		const page = await context.newPage()
		const response = await page.goto(DOCUMENT, { waitUntil: 'commit', timeout: 30000 })
		return {
			document: response?.status() === 200 ? 'ok' : `status ${response?.status()}`,
			sameOrigin: await probe(page, DOCUMENT),
			crossOrigin: await probe(page, CROSS_ORIGIN),
			unknownHost: await probe(page, UNKNOWN_HOST),
			dataUrl: await probe(page, 'data:text/plain,sketch'),
			aborted,
		}
	} finally {
		await context.close()
	}
}

// ------------------------------------------------------- the socket cases

/** A 1x1 transparent PNG. A picture the browser really decodes. */
const PIXEL = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
	'base64',
)

// A stand-in Runtime, so `runCheck` can read a real report off a page this file
// controls. It reports the one shape `runCheck` waits for, and it reports it
// only after both remote calls have finished, so the report can never be read
// before the filter has seen them.
//
// The Viewer is not used: it needs a Prototype, a Runtime build and a
// signature, and none of that changes the network layer under test.
const STUB = `<!doctype html><title>stub</title><body><script>
const other = new URLSearchParams(location.search).get('other')
let left = 2
const finish = () => {
	if (--left > 0) return
	window.__sketch = {
		status: 'ok', routes: ['/'], errors: [], warnings: [], consoleErrors: [], timings: {},
	}
}
const once = (run) => { let spent = false; return () => { if (!spent) { spent = true; run() } } }
window.__sketchGoto = () => {}

const picture = new Image()
const pictureDone = once(finish)
picture.onload = pictureDone
picture.onerror = pictureDone
picture.src = other + '/pixel.png'
document.body.appendChild(picture)

const socket = new WebSocket(other.replace('http:', 'ws:') + '/socket')
const socketDone = once(finish)
socket.onopen = socketDone
socket.onclose = socketDone
socket.onerror = socketDone
</script></body>`

/**
 * One throwaway origin on loopback: a document, a picture and a WebSocket.
 *
 * It counts every upgrade it accepts. That count is the only honest answer to
 * "did the socket connect": Playwright answers a routed WebSocket itself, so
 * the page can see an open socket that never reached any server.
 *
 * The handshake is written by hand. checkd has no WebSocket library, and the
 * accept key is one SHA-1 of the client key and the RFC 6455 GUID.
 */
async function startOrigin() {
	const counts = { upgrades: 0, pictures: 0 }

	const server = createServer((req, res) => {
		const path = req.url.split('?')[0]
		if (path === '/pixel.png') {
			counts.pictures += 1
			res.writeHead(200, { 'content-type': 'image/png', 'cache-control': 'no-store' })
			return res.end(PIXEL)
		}
		res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
		res.end(path === '/stub' ? STUB : '<!doctype html><title>egress</title><body>egress</body>')
	})

	// An upgraded socket leaves the server's own connection list, so this file
	// holds it. Without that, `close` waits forever on a socket still open.
	const live = new Set()

	server.on('upgrade', (req, socket) => {
		counts.upgrades += 1
		live.add(socket)
		socket.on('close', () => live.delete(socket))
		const accept = createHash('sha1')
			.update(`${req.headers['sec-websocket-key']}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
			.digest('base64')
		socket.write(
			'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n' +
				`Connection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`,
		)
	})

	await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
	const origin = `http://127.0.0.1:${server.address().port}`
	const close = () =>
		new Promise((resolve) => {
			for (const socket of live) socket.destroy()
			server.closeAllConnections()
			server.close(resolve)
		})
	return { origin, counts, close }
}

/** `open` when the socket opened, `closed <code>` or `error` when it did not. */
async function socketProbe(page, origin) {
	return await page.evaluate(async (target) => {
		return await new Promise((resolve) => {
			const socket = new WebSocket(`${target.replace('http:', 'ws:')}/socket`)
			socket.onopen = () => resolve('open')
			socket.onerror = () => resolve('error')
			socket.onclose = (event) => resolve(`closed ${event.code}`)
			setTimeout(() => resolve('timeout'), 5000)
		})
	}, origin)
}

/** `loaded` when the picture decoded, `blank` when it rendered at zero width. */
async function pictureProbe(page, origin) {
	return await page.evaluate(async (target) => {
		return await new Promise((resolve) => {
			const img = document.createElement('img')
			img.onload = () => resolve(img.naturalWidth > 0 ? 'loaded' : 'blank')
			img.onerror = () => resolve('blank')
			img.src = `${target}/pixel.png`
			document.body.appendChild(img)
			setTimeout(() => resolve('timeout'), 5000)
		})
	}, origin)
}

/**
 * The socket and picture case, with the filter on or off.
 *
 * `site` is the origin under test. `other` is the neighbouring service on
 * loopback, which is the SSRF shape.
 */
async function measureSockets(browser, site, other, { filter }) {
	const context = await browser.newContext()
	let refused = null
	if (filter) refused = await restrictEgress(context, `${site.origin}/`)

	try {
		const page = await context.newPage()
		await page.goto(`${site.origin}/`, { waitUntil: 'commit', timeout: 30000 })

		const answer = {
			sameOriginSocket: await socketProbe(page, site.origin),
			crossOriginSocket: await socketProbe(page, other.origin),
			remotePicture: await pictureProbe(page, other.origin),
		}
		// The servers answer on their own event loop. Let them catch up before
		// the counts are read.
		await page.waitForTimeout(500)
		answer.siteUpgrades = site.counts.upgrades
		answer.otherUpgrades = other.counts.upgrades
		answer.otherPictures = other.counts.pictures
		answer.warnings = egressWarnings(refused)
		answer.refusedTotal = refused ? refused.total : 0
		answer.refusedOrigins = refused ? refused.origins.map((entry) => entry.origin) : []
		return answer
	} finally {
		await context.close()
	}
}

/**
 * One whole `runCheck`, so the report itself is the measurement.
 *
 * This is the case that holds the wiring: the filter counts the refusals, and
 * `body` must put them in `warnings`. Without it a refused picture is empty in
 * the screenshot and the report says nothing at all.
 */
async function measureReport(browser, site, other) {
	const url = `${site.origin}/stub?other=${encodeURIComponent(other.origin)}`
	const report = await runCheck(browser, { url, timeoutMs: 20000 })
	return {
		status: report.status,
		errors: report.errors,
		consoleErrors: report.consoleErrors,
		warnings: report.warnings,
		otherUpgrades: other.counts.upgrades,
		otherPictures: other.counts.pictures,
	}
}

const answers = {}

const capped = await chromium.launch({ args: [`--host-resolver-rules=${CATCH_ALL}`] })
try {
	answers.filtered = await measure(capped, { filter: true })
	answers.resolverOnly = await measure(capped, { filter: false })
} finally {
	await capped.close()
}

// A literal 127.0.0.1 is not touched by a MAP rule, so the socket cases run on
// this browser. They are about the route filter, which is the control.
const open = await chromium.launch({ args: [`--host-resolver-rules=${MAP}`] })
try {
	answers.routeOnly = await measure(open, { filter: true })
	answers.control = await measure(open, { filter: false })

	// A fresh pair of servers per case, so one case never reads the other's
	// counts.
	for (const [name, measure] of [
		['sockets', (site, other) => measureSockets(open, site, other, { filter: true })],
		['socketsOpen', (site, other) => measureSockets(open, site, other, { filter: false })],
		['report', (site, other) => measureReport(open, site, other)],
	]) {
		const site = await startOrigin()
		const other = await startOrigin()
		try {
			answers[name] = await measure(site, other)
		} finally {
			await site.close()
			await other.close()
		}
	}
} finally {
	await open.close()
}

process.stdout.write(JSON.stringify(answers))
