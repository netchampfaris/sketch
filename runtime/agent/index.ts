// The frame's half of the Viewer shell (sketch/viewer.py). boot.js imports it when the payload says
// `chrome: 'shell'`. It draws nothing and holds no credential: it tells the shell what the page is doing (the
// route, the theme, the viewport, the Demo and the canvas), and measures, picks and writes tweaks for it.
// Messages go to the parent alone; one from anywhere else, or of a type it does not know, is dropped.
import { watch } from 'vue'
import { envelope, read, toFrame, type FromFrame, type Theme, type ToFrame } from '../shared/protocol'
import { isOurs, pageLayerOpen, routeKey, setSourceFiles, typing } from './dom'
import { startPicking } from './pick'
import { startTweak } from './tweakPick'
// `sketch:variants` as the Prototype's page loaded it (its types only: the module is the page's, imported at run time).
import type * as VariantsModule from '../variants/index'

type Variants = typeof VariantsModule

type Router = {
	afterEach: (fn: () => void) => void
	currentRoute: { value: { fullPath: string; path: string; query: Record<string, any>; matched: unknown[] } }
	push: (path: string) => Promise<unknown>
	getRoutes: () => { path: string }[]
}
export type AgentStart = {
	status: string
	routes: string[]
	router: Router | null
	// The Prototype's tree, for the component names a pick reports (dom.ts componentOf). Never sent on.
	files: Record<string, string>
	// Repaints boot.js's status screen with the shell's wording for this reader.
	repaint: (hints: ToFrame['copy']) => void
}

// frappe-ui's MobileNav on a phone-width screen.
const PHONE = '(max-width: 767px)'
const NAV = '[data-slot="mobile-nav"]'
// The keys the shell hears from here, with the focus in the page: Escape, and the tool shortcuts.
const SHORTCUTS = ['n', 'c', 't']

let started = false

function post<K extends keyof FromFrame>(type: K, data: FromFrame[K]) {
	// An opaque origin cannot name the shell's origin, and nothing here is secret. Plain data only: what the canvas
	// learned of the pages is partly reactive, which cannot be cloned across.
	parent.postMessage(JSON.parse(JSON.stringify(envelope(type, data))), '*')
}

const themeNow = (): Theme => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')

// A page dialog is open. The tools step aside for it: it takes Escape first.
const dialogOpen = () => [...document.querySelectorAll('[role="dialog"][data-state="open"]')].some((d) => !isOurs(d))

function layout(): FromFrame['layout'] {
	const nav = window.matchMedia(PHONE).matches ? document.querySelector<HTMLElement>(NAV) : null
	return { vw: window.innerWidth, vh: window.innerHeight, navBottom: nav?.offsetHeight ?? 0, pageLayerOpen: pageLayerOpen(), dialogOpen: dialogOpen() }
}

const modsOf = (e: KeyboardEvent) =>
	(['shift', 'alt', 'ctrl', 'meta'] as const).filter((m) => e[`${m}Key` as 'shiftKey'])

// Escape the shell passes on (focus is in the shell's comment box) is dispatched here, and not sent back.
let dispatching = false
function forwardKeys() {
	window.addEventListener(
		'keydown',
		(e) => {
			if (dispatching || e.isComposing) return
			// Heard in the capture phase, before a page layer closes on it: the shell learns what took it.
			if (e.key === 'Escape') return post('key', { key: 'Escape', mods: modsOf(e), layer: dialogOpen() ? 'dialog' : pageLayerOpen() ? 'layer' : '' })
			if (e.metaKey || e.ctrlKey || e.altKey || e.repeat || !SHORTCUTS.includes(e.key.toLowerCase()) || typing(e.target)) return
			post('key', { key: e.key, mods: modsOf(e), layer: '' })
		},
		true,
	)
}
function escapeInPage() {
	dispatching = true
	try {
		const at = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : document.body
		at.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true, cancelable: true }))
	} finally {
		dispatching = false
	}
}

