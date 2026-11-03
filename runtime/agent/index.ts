// The frame's half of the Viewer shell (sketch/viewer.py SHELL_FLAG). boot.js imports it in place of the
// toolbar when the payload says `chrome: 'shell'`. It draws nothing and holds no credential: it tells the
// shell what the page is doing (the route, the theme, the viewport) and, in later steps, measures and picks
// for it. Messages go to the parent alone; one from anywhere else, or of a type it does not know, is dropped.
import { envelope, read, toFrame, type FromFrame, type Theme, type ToFrame } from '../shared/protocol'

type Router = {
	afterEach: (fn: () => void) => void
	currentRoute: { value: { fullPath: string } }
	push: (path: string) => Promise<unknown>
}
export type AgentStart = {
	status: string
	routes: string[]
	router: Router | null
	// Repaints boot.js's status screen with the shell's wording for this reader.
	repaint: (hints: ToFrame['copy']) => void
}

// Same as runtime/annotate/mobileNav.ts: frappe-ui's MobileNav on a phone-width screen.
const PHONE = '(max-width: 767px)'
const NAV = '[data-slot="mobile-nav"]'
// A page menu, popover, list or dialog is open (reka marks each one), as annotate.ts pageLayerOpen reads it.
const LAYER = '[data-dismissable-layer]'

let started = false

function post<K extends keyof FromFrame>(type: K, data: FromFrame[K]) {
	// An opaque origin cannot name the shell's origin, and nothing here is secret.
	parent.postMessage(envelope(type, data), '*')
}

const themeNow = (): Theme => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')

function layout(): FromFrame['layout'] {
	const nav = window.matchMedia(PHONE).matches ? document.querySelector<HTMLElement>(NAV) : null
	const pageLayerOpen = [...document.querySelectorAll(LAYER)].some((l) => !l.querySelector('[role="tooltip"]'))
	return { vw: window.innerWidth, vh: window.innerHeight, navBottom: nav?.offsetHeight ?? 0, pageLayerOpen }
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

export function startAgent({ status, routes, router, repaint }: AgentStart) {
	if (started || window.parent === window) return
	started = true

	let theme = themeNow()
	const handlers: { [K in keyof ToFrame]?: (d: ToFrame[K]) => void } = {
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

	post('ready', { status, routes })
	post('theme', { theme })

	if (router) {
		post('route', { fullPath: router.currentRoute.value.fullPath })
		router.afterEach(() => {
			post('route', { fullPath: router.currentRoute.value.fullPath })
			postLayout()
		})
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
