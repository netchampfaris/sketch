// Picking, for the Viewer shell's Note and Comment tools. The shell draws the outline, the box, the pins and
// the comment box; the page and its elements are here, in the frame, so the pointer is caught here. While a tool
// picks, every pointer event aimed at the page is swallowed before the app sees it (as the in-frame toolbar did),
// so a page's open menu or popover stays open, and an item inside one can be picked.
//
// What goes to the shell is geometry and words about elements: a rect, a selector, a component name. An element
// picked this visit gets a `ref`, so the shell can name the same element again (the box's selection, a step to its
// parent, a pin's place) while it lives; once it is gone, the selector stands in.
import {
	analyzeBox,
	childOf,
	clamp,
	componentOf,
	fracRect,
	infoOf,
	isOurs,
	labelOf,
	listen,
	parentOf,
	redlines,
	resolve,
	tagOf,
	targetOf,
	type Redline,
} from './dom'
import type { BoxInfo, FromFrame, Pick, Rect, ToFrame } from '../shared/protocol'
import type { DemoPick } from '../shared/picks'

type Post = <K extends keyof FromFrame>(type: K, data: FromFrame[K]) => void

const toRect = (r: DOMRect): Rect => ({ x: r.left, y: r.top, w: r.width, h: r.height })
const centreOf = (el: Element) => {
	const r = el.getBoundingClientRect()
	return { x: clamp(r.left + r.width / 2, 8, innerWidth - 8), y: clamp(r.top + r.height / 2, 8, innerHeight - 8) }
}