// One layout message per frame at most, and only when something in it moved.
let lastLayout = ''
let layoutQueued = false
function postLayout() {
	if (layoutQueued) return
	layoutQueued = true
	requestAnimationFrame(() => {
		layoutQueued = false
		const now = layout()
		const key = JSON.stringify(now)
		if (key === lastLayout) return
		lastLayout = key
		post('layout', now)
	})
}

// ---- The canvas ------------------------------------------------------------------------------
// The canvas draws its tiles here; the shell draws its panel, its toolbar and the pins on the tiles. A tile clicked with
// a tool in hand is a `tile:pick` (Canvas.vue `activate`), a click off the tiles a `canvas:click`. What the canvas shows
// goes up at most once a frame: the pan and zoom every time, the tiles, pages and Show rows only when they changed.
function startCanvas({ bridge, canvasReport }: Variants) {
	bridge.pick = (hit) => post('tile:pick', { spot: { route: hit.route, tile: hit.tile }, fx: hit.fx, fy: hit.fy, x: hit.x, y: hit.y })
	bridge.onEmptyClick = () => post('canvas:click', {})
	// The live tile's ⋯: the shell opens its menu at the button (runtime/shell/TileMenu.vue).
	bridge.tileMenu = (tileId, rect) => post('tile:menu', { tileId, rect })
	// The phone's title pill: the shell opens its Show list under the name (runtime/shell/CanvasLayer.vue).
	bridge.showMenu = (rect, open) => post('canvas:show', { rect, open })

	const PARTS = ['tiles', 'pages', 'items'] as const
	let sent = { tiles: '', pages: '', items: '' }
	let queued = false
	const send = () => {
		queued = false
		const { tiles, pages, items, ...msg }: FromFrame['canvas'] = canvasReport()
		// Closed, it has nothing to show, and opened again it says everything again.
		if (!msg.open) {
			sent = { tiles: '', pages: '', items: '' }
			return post('canvas', msg)
		}
		const parts = { tiles, pages, items }
		const changed: Pick<FromFrame['canvas'], (typeof PARTS)[number]> = {}
		for (const k of PARTS) {
			if (parts[k] === undefined) continue
			const json = JSON.stringify(parts[k])
			if (json === sent[k]) continue
			sent[k] = json
			Object.assign(changed, { [k]: parts[k] })
		}
		post('canvas', { ...msg, ...changed })
	}
	watch(
		() => [bridge.open, bridge.phone, bridge.view, bridge.zoom, bridge.pan, bridge.corner, bridge.tiles, bridge.model, bridge.items],
		() => {
			if (queued) return
			queued = true
			requestAnimationFrame(send)
		},
		{ immediate: true },
	)
}

