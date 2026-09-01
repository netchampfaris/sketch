// One check run. Open the Viewer, read what the Runtime already reports, walk
// the routes, screenshot each static one, and take the card images. There is no
// second compiler here: the page is the only source of truth (spec 7.1).

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

// The report names the origins it refused, not every URL. One page can ask for
// a hundred pictures from one CDN, and the reader needs the origin once.
export const MAX_BLOCKED_ORIGINS = 20

/** A fresh count of what the filter refused. One per check run. */
export function newRefusals(allowed) {
	return { allowed, origins: [], total: 0 }
}

/** Record one refused request under its origin. */
function refuse(refused, target, kind) {
	refused.total += 1

	let origin = target
	try {
		origin = new URL(target).origin
	} catch {
		// A target this filter cannot parse is still worth naming as it stands.
	}

	const found = refused.origins.find((entry) => entry.origin === origin)
	if (found) {
		found.count += 1
		if (!found.kinds.includes(kind)) found.kinds.push(kind)
		return
	}
	// Past the cap the count still grows, so the summary line stays honest.
	if (refused.origins.length < MAX_BLOCKED_ORIGINS) {
		refused.origins.push({ origin, count: 1, kinds: [kind] })
	}
}

/** The origin a WebSocket URL belongs to, as an HTTP origin. */
function socketOrigin(target) {
	const url = new URL(target)
	url.protocol = url.protocol === 'wss:' ? 'https:' : 'http:'
	return url.origin
}

/**
 * Let a context reach the origin under test and nothing else.
 *
 * A Prototype is JavaScript one user wrote, and the check runs it in a browser
 * on the server. Without this, an `onMounted` fetch reaches a neighbouring
 * bench on loopback or the cloud metadata address, and an iframe of any
 * frameable internal page lands in the screenshot the attacker reads back.
 *
 * An origin match is the whole allowlist. The Viewer document loads its
 * stylesheets, its import map and boot.js from `/assets` on the same origin,
 * and it fetches nothing else. `data:` and `blob:` never leave the browser.
 *
 * A WebSocket needs its own rule. Playwright keeps handshakes off the
 * `context.route` list, so the filter above never sees them and a
 * `new WebSocket('ws://127.0.0.1:8000/')` reaches the neighbouring bench.
 * `context.routeWebSocket` is the list that does see them (Playwright 1.62).
 * The matcher returns false for the origin under test, so an allowed socket is
 * never intercepted and connects as it always did. A matched socket has no
 * `connectToServer` call, so Playwright never opens the server side: the
 * handshake does not leave the browser.
 *
 * Returns the count of what it refused. `egressWarnings` turns it into report
 * lines, because a silent abort renders as an empty picture with no reason.
 *
 * Exported for `sketch/tests/checkd_egress.mjs`, which drives it in a browser.
 */
export async function restrictEgress(context, url, refused = null) {
	const allowed = new URL(url).origin
	const log = refused ?? newRefusals(allowed)

	await context.route('**/*', (route) => {
		const target = route.request().url()
		if (target.startsWith('data:') || target.startsWith('blob:')) return route.continue()
		if (new URL(target).origin === allowed) return route.continue()
		refuse(log, target, route.request().resourceType())
		// The page console reads this as `net::ERR_BLOCKED_BY_CLIENT`.
		return route.abort('blockedbyclient')
	})

	await context.routeWebSocket(
		(target) => socketOrigin(target) !== allowed,
		(socket) => {
			// Under the HTTP origin, so one host is one line in the report.
			refuse(log, socketOrigin(socket.url()), 'websocket')
			// 1008 is "policy violation". The page reads the code and the reason.
			socket.close({ code: 1008, reason: 'the check browser reaches this Prototype only' })
		},
	)

	return log
}

/**
 * What the filter refused, as report warnings.
 *
 * Warnings and not errors. The block is this service's policy, not a defect in
 * the Prototype: a recipe that loads a picture from a CDN is correct code, and
 * `body` below turns a non-empty `errors` list into status `errors`. A silent
 * abort is the real failure here. The picture renders at zero width, and
 * `errors` and `consoleErrors` are both empty, so the agent reads a broken
 * screenshot with no reason for it.
 *
 * `warnings` is the advisory list the report already has, and
 * `mcp/tools.py check_text` prints every entry, so the agent sees this in the
 * text as well as in the structured answer. `file` carries the origin, which
 * is where the block happened.
 */
export function egressWarnings(refused) {
	if (!refused || !refused.total) return []

	const warnings = refused.origins.map((entry) => ({
		kind: 'egress-blocked',
		file: entry.origin,
		message:
			`the check browser refused ${entry.count} request(s) (${entry.kinds.join(', ')}). ` +
			`It runs on the server, so it reaches ${refused.allowed} only. ` +
			'A refused picture or font is empty in the screenshot, and a refused ' +
			'socket never opens. Inline the asset, or use a data URL, to see it here.',
	}))

	const named = refused.origins.reduce((sum, entry) => sum + entry.count, 0)
	if (refused.total > named) {
		warnings.push({
			kind: 'egress-blocked',
			file: null,
			message: `${refused.total - named} more request(s) to other origins were refused.`,
		})
	}

	return warnings
}

