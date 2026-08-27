// sketch-checkd. A daemon on 127.0.0.1:8010 that serves POST /check.
//
// A daemon, not one process per check: the 350 ms gap is Node boot and the
// Playwright import, not the browser. Chromium launches in 45 ms (spec 7.3).
// One browser, one fresh context per check. Concurrency is capped and the rest
// queues, because eight at once degrades every one of them.
import { createServer } from 'node:http'
import { chromium } from 'playwright'
import { CHECK_TIMEOUT_MS, hostRewrite, runCheck } from './check-lib.mjs'

const PORT = Number(process.env.SKETCH_CHECKD_PORT || 8010)
const HOST = process.env.SKETCH_CHECKD_HOST || '127.0.0.1'
const CONCURRENCY = Number(process.env.SKETCH_CHECKD_CONCURRENCY || 4)
const TIMEOUT_MS = Number(process.env.SKETCH_CHECKD_TIMEOUT_MS || CHECK_TIMEOUT_MS)
const MAX_BODY = 64 * 1024

// ------------------------------------------------------------ the browsers
// One browser per host rewrite rule. A resolver rule is a launch argument, so
// a second site would need a second browser. In practice there is one.
const browsers = new Map()

async function getBrowser(rule) {
	const key = rule ?? 'none'
	const found = browsers.get(key)
	if (found && found.isConnected()) return found

	const browser = await chromium.launch({ args: rule ? [`--host-resolver-rules=${rule}`] : [] })
	browsers.set(key, browser)
	return browser
}

// ------------------------------------------------------------- the queue
// Past the cap, a check waits. It does not fail and it does not slow the
// checks already running.
let running = 0
const waiting = []

function acquire() {
	if (running < CONCURRENCY) {
		running += 1
		return Promise.resolve()
	}
	return new Promise((resolve) => waiting.push(resolve))
}

function release() {
	const next = waiting.shift()
	if (next) return next()
	running -= 1
}

// ------------------------------------------------------------- the answer
// checkd's own failure is still an answer. The agent gets HTTP 200 and one
// readable error, never a dead socket.
function bootFailed(message) {
	return {
		status: 'boot-failed',
		errors: [{ kind: 'checkd', file: null, line: null, column: null, message }],
		warnings: [],
		consoleErrors: [],
		routes: [],
		skipped: [],
		timings: {},
		screenshots: [],
	}
}

function deadline(promise, ms) {
	let timer = null
	const cap = new Promise((_, reject) => {
		timer = setTimeout(() => reject(new Error(`the check did not finish in ${ms} ms`)), ms)
	})
	return Promise.race([promise, cap]).finally(() => clearTimeout(timer))
}

async function check(request) {
	const { url, rule } = hostRewrite(request.url, request.host)
	const browser = await getBrowser(rule)

	// The hard cap covers the queue wait as well, so a caller blocked on one
	// HTTP call always gets an answer.
	return await deadline(queued(browser, url, !!request.screenshot), TIMEOUT_MS)
}

async function queued(browser, url, screenshot) {
	await acquire()
	try {
		return await runCheck(browser, { url, screenshot, timeoutMs: TIMEOUT_MS })
	} finally {
		release()
	}
}

// --------------------------------------------------------------- the wire
function readBody(req) {
	return new Promise((resolve, reject) => {
		let raw = ''
		req.on('data', (chunk) => {
			raw += chunk
			if (raw.length > MAX_BODY) reject(new Error('the request body is too large'))
		})
		req.on('end', () => resolve(raw))
		req.on('error', reject)
	})
}

function send(res, code, payload) {
	const json = JSON.stringify(payload)
	res.writeHead(code, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(json) })
	res.end(json)
}

// A malformed request is the only 5xx-class answer, and it is a 400.
function parse(raw) {
	let request = null
	try {
		request = JSON.parse(raw || '')
	} catch {
		throw new Error('the request body is not JSON')
	}
	if (!request || typeof request !== 'object') throw new Error('the request body is not an object')
	if (typeof request.url !== 'string' || !request.url) throw new Error('url is required')
	try {
		const parsed = new URL(request.url)
		if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') throw new Error('bad protocol')
	} catch {
		throw new Error(`url is not an http URL: ${request.url}`)
	}
	if (request.host !== undefined && typeof request.host !== 'string')
		throw new Error('host must be a string')

	return request
}

const server = createServer(async (req, res) => {
	if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/check')
		return send(res, 404, { error: 'POST /check is the only route' })

	let request = null
	try {
		request = parse(await readBody(req))
	} catch (e) {
		return send(res, 400, { error: String(e?.message || e) })
	}

	try {
		send(res, 200, await check(request))
	} catch (e) {
		send(res, 200, bootFailed(String(e?.message || e)))
	}
})

for (const signal of ['SIGINT', 'SIGTERM']) {
	process.on(signal, async () => {
		server.close()
		for (const browser of browsers.values()) await browser.close().catch(() => {})
		process.exit(0)
	})
}

server.listen(PORT, HOST, () =>
	console.log(`sketch-checkd on ${HOST}:${PORT}, concurrency ${CONCURRENCY}, timeout ${TIMEOUT_MS} ms`),
)
