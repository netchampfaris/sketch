// Tweak's picking, in the Viewer shell's frame: the frame half of runtime/shell/TweakLayer.vue. While Tweak is the
// tool, the pointer is caught here (the page's elements are here): a click selects, Shift-click adds or takes out, \ and
// Enter step to the parent and child, Space held peeks, Escape lets go. What the shell needs to draw (the outlines and
// their rects, the facts its panel shows) is sent up; what the shell's panel changes comes back as class, prop and copy
// writes (tweakDom.ts). The frame draws nothing and saves nothing.
import { childOf, isOurs, listen, parentOf, targetOf, typing } from './dom'
import { elOf, refOf } from './refs'
import {
	alikeOf,
	alikeSet,
	elsOfTweaks,
	factsOf,
	frappeOf,
	kindOf,
	nameOf,
	openerOf,
	probeTokens,
	reapply,
	retarget,
	setPreviewing,
	setRoute,
	setTweaks,
	stackCounts,
	startSync,
	writeCopyAt,
	writeDom,
	writeProp,
} from './tweakDom'
import { resolve } from './dom'
import type { FromFrame, Rect, ToFrame, TweakInfo } from '../shared/protocol'

type Post = <K extends keyof FromFrame>(type: K, data: FromFrame[K]) => void

const rectOf = (el: Element | null): Rect | null => {
	if (!el) return null
	const r = el.getBoundingClientRect()
	return { x: r.left, y: r.top, w: r.width, h: r.height }
}

