// Drives the Viewer headless, the way the Frappe renderer drives it in
// production: read the pinned viewer.html, substitute the data slot once, and
// serve the result. Nothing here is part of the Runtime bundle.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

export const VERSION = '1.0.0-beta.55'
export const BASE = `http://localhost:8007/assets/sketch/runtimes/${VERSION}`
export const VIEWER = `${BASE}/viewer.html`

/** The flat { path: source } map for a Prototype directory. */
export function readTree(root) {
	const files = {}
	;(function walk(dir) {
		for (const entry of readdirSync(dir)) {
			const path = join(dir, entry)
			if (statSync(path).isDirectory()) walk(path)
			else files[relative(root, path).split('\\').join('/')] = readFileSync(path, 'utf8')
		}
	})(join(root, 'src'))
	return files
}

/**
 * The renderer's serialiser. Every SFC with a script block ends with
 * `</script>`, which closes the JSON block early, so `<` must be escaped.
 */
export function serialise(payload) {
	return JSON.stringify(payload)
		.replace(/</g, '\\u003c')
		.replace(/>/g, '\\u003e')
		.replace(/&/g, '\\u0026')
}

/** Open the Viewer on one tree and wait for it to report. */
export async function openViewer(context, files, options = {}) {
	const { theme = 'light', meta = {}, timeout = 60000 } = options
	const data = serialise({
		files,
		name: 'harness',
		title: 'Harness',
		slug: 'harness',
		pin: VERSION,
		is_public: false,
		is_owner: true,
		theme,
		...meta,
	})

	const page = await context.newPage()
	await page.route(VIEWER, async (route) => {
		const response = await route.fetch()
		const body = await response.text()
		// One replace, no template engine. A function replacement keeps `$&`
		// in the payload from being read as a back-reference.
		route.fulfill({
			status: 200,
			contentType: 'text/html; charset=utf-8',
			body: body.replace('SKETCH_DATA', () => data),
		})
	})
	await page.goto(VIEWER, { waitUntil: 'commit' })
	await page.waitForFunction(() => window.__sketch, null, { timeout })
	return page
}