export async function startAgent({ status, routes, router, files, repaint }: AgentStart) {
	if (started || window.parent === window) return
	started = true
	setSourceFiles(files)
	// The Demo's module, which the page shares (same URL, same instance). Only a page that mounted has one to
	// read; a status screen goes without, and so does a Runtime whose module failed to load.
	const variants: Variants | null = router ? await import('sketch:variants').catch(() => null) : null

	let theme = themeNow()
	const picker = startPicking(post, () => (variants && router ? variants.currentPicks(router.currentRoute.value) : []))
	// Tweak hears its keys before forwardKeys below sends Escape on: started first, its window listener runs first.
	const tweak = router ? startTweak(post, () => routeKey(router.currentRoute.value)) : null
	const handlers: { [K in keyof ToFrame]?: (d: ToFrame[K]) => void } = {
		tool: (d) => {
			picker.tool(d)
			tweak?.tool(d)
		},
		'tweak:inspect': (d) => void tweak?.inspect(d),
		'tweak:preview': (d) => tweak?.preview(d),
		'tweak:commit': (d) => tweak?.commit(d),
		'tweak:cancel': (d) => tweak?.cancel(d),
		'tweak:props': (d) => tweak?.props(d),
		'tweak:copy': (d) => tweak?.copy(d),
		'tweak:reapply': (d) => tweak?.reapply(d),
		selection: picker.selection,
		step: picker.step,
		track: picker.track,
		resolve: picker.resolve,
		scrollTo: picker.scrollTo,
		escape: escapeInPage,
		'picks:apply': ({ picks }) => router && variants?.applyPicks(picks, router),
		// The shell's Demo pill: an option or a state picked in it, and a fresh look at where the rows sit.
		'state:set': ({ id, value }) => router && variants?.setDemo(id, value, router),
		'model:measure': () => router && variants?.measureDemo(router.currentRoute.value),
		'tile:open': ({ tileId }) => variants?.bridge.openTile?.(tileId),
		// The canvas fits its tiles in the room the shell's panel leaves. The options new to this reader get their "New"
		// badge. The tile whose action the shell saves spins, the one whose menu is open looks pressed, and the option a
		// write landed on is ringed once drawn.
		display: (d) => {
			if (!variants) return
			if (d.reserve !== undefined) variants.bridge.shellReserve = Math.max(0, d.reserve)
			for (const o of d.newOptions ?? []) variants.badges.fresh[o] = true
			if (d.busyTile !== undefined) variants.bridge.busyTile = d.busyTile
			if (d.menuTile !== undefined) variants.bridge.menuTile = d.menuTile
			if (d.landed && variants.landed) variants.landed.value = d.landed
			if (d.showOpen !== undefined) variants.bridge.showOpen = d.showOpen
		},
		'canvas:open': ({ view }) => {
			if (!router || !variants) return
			const id = view || 'page:' + router.currentRoute.value.path
			// Open, it shows another view in place (as the panel's rows do); closed, it opens on top of the page, so Back leaves it.
			if (variants.bridge.open) router.replace({ query: { ...router.currentRoute.value.query, canvas: id } }).catch(() => {})
			else variants.openCanvas(router, id)
		},
		'canvas:close': () => router && variants?.bridge.open && variants.closeCanvas(router),
		'canvas:tool': ({ tool }) => variants && (variants.bridge.tool = tool),
		'canvas:reveal': async ({ req, spot, fx, fy }) => {
			const point = (await variants?.bridge.reveal?.(spot, { fx, fy }).catch(() => null)) ?? null
			post('canvas:revealed', { req, point })
		},
		theme: ({ theme: next }) => {
			theme = next
			document.documentElement.dataset.theme = next
		},
		copy: (hints) => repaint(hints),
		nav: ({ path }) => {
			if (router && path !== router.currentRoute.value.fullPath) router.push(path).catch(() => {})
		},
	}
	window.addEventListener('message', (e) => {
		if (e.source !== window.parent) return
		const msg = read<ToFrame>(e.data, toFrame)
		if (!msg) return
		;(handlers[msg.type] as ((d: unknown) => void) | undefined)?.(msg.data)
	})

	const pages = router && variants ? router.getRoutes().map((r) => ({ path: r.path, title: variants.titleOfRoute(r) })) : []
	post('ready', { status, routes, pages })
	post('theme', { theme })

	if (router) {
		const postRoute = () => {
			const r = router.currentRoute.value
			post('route', { fullPath: r.fullPath, path: r.path, key: routeKey(r) })
		}
		postRoute()
		router.afterEach(() => {
			postRoute()
			postLayout()
			picker.routed()
			tweak?.routed(routeKey(router.currentRoute.value))
		})
	}
	forwardKeys()

	// The Demo's sets and states, and what each shows, whenever they change: the shell tells from them whether a
	// comment's picks are on show. The canvas, for the shell's panel and the pins it draws on the tiles.
	if (variants) {
		const { demoEntries } = variants
		watch(() => JSON.stringify(demoEntries()), () => post('demo', { entries: demoEntries() }), { immediate: true })
		// The Demo pill's rows, which the shell draws.
		if (router) watch(() => JSON.stringify(variants.demoModel(router)), (json) => post('model', JSON.parse(json)), { immediate: true })
		startCanvas(variants)
	}

	// The Prototype may switch its own theme (a toggle in the page writes data-theme); the shell follows it.
	new MutationObserver(() => {
		const next = themeNow()
		if (next === theme) return
		theme = next
		post('theme', { theme })
	}).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

	window.addEventListener('resize', postLayout)
	// A page layer opening or closing, or the bottom bar arriving, is a change in the DOM, not in the viewport.
	new MutationObserver(postLayout).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-state'] })
	postLayout()
}