export function startTweak(post: Post, routeNow: () => string) {
	let live = false
	let toolActive = false
	// The selection is ordered; the last pick is the one the shell's popover sits under.
	let sels: Element[] = []
	let hover: Element | null = null
	// The elements whose row is hovered in the shell's tweak list.
	let hls: Element[] = []
	// Copies of the selection (same maker, tag, mostly the same classes) and of the Shift-hovered element.
	let alike: { copies: Element[]; total: number } = { copies: [], total: 0 }
	let hoverAlike: Element[] = []
	let hoverName = ''
	let shift = false
	let peek = false
	// Where on the element the click landed, as fractions: a very tall element puts the popover there.
	let anchor: { fx: number; fy: number } | null = null

	// ---- Facts for the shell ---------------------------------------------------------------------
	// Copies that can join the selection: the same kind, and the component itself, not a part of it.
	let joinableCache: Element[] | null = null
	function joinable(): Element[] {
		if (joinableCache) return joinableCache
		const first = sels[0]
		if (!first) return (joinableCache = [])
		const kind = kindOf(first)
		return (joinableCache = alike.copies.filter((c) => {
			if (!c.isConnected) return false
			const f = frappeOf(c)
			const root = f?.rootEl && f.rootEl !== c && f.rootEl.isConnected ? f.rootEl : c
			return root === c && (f?.name ?? '') === kind
		}))
	}
	function info(req = ''): TweakInfo {
		return {
			req,
			sels: sels.filter((e) => e.isConnected).map((e) => factsOf(e, refOf(e))),
			total: alike.total,
			joinable: joinable().length,
			anchor,
		}
	}
	const send = (req = '') => post('tweak:info', info(req))
	// After a write the panel reads the page again, once.
	let refreshQueued = false
	function refreshSoon() {
		if (refreshQueued || !sels.length) return
		refreshQueued = true
		requestAnimationFrame(() => {
			refreshQueued = false
			if (sels.length) send()
		})
	}
	let tokensSent = false
	function sendTokens() {
		if (tokensSent) return
		tokensSent = true
		void probeTokens().then((t) => t && post('tweak:info', { req: '', tokens: t as unknown as Record<string, string[]> }))
	}
	let lastStacks = ''
	function sendStacks() {
		const stacks = stackCounts()
		const key = JSON.stringify(stacks)
		if (key === lastStacks) return
		lastStacks = key
		post('tweak:info', { req: '', stacks })
	}

	// ---- Selection ------------------------------------------------------------------------------
	function setSel(list: Element[], pt?: { x: number; y: number }) {
		sels = list
		hover = null
		hoverName = ''
		hoverAlike = []
		anchor = null
		const t = list[list.length - 1]
		if (t && pt) {
			const r = t.getBoundingClientRect()
			if (r.width && r.height) anchor = { fx: (pt.x - r.left) / r.width, fy: (pt.y - r.top) / r.height }
		}
		// The copies are looked up when the selection changes, not every frame.
		alike = list.length ? alikeSet(list) : { copies: [], total: 0 }
		joinableCache = null
		peek = false
		if (t) sendTokens()
		send()
		poke()
	}
	const select = (el: Element | null, pt?: { x: number; y: number }) => setSel(el ? [retarget(el)] : [], pt)
	const deselect = () => setSel([])
	function say(text: string, pt?: { x: number; y: number }) {
		post('tweak:info', { req: '', say: { text, x: pt?.x ?? 16, y: pt?.y ?? 16 } })
	}
	// Shift+click: add to the selection, or take out of it (the last one stays).
	function pick(el: Element, pt: { x: number; y: number }, additive: boolean) {
		const t = retarget(el)
		const cur = sels
		if (!additive || !cur.length) return setSel([t], pt)
		if (cur.includes(t)) return cur.length > 1 ? setSel(cur.filter((x) => x !== t)) : undefined
		if (kindOf(t) !== kindOf(cur[0])) return say(`Can't mix ${nameOf(t)} with ${nameOf(cur[0])}`, pt)
		setSel([...cur, t], pt)
	}
	function selectAll() {
		// The current pick stays last, so the popover stays where it is.
		setSel([...joinable(), ...sels])
	}
	function goParent() {
		if (sels.length !== 1) return
		const cur = sels[0]
		let p = parentOf(cur)
		// A parent inside the same frappe-ui component retargets to where we are: keep climbing.
		for (let i = 0; p && !isOurs(p) && i < 8; i++, p = parentOf(p)) {
			const t = retarget(p)
			if (t !== cur) return select(t)
		}
	}
	function goChild() {
		if (sels.length !== 1) return
		const c = childOf(sels[0])
		if (c && retarget(c) !== sels[0]) select(c)
	}

	// ---- Rects, once a frame while something may have moved ----------------------------------------
	// Frames run while something may have moved: a change of selection or hover, a scroll, a resize, a DOM change, a
	// transition. Each of those keeps them going for a moment (a CSS transition moves things without any event), then the
	// loop rests instead of reading rects every frame.
	let raf = 0
	let until = 0
	let lastRects = ''
	function poke(ms = 600) {
		until = Math.max(until, performance.now() + ms)
		if (!raf && (live || hls.length > 0)) raf = requestAnimationFrame(frame)
		else if (!live && !hls.length) postRects()
	}
	function postRects() {
		const vh = window.innerHeight
		const vw = window.innerWidth
		const picked = new Set(sels)
		const showLive = live
		// With a selection, only Shift (add or remove) brings the hover outline back, as in comment mode.
		const h = showLive && hover && !sels.includes(hover) && (!sels.length || shift) ? rectOf(hover) : null
		const faint = showLive
			? [...new Set([...alike.copies, ...hoverAlike])]
					.filter((e) => !picked.has(e) && e.isConnected)
					.map((e) => rectOf(e)!)
					.filter((r) => r.w > 0 && r.h > 0 && r.y < vh && r.y + r.h > 0 && r.x < vw && r.x + r.w > 0)
			: []
		const data: FromFrame['tweak:rects'] = {
			sel: showLive ? rectOf(sels[sels.length - 1] ?? null) : null,
			others: showLive ? sels.slice(0, -1).map((e) => rectOf(e)!) : [],
			faint,
			hover: h,
			hoverName: h ? hoverName : '',
			hl: hls.filter((e) => !sels.includes(e)).map((e) => rectOf(e)!),
			peek,
		}
		const key = JSON.stringify(data)
		if (key === lastRects) return
		lastRects = key
		post('tweak:rects', data)
	}
	function frame() {
		raf = 0
		// A removed element: drop it from the selection quietly, the tweak stays.
		if (sels.some((e) => !e.isConnected)) setSel(sels.filter((e) => e.isConnected))
		if (hover && !hover.isConnected) hover = null
		if (hls.some((e) => !e.isConnected)) hls = hls.filter((e) => e.isConnected)
		postRects()
		if (performance.now() < until) raf = requestAnimationFrame(frame)
	}
	// What can move things on screen, other than our own overlays restyling themselves.
	let mut: MutationObserver | null = null
	const WIN_EVENTS = ['scroll', 'resize', 'transitionrun', 'transitionend', 'animationstart', 'animationend']
	function onWin(e: Event) {
		if (e.target instanceof Node && isOurs(e.target)) return
		if (live && e.type === 'scroll') outside(true)
		poke()
	}
	let watching = false
	function watchLayout() {
		const on = live || hls.length > 0
		if (on === watching) return
		watching = on
		mut?.disconnect()
		mut = null
		for (const t of WIN_EVENTS) window.removeEventListener(t, onWin, true)
		if (!on) return
		for (const t of WIN_EVENTS) window.addEventListener(t, onWin, { capture: true, passive: true })
		mut = new MutationObserver((rs) => {
			if (rs.some((r) => !(r.type === 'attributes' && isOurs(r.target)))) poke()
		})
		mut.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true })
	}

	// ---- Floating layers --------------------------------------------------------------------------
	// A HoverCard, Popover or menu is teleported out of #app and closes when the pointer leaves it, which is exactly what
	// travelling to the shell's popover does. While something inside one is selected, the events that would close it
	// are swallowed. Once the lock lets go the layer closes on the pointer's next move, as it would on the page.
	function layerOf(el: Element | null): Element | null {
		if (!el || isOurs(el)) return null
		const app = document.querySelector('#app')
		if (!app || app.contains(el)) return null
		let n: Element = el
		while (n.parentElement && n.parentElement !== document.body) n = n.parentElement
		return n.parentElement === document.body && !isOurs(n) ? n : null
	}
	const LEAVE = ['pointerleave', 'pointerout', 'mouseleave', 'mouseout', 'focusout', 'blur']
	function keepOpen(e: Event) {
		const l = layerOf(sels[sels.length - 1] ?? null) ?? layerOf(hover)
		if (l && e.target instanceof Node && l.contains(e.target)) e.stopImmediatePropagation()
	}

	// ---- The pointer and the keys, while Tweak is the tool ------------------------------------------
	const pickable = (t: Element | null) => (t && t !== document.body && t !== document.documentElement ? t : null)
	const stop = (e: Event) => {
		e.preventDefault()
		e.stopPropagation()
		e.stopImmediatePropagation()
	}
	// While Shift is held, the hovered element shows its copies: what a Shift+click would offer.
	function setShift(v: boolean) {
		if (v === shift) return
		shift = v
		poke()
		hoverAlike = shift && hover ? alikeOf(hover) : []
	}
	let lastTarget: Element | null = null
	function onMove(e: PointerEvent) {
		shift = e.shiftKey
		const t = targetOf(e)
		// The vnode walk behind the name is not free: only when the pointer enters another element.
		if (t === lastTarget) return
		lastTarget = t
		const p = pickable(t)
		const el = p ? retarget(p) : null
		hover = el
		hoverName = el ? nameOf(el) : ''
		hoverAlike = shift && el ? alikeOf(el) : []
		poke()
	}
	// Set while a list row reopens a popover by clicking its trigger: the page must get that click.
	let passthrough = false
	function swallow(e: Event) {
		if (!passthrough && targetOf(e)) stop(e)
	}
	// A press or a scroll in the page closes what the shell has open (a token list), as one outside it would.
	let outsideAt = 0
	function outside(scroll = false) {
		const now = performance.now()
		if (scroll && now - outsideAt < 200) return
		outsideAt = now
		post('tweak:info', { req: '', outside: true })
	}
	function onPress(e: Event) {
		outside()
		swallow(e)
	}
	function onClick(e: MouseEvent) {
		if (passthrough) return
		const t = targetOf(e)
		if (!t) return
		stop(e)
		const el = pickable(t)
		if (el) pick(el, { x: e.clientX, y: e.clientY }, e.shiftKey)
	}
	function setPeek(v: boolean) {
		if (v === peek) return
		peek = v
		postRects()
	}
	// Heard on the window before the agent forwards Escape to the shell: with something selected, Escape lets go of it
	// here (and a page popover it sits in stays open), and the shell never hears it.
	function onKey(e: KeyboardEvent) {
		if (!live) return
		if (e.key === 'Shift') return setShift(e.type === 'keydown')
		if (e.key === ' ' && e.type === 'keyup') {
			// The release must not click a focused button either.
			if (!peek) return
			setPeek(false)
			e.preventDefault()
			return e.stopImmediatePropagation()
		}
		if (e.type === 'keyup') return
		if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing || !sels.length) return
		const t = e.target as HTMLElement | null
		// A text field in the page owns its keys, all but Escape.
		if (typing(t) && e.key !== 'Escape') return
		if (e.key === 'Escape') deselect()
		// Hold to see the page without the outlines; repeats still must not scroll it.
		else if (e.key === ' ') !e.repeat && setPeek(true)
		else if (e.key === '\\') goParent()
		else if (e.key === 'Enter' && !t?.closest?.('button,a')) goChild()
		else return
		e.preventDefault()
		e.stopImmediatePropagation()
	}
	window.addEventListener('keydown', onKey, true)
	window.addEventListener('keyup', onKey, true)
	window.addEventListener('blur', () => {
		setShift(false)
		setPeek(false)
	})

	let off: (() => void) | null = null
	function attach() {
		off = listen([
			['pointermove', onMove],
			['pointerdown', onPress],
			['mousedown', swallow],
			['mouseup', swallow],
			['click', onClick],
			['dblclick', swallow],
			...LEAVE.map((t) => [t, keepOpen] as [string, (e: any) => void]),
		])
	}
	function detach() {
		off?.()
		off = null
		lastTarget = null
		shift = false
		peek = false
		hover = null
		hoverName = ''
		hoverAlike = []
		if (sels.length) setSel([])
	}

	// ---- Finding a list row's elements again ---------------------------------------------------------
	// An element inside a popover is not there until its trigger has been clicked: do that once, then give the layer 1.5s
	// to appear. The elements found wait for `select`, which comes once the shell has turned Tweak on.
	let found: Element[] = []
	async function find(ids: string[]): Promise<boolean> {
		let els: Element[] = []
		let deadline = Date.now() + 2500
		let opened = false
		while (!els.length && Date.now() < deadline) {
			els = elsOfTweaks(ids)
			if (els.length) break
			const sel = opened ? null : openerOf(ids)
			const trigger = sel ? resolve(sel) : null
			if (trigger) {
				opened = true
				deadline = Math.max(deadline, Date.now() + 1500)
				// Already open and still empty: it is only filling in.
				if (trigger.getAttribute('aria-expanded') !== 'true') {
					passthrough = true
					try {
						;(trigger as HTMLElement).click()
					} finally {
						passthrough = false
					}
				}
			}
			await new Promise((r) => setTimeout(r, 100))
		}
		found = els
		return els.length > 0
	}

	startSync(() => toolActive, () => {
		sendStacks()
		refreshSoon()
	})
	setRoute(routeNow())

	const edits = <T extends { ref: string }>(list: T[]) => list.map((x) => [elOf(x.ref), x] as const).filter((p): p is readonly [Element, T] => !!p[0])

	return {
		tool(d: ToFrame['tool']) {
			toolActive = d.active
			const on = d.active && d.mode === 'tweak'
			if (on !== live) {
				detach()
				live = on
				if (on) attach()
				watchLayout()
				poke()
			}
			// The one owner of the crosshair while Tweak is the tool; the other tools set their own (pick.ts).
			if (on) document.body.style.cursor = 'crosshair'
			else if (!(d.active && (d.mode === 'note' || d.mode === 'comment'))) document.body.style.cursor = ''
		},
		async inspect(d: ToFrame['tweak:inspect']) {
			switch (d.op) {
				case 'clear':
					return deselect()
				case 'all':
					return selectAll()
				case 'parent':
					return goParent()
				case 'child':
					return goChild()
				case 'refresh':
					return send(d.req)
				case 'keys':
					if (d.shift !== undefined) setShift(d.shift)
					if (d.peek !== undefined) setPeek(d.peek)
					return
				case 'highlight':
					hls = d.ids?.length ? elsOfTweaks(d.ids) : []
					watchLayout()
					return poke()
				case 'find': {
					const ok = await find(d.ids ?? [])
					return post('tweak:info', { req: d.req, found: ok })
				}
				case 'select': {
					const els = found.filter((e) => e.isConnected)
					found = []
					if (!els.length) return
					els[0].scrollIntoView({ block: 'center' })
					return setSel(els)
				}
			}
		},
		preview(d: ToFrame['tweak:preview']) {
			setPreviewing(true)
			for (const [el, e] of edits(d.edits)) writeDom(el, e.classes)
		},
		commit(d: ToFrame['tweak:commit']) {
			for (const [el, e] of edits(d.edits)) writeDom(el, [...new Set(e.classes)])
			setPreviewing(false)
			refreshSoon()
		},
		cancel(d: ToFrame['tweak:cancel']) {
			for (const [el, e] of edits(d.edits)) writeDom(el, e.classes)
			setPreviewing(false)
			refreshSoon()
		},
		props(d: ToFrame['tweak:props']) {
			setPreviewing(d.phase === 'preview')
			for (const [el, e] of edits(d.edits)) writeProp(el, d.key, e.value)
			if (d.phase !== 'preview') refreshSoon()
		},
		copy(d: ToFrame['tweak:copy']) {
			const el = elOf(d.ref)
			if (el) writeCopyAt(el, d.i, d.to, d.stem)
			refreshSoon()
		},
		reapply(d: ToFrame['tweak:reapply']) {
			setTweaks(d.tweaks, d.bind, elOf)
			joinableCache = null
			refreshSoon()
		},
		routed(key: string) {
			setRoute(key)
			deselect()
			hls = []
			watchLayout()
			poke()
			reapply()
		},
	}
}
