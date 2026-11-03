// The frame's half of the Viewer shell (sketch/viewer.py SHELL_FLAG). boot.js imports it in place of the
// toolbar when the payload says `chrome: 'shell'`. It draws nothing and holds no credential: it tells the
// shell what the page is doing (the route, the theme, the viewport) and, in later steps, measures and picks
// for it. Messages go to the parent alone; one from anywhere else, or of a type it does not know, is dropped.
import { watch } from 'vue'
import { envelope, read, toFrame, type FromFrame, type Theme, type ToFrame } from '../shared/protocol'
import { isOurs, pageLayerOpen, routeKey, setSourceFiles, typing } from './dom'
import { startPicking } from './pick'

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

// Same as runtime/annotate/mobileNav.ts: frappe-ui's MobileNav on a phone-width screen.
const PHONE = '(max-width: 767px)'
const NAV = '[data-slot="mobile-nav"]'
// The keys the shell hears from here, with the focus in the page: Escape, and the tool shortcuts.
const SHORTCUTS = ['n', 'c', 't']

let started = false

function post<K extends keyof FromFrame>(type: K, data: FromFrame[K]) {
	// An opaque origin cannot name the shell's origin, and nothing here is secret.
	parent.postMessage(envelope(type, data), '*')
}

const themeNow = (): Theme => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')

// A page dialog is open. The tools step aside for it: it takes Escape first.
const dialogOpen = () => [...document.querySelectorAll('[role="dialog"][data-state="open"]')].some((d) => !isOurs(d))

function layout(): FromFrame['layout'] {
	const nav = window.matchMedia(PHONE).matches ? document.querySelector<HTMLElement>(NAV) : null
	// The Demo pill publishes its height, with its bar's, for whatever floats at the bottom edge (Pills.vue).
	const variantsH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sketch-variants-h')) || 0
	return { vw: window.innerWidth, vh: window.innerHeight, navBottom: nav?.offsetHeight ?? 0, pageLayerOpen: pageLayerOpen(), dialogOpen: dialogOpen(), variantsH }
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

export async function startAgent({ status, routes, router, files, repaint }: AgentStart) {
	if (started || window.parent === window) return
	started = true
	setSourceFiles(files)
	// The Demo's module, which the page shares (same URL, same instance). Only a page that mounted has one to
	// read; a status screen goes without, and so does a Runtime whose module failed to load.
	const variants = router ? await import('sketch:variants').catch(() => null) : null

	let theme = themeNow()
	const picker = startPicking(post, () => (variants && router ? variants.currentPicks(router.currentRoute.value) : []))
	const handlers: { [K in keyof ToFrame]?: (d: ToFrame[K]) => void } = {
		tool: picker.tool,
		selection: picker.selection,
		step: picker.step,
		track: picker.track,
		resolve: picker.resolve,
		scrollTo: picker.scrollTo,
		escape: escapeInPage,
		'picks:apply': ({ picks }) => router && variants?.applyPicks(picks as any, router),
		// The Demo pill rides above the shell's toolbar on a phone when the two would meet (Pills.vue).
		display: (d) => {
			if (!variants) return
			if (d.toolbarLift !== undefined) variants.bridge.toolbarLift = d.toolbarLift
			if (d.toolbarRight !== undefined) variants.bridge.toolbarRight = d.toolbarRight
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
		})
	}
	forwardKeys()

	// The Demo's sets and states, and what each shows, whenever they change: the shell tells from them whether a
	// comment's picks are on show. The canvas opening and closing hides the shell's page tools.
	if (variants) {
		const { bridge, demoEntries } = variants
		watch(() => JSON.stringify(demoEntries()), () => post('demo', { entries: demoEntries() }), { immediate: true })
		watch(
			() => [bridge.open, bridge.phone] as const,
			([open, phone]) => post('canvas', { open, phone, view: String(bridge.view ?? ''), zoom: bridge.zoom, pan: { x: 0, y: 0 }, tiles: [] }),
			{ immediate: true },
		)
	}

	// The Prototype may switch its own theme (a toggle in the page writes data-theme); the shell follows it. The
	// Demo pill's height arrives as a style on the same element.
	new MutationObserver(() => {
		postLayout()
		const next = themeNow()
		if (next === theme) return
		theme = next
		post('theme', { theme })
	}).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'style'] })

	window.addEventListener('resize', postLayout)
	// A page layer opening or closing, or the bottom bar arriving, is a change in the DOM, not in the viewport.
	new MutationObserver(postLayout).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-state'] })
	postLayout()
}
