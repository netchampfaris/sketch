// One check run. Open the Viewer, read what the Runtime already reports, walk
// the routes, screenshot each static one. There is no second compiler here:
// the page is the only source of truth (spec 7.1).

// The walk is capped, and the whole check is capped. A silent cap reads as
// "everything is fine", so every route the walk leaves out goes into `skipped`
// with a reason (trap 12).
export const MAX_ROUTES = 20
export const CHECK_TIMEOUT_MS = 30000
export const VIEWPORT = { width: 1280, height: 800 }

// A route with a parameter or a catch-all cannot be visited blind.
const isStatic = (path) => !path.includes(':') && !path.includes('*')

const REASON_PARAM = 'route takes a parameter, so it cannot be visited blind'
const REASON_WILDCARD = 'route is a catch-all pattern, so it cannot be visited blind'
const REASON_CAP = `the route walk is capped at ${MAX_ROUTES} routes`
const REASON_DEADLINE = 'the check ran out of time before this route'

/**
 * Rewrite the URL so the browser sends the site as the HTTP Host header.
 *
 * The caller sends `http://127.0.0.1:8007/...` plus `host: "sketch.localhost"`
 * (Contract 5). Chromium refuses a Host header set through extraHTTPHeaders,
 * so the hostname goes into the URL and a host-resolver rule points it back at
 * the same address. The public hostname is never used: it routes every request
 * out to Cloudflare and back (trap 14).
 *
 * Returns the URL to open and the resolver rule the browser needs.
 */
export function hostRewrite(rawUrl, host) {
	const url = new URL(rawUrl)
	if (!host || host === url.hostname) return { url: url.toString(), rule: null, address: url.hostname }

	const address = url.hostname
	url.hostname = host
	return { url: url.toString(), rule: `MAP ${host} ${address}`, address }
}

/**
 * Run one check against one browser.
 *
 * `browser` must already carry the host-resolver rule for this URL.
 * Returns the Contract 5 body, always with `skipped` present.
 */
export async function runCheck(browser, { url, screenshot = false, timeoutMs = CHECK_TIMEOUT_MS } = {}) {
	const start = Date.now()
	const deadline = start + timeoutMs
	const left = () => Math.max(500, deadline - Date.now())

	const context = await browser.newContext({
		viewport: VIEWPORT,
		// check forces light, so its screenshots stay deterministic (spec 12).
		colorScheme: 'light',
	})
	const contextReady = Date.now()

	try {
		const page = await context.newPage()
		await page.goto(url, { waitUntil: 'commit', timeout: left() })
		await page.waitForFunction(() => window.__sketch, null, { timeout: left() })
		const reported = Date.now()

		const first = await page.evaluate(() => window.__sketch)
		const routes = first.routes ?? []

		// A tree that does not compile, link or boot never mounts. Nothing to
		// walk, and the report is already final.
		if (['compile-failed', 'link-failed', 'boot-failed', 'empty'].includes(first.status)) {
			return body(first, {
				routes,
				skipped: [],
				screenshots: [],
				wall: { start, contextReady, reported, walked: reported, done: Date.now() },
			})
		}

		const skipped = []
		const screenshots = []
		let walked = 0

		for (const path of routes) {
			if (!isStatic(path)) {
				skipped.push({ route: path, reason: path.includes(':') ? REASON_PARAM : REASON_WILDCARD })
				continue
			}
			if (walked >= MAX_ROUTES) {
				skipped.push({ route: path, reason: REASON_CAP })
				continue
			}
			if (Date.now() >= deadline) {
				skipped.push({ route: path, reason: REASON_DEADLINE })
				continue
			}

			// Drive the router directly. Never through the DOM (spec 7.4).
			await page.evaluate((p) => window.__sketchGoto(p), path)
			walked += 1
			if (screenshot) {
				const png = await page.screenshot({ type: 'png', timeout: left() })
				screenshots.push({ route: path, png_base64: png.toString('base64') })
			}
		}
		const walkedAt = Date.now()

		const final = await page.evaluate(() => window.__sketch)
		return body(final, {
			routes,
			skipped,
			screenshots,
			wall: { start, contextReady, reported, walked: walkedAt, done: Date.now() },
		})
	} finally {
		await context.close()
	}
}

/**
 * The Contract 5 body.
 *
 * The Runtime fixes its status at mount time. A route reached only during the
 * walk can throw, and that status would still read "ok". Recompute it (trap
 * 13).
 */
function body(report, { routes, skipped, screenshots, wall }) {
	const errors = (report.errors ?? []).map(error)
	const consoleErrors = report.consoleErrors ?? []
	let status = report.status
	if (status === 'ok' && (errors.length || consoleErrors.length)) status = 'errors'

	return {
		status,
		errors,
		warnings: (report.warnings ?? []).map(warning),
		consoleErrors,
		routes,
		skipped,
		timings: { ...(report.timings ?? {}), ...timings(wall) },
		screenshots,
	}
}

// Errors read as `file:line:col message`, so every entry carries the same keys.
function error(entry) {
	const info = entry.info ? ` (${entry.info})` : ''
	return {
		kind: entry.kind ?? 'runtime',
		file: entry.file ?? null,
		line: entry.line ?? null,
		column: entry.column ?? null,
		message: `${entry.message ?? ''}${info}`,
	}
}

function warning(entry) {
	return { kind: entry.kind ?? 'warning', file: entry.file ?? null, message: entry.message ?? '' }
}

function timings(wall) {
	return {
		contextMs: wall.contextReady - wall.start,
		loadMs: wall.reported - wall.contextReady,
		walkMs: wall.walked - wall.reported,
		checkMs: wall.done - wall.start,
	}
}