/**
 * The URL of the same Viewer in another theme.
 *
 * The Viewer reads `theme` from the URL before it reads anything else
 * (spec 12), so one parameter is the whole switch. Every other parameter is
 * kept, including the signature: `theme` sits outside it (spec 7.3).
 */
export function themed(rawUrl, theme) {
	const url = new URL(rawUrl)
	url.searchParams.set('theme', theme)
	return url.toString()
}

/**
 * Run one check against one browser.
 *
 * `browser` must already carry the host-resolver rule for this URL.
 * Returns the Contract 5 body, always with `skipped` present.
 *
 * `screenshot` is the agent's option: one light PNG per static route, the
 * shape spec 7.4 fixes. `thumbnails` is a different job with a different
 * reader. It takes the home route only, once per theme, for the gallery card
 * and the feed card. Both are opt-in and neither implies the other.
 */
export async function runCheck(
	browser,
	{ url, screenshot = false, thumbnails = false, timeoutMs = CHECK_TIMEOUT_MS } = {},
) {
	const start = Date.now()
	const deadline = start + timeoutMs
	const left = () => Math.max(500, deadline - Date.now())

	const context = await browser.newContext({
		viewport: VIEWPORT,
		// check forces light, so its screenshots stay deterministic (spec 12).
		colorScheme: 'light',
	})
	const refused = await restrictEgress(context, url)
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
				thumbnails: [],
				refused,
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

		// The card images. After the walk, so a thumbnail can never change what
		// the walk reported, and never on the failed-status path above: a tree
		// that did not mount has no picture to take.
		const shots = thumbnails ? await takeThumbnails(browser, page, url, routes, left, refused) : []

		const final = await page.evaluate(() => window.__sketch)
		return body(final, {
			routes,
			skipped,
			screenshots,
			thumbnails: shots,
			refused,
			wall: { start, contextReady, reported, walked: walkedAt, done: Date.now() },
		})
	} finally {
		await context.close()
	}
}

/**
 * One PNG per theme of the home route.
 *
 * The home route, not every route: this is the picture on a card, and a card
 * shows the page a visitor lands on. It is the first static route, which is
 * `/` for every recipe and for every router that names a root.
 *
 * Light reuses the page the walk already has open, so it costs one navigation.
 * Dark cannot: the Viewer resolves the theme once, at boot (spec 12), and
 * Playwright fixes `colorScheme` when the context is made. So dark is a second
 * context and a second load, and it is the whole added cost of this pass.
 *
 * A failure here returns fewer images and never throws. The check is the
 * agent's answer about their code; a missing card image is not their bug, and
 * it must not turn a passing check into a failing one.
 */
async function takeThumbnails(browser, page, url, routes, left, refused) {
	const home = routes.find(isStatic)
	if (!home) return []

	const shots = []

	try {
		await page.evaluate((p) => window.__sketchGoto(p), home)
		const png = await page.screenshot({ type: 'png', timeout: left() })
		shots.push({ theme: 'light', route: home, png_base64: png.toString('base64') })
	} catch {
		// Nothing to add: the caller reads the list, not a reason.
	}

	let dark = null
	try {
		dark = await browser.newContext({ viewport: VIEWPORT, colorScheme: 'dark' })
		// A second context is a second egress hole. It loads the same Prototype,
		// so it counts into the same refusals and the report names them once.
		await restrictEgress(dark, url, refused)
		const darkPage = await dark.newPage()
		await darkPage.goto(themed(url, 'dark'), { waitUntil: 'commit', timeout: left() })
		await darkPage.waitForFunction(() => window.__sketch, null, { timeout: left() })
		await darkPage.evaluate((p) => window.__sketchGoto(p), home)
		const png = await darkPage.screenshot({ type: 'png', timeout: left() })
		shots.push({ theme: 'dark', route: home, png_base64: png.toString('base64') })
	} catch {
		// Same. A card falls back to its light image.
	} finally {
		if (dark) await dark.close().catch(() => {})
	}

	return shots
}

/**
 * The Contract 5 body.
 *
 * The Runtime fixes its status at mount time. A route reached only during the
 * walk can throw, and that status would still read "ok". Recompute it (trap
 * 13).
 */
function body(report, { routes, skipped, screenshots, thumbnails = [], refused = null, wall }) {
	const errors = (report.errors ?? []).map(error)
	const consoleErrors = report.consoleErrors ?? []
	let status = report.status
	if (status === 'ok' && (errors.length || consoleErrors.length)) status = 'errors'

	return {
		status,
		errors,
		// The egress lines go last, so the Prototype's own warnings read first.
		warnings: [...(report.warnings ?? []).map(warning), ...egressWarnings(refused)],
		consoleErrors,
		routes,
		skipped,
		timings: { ...(report.timings ?? {}), ...timings(wall) },
		screenshots,
		thumbnails,
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