// `picksNow` is what the Demo shows on this page now (sketch:variants currentPicks), or nothing without a Demo.
export function startPicking(post: Post, picksNow: () => DemoPick[]) {
	// ---- Refs: elements picked this visit, by a name the shell can hand back -----------------------
	const byRef = new Map<string, WeakRef<Element>>()
	const refs = new WeakMap<Element, string>()
	let next = 0
	function refOf(el: Element): string {
		let r = refs.get(el)
		if (!r) {
			r = `e${++next}`
			refs.set(el, r)
			byRef.set(r, new WeakRef(el))
		}
		return r
	}
	const elOf = (ref: string | undefined) => {
		const el = ref ? byRef.get(ref)?.deref() : undefined
		return el?.isConnected ? el : null
	}

	function pickOf(el: Element, kind: Pick['kind'], x: number, y: number, more: { shift?: boolean; keyboard?: boolean; box?: BoxInfo } = {}): Pick {
		const c = componentOf(el)
		return {
			kind,
			ref: refOf(el),
			el: infoOf(el),
			label: labelOf(el),
			component: { component: c.component, chain: c.chain, file: c.file ?? '' },
			rect: toRect(el.getBoundingClientRect()),
			x,
			y,
			shift: !!more.shift,
			keyboard: !!more.keyboard,
			// On the live page a thread also keeps what the Demo shows, so it can be put back that way.
			picks: picksNow(),
			...(more.box ? { box: more.box } : {}),
		}
	}

	// ---- What the shell said --------------------------------------------------------------------
	let picking = false
	let selection: Element[] = []
	let selectionBox: BoxInfo | undefined
	let hoverEl: Element | null = null
	let alt = false
	let shift = false

	// ---- Hover: the element under the pointer, and with Alt the distances in px ------------------
	let lastHover = ''
	function postHover() {
		const he = picking && hoverEl?.isConnected ? hoverEl : null
		let lines: Redline[] = []
		if (he && alt) {
			// Against the selection when there is one, else the hovered element against its parent.
			const sel = selection.find((e) => e.isConnected)
			if (sel) {
				const r = sel.getBoundingClientRect()
				const s = selectionBox ? fracRect(r, selectionBox) : toRect(r)
				if (!selection.includes(he)) lines = redlines(new DOMRect(s.x, s.y, s.w, s.h), he.getBoundingClientRect())
			} else {
				const p = parentOf(he)
				if (p) lines = redlines(p.getBoundingClientRect(), he.getBoundingClientRect())
			}
		}
		const data: FromFrame['hover'] = he
			? { rect: toRect(he.getBoundingClientRect()), label: tagOf(he), lines, alt, shift }
			: { rect: null, label: '', lines: [], alt, shift }
		const key = JSON.stringify(data)
		if (key === lastHover) return
		lastHover = key
		post('hover', data)
	}
	function setHover(el: Element | null) {
		if (el === hoverEl) return
		hoverEl = el
		postHover()
	}

	// ---- The pointer, while a tool picks --------------------------------------------------------
	const stop = (e: Event) => {
		e.stopPropagation()
		e.stopImmediatePropagation()
	}
	let down: { x: number; y: number } | null = null
	let dragging = false
	let skipClick = false
	function resetDrag() {
		if (dragging) post('drag', { rect: null })
		down = null
		dragging = false
	}

	function onDown(e: MouseEvent) {
		if (!targetOf(e)) return
		// No default: no text selection, and shift-click can't extend one.
		e.preventDefault()
		stop(e)
		skipClick = false
		if (e.button === 0) down = { x: e.clientX, y: e.clientY }
	}

	function onMove(e: PointerEvent) {
		const keysMoved = alt !== e.altKey || shift !== e.shiftKey
		alt = e.altKey
		shift = e.shiftKey
		if (down && e.buttons === 0) resetDrag() // the button was released outside the window
		if (down) {
			if (!dragging && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) {
				dragging = true
				setHover(null)
			}
			if (dragging) {
				post('drag', { rect: { x: Math.min(down.x, e.clientX), y: Math.min(down.y, e.clientY), w: Math.abs(e.clientX - down.x), h: Math.abs(e.clientY - down.y) } })
				return
			}
		}
		const el = targetOf(e)
		// Over the page's chrome of ours (the Demo pill, a toast) there is nothing to outline.
		if (!el) return setHover(null)
		if (el === document.body || el === document.documentElement) return keysMoved && postHover()
		if (el !== hoverEl) setHover(el)
		else if (keysMoved) postHover()
	}

	function onUp(e: MouseEvent) {
		if (!down) return
		const was = dragging
		const start = down
		resetDrag()
		if (!was) return
		e.preventDefault()
		stop(e)
		skipClick = true // the click that follows a drag is not a pick
		const b = { x: Math.min(start.x, e.clientX), y: Math.min(start.y, e.clientY), w: Math.abs(e.clientX - start.x), h: Math.abs(e.clientY - start.y) }
		const { container, ...info } = analyzeBox(b)
		const c = container.getBoundingClientRect()
		const box: BoxInfo = { ...info, fx: (b.x - c.left) / (c.width || 1), fy: (b.y - c.top) / (c.height || 1), fw: b.w / (c.width || 1), fh: b.h / (c.height || 1) }
		post('pick', pickOf(container, 'box', clamp(b.x + b.w, 8, innerWidth - 8), clamp(b.y + b.h, 8, innerHeight - 8), { box }))
	}

	function onClick(e: MouseEvent) {
		const el = targetOf(e)
		if (!el) return
		e.preventDefault()
		stop(e)
		if (skipClick) {
			skipClick = false
			return
		}
		// A keyboard activation (Enter on a focused element) has no pointer: aim at the element's centre.
		const keyboard = e.detail === 0
		const at = keyboard ? centreOf(el) : { x: e.clientX, y: e.clientY }
		post('pick', pickOf(el, 'click', at.x, at.y, { shift: e.shiftKey, keyboard }))
	}

	// Everything else is the tool's alone: the app must not see it.
	function swallow(e: Event) {
		if (targetOf(e)) stop(e)
	}

	let off: (() => void) | null = null
	function setPicking(on: boolean) {
		if (on === picking) return
		picking = on
		off?.()
		off = null
		resetDrag()
		alt = shift = false
		if (on)
			off = listen([
				['pointermove', onMove],
				['mousedown', onDown],
				['mouseup', onUp],
				['click', onClick],
				['pointerdown', swallow],
				['pointerup', swallow],
				['dblclick', swallow],
				['contextmenu', swallow],
				['auxclick', swallow],
			])
		else setHover(null)
		document.body.style.cursor = on ? 'crosshair' : ''
	}

	// Leaving the frame (for the shell's toolbar, a pin, the comment box) leaves no hover behind.
	document.documentElement.addEventListener('mouseleave', () => picking && setHover(null))
	window.addEventListener('blur', () => {
		alt = shift = false
		resetDrag()
		postHover()
	})
	const onKeys = (e: KeyboardEvent) => {
		if (alt === e.altKey && shift === e.shiftKey) return
		alt = e.altKey
		shift = e.shiftKey
		if (picking) postHover()
	}
	window.addEventListener('keydown', onKeys, true)
	window.addEventListener('keyup', onKeys, true)

	// ---- Tracking: the rects of what the shell draws on, kept fresh ------------------------------
	let tracked: ToFrame['track'] = { map: {}, refs: {} }
	let lastTrack = ''
	const labels = new WeakMap<Element, string>()
	function measure() {
		const map: Record<string, Rect | null> = {}
		const named: Record<string, string> = {}
		for (const [id, sel] of Object.entries(tracked.map)) {
			const el = elOf(tracked.refs[id]) ?? resolve(sel)
			map[id] = el ? toRect(el.getBoundingClientRect()) : null
			if (el) {
				let l = labels.get(el)
				if (l === undefined) labels.set(el, (l = tagOf(el)))
				named[id] = l
			}
		}
		const key = JSON.stringify(map)
		if (key !== lastTrack) {
			lastTrack = key
			post('track', { map, labels: named })
		}
		if (picking && hoverEl) postHover()
	}
	let raf = 0
	const schedule = () => {
		if (!raf)
			raf = requestAnimationFrame(() => {
				raf = 0
				measure()
			})
	}
	// Scroll doesn't bubble, so listen in the capture phase to catch the app's inner scrollers.
	window.addEventListener('scroll', schedule, { capture: true, passive: true })
	window.addEventListener('resize', schedule)
	let wait = 0
	new MutationObserver((list) => {
		if (list.every((m) => isOurs(m.target)) || wait) return
		wait = window.setTimeout(() => {
			wait = 0
			schedule()
		}, 120)
	}).observe(document.body, { childList: true, subtree: true })

	return {
		tool(d: ToFrame['tool']) {
			setPicking(d.active && (d.mode === 'note' || d.mode === 'comment'))
		},
		selection(d: ToFrame['selection']) {
			selection = d.refs.map(elOf).filter((e): e is Element => !!e)
			selectionBox = d.box
			if (picking && alt) postHover()
		},
		step(d: ToFrame['step']) {
			const el = elOf(d.ref)
			const to = el && (d.dir === 'parent' ? parentOf(el) : childOf(el))
			if (!to) return
			const p = centreOf(to)
			post('pick', pickOf(to, 'step', p.x, p.y))
		},
		track(d: ToFrame['track']) {
			tracked = d
			lastTrack = ''
			measure()
		},
		resolve(d: ToFrame['resolve']) {
			const map: Record<string, Rect | null> = {}
			for (const sel of d.selectors) {
				const el = resolve(sel)
				map[sel] = el ? toRect(el.getBoundingClientRect()) : null
			}
			post('rects', { req: d.req, map })
		},
		scrollTo(d: ToFrame['scrollTo']) {
			resolve(d.selector)?.scrollIntoView({ block: 'center', behavior: d.smooth ? 'smooth' : 'auto' })
		},
		routed: schedule,
	}
}
