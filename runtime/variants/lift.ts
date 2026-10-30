// Lift a version out of its live page: the page renders whole, so its data, styles, state and providers stay real, but
// only the set's element shows. Everything else is `visibility: hidden` (still laid out), and the scroll containers
// around the element stop clipping, so it sits at its natural place, its real width and its full height, and nothing
// scrolls to find it. The tile then moves the page by the element's offset (Tile.vue).
import type { Crop } from './snapshot'

const ROOT = 'data-sketch-lift'
const SHOW = 'data-sketch-lift-show'
const OPEN = 'data-sketch-lift-open'
const MINW = 'data-sketch-lift-minw'
const MINH = 'data-sketch-lift-minh'
const GROW = 'data-sketch-lift-grow'
const GROW_COL = 'data-sketch-lift-grow-col'
const MARKS = [SHOW, OPEN, MINW, MINH, GROW, GROW_COL]

// Paint containment and overflow would clip the element; layout containment stays, so `fixed` and `absolute` parts of the
// page keep the frame as their containing block. A scroll container's automatic minimum size is 0 in flex and grid, so
// an opened one keeps that and the layout around it does not move.
const CSS = `
[${ROOT}]{visibility:hidden!important;overflow:visible!important;contain:layout!important}
[${SHOW}]{visibility:visible!important}
[${OPEN}]{overflow:visible!important}
[${MINW}]{min-width:0!important}
[${MINH}]{min-height:0!important}
[${GROW}]{overflow:visible!important;height:auto!important;max-height:none!important;align-self:flex-start!important;bottom:auto!important}
[${GROW_COL}]{flex:none!important}
`
let styled = false
function ensureStyle() {
  if (styled) return
  styled = true
  const el = document.createElement('style')
  el.setAttribute('data-sketch-ui', 'lift')
  el.textContent = CSS
  document.head.appendChild(el)
}

// Marks `root` as a lifted page and `els` as what shows, clearing earlier marks. A snapshot keeps the marks inside the
// root; its wrapper in the tile carries the root's own mark. With `grow` (a state tile), the set and every box in it that
// scrolls its overflow grow to their full content, so the whole of it shows.
export function lift(root: HTMLElement, els: Element[], grow = false) {
  ensureStyle()
  root.setAttribute(ROOT, '')
  for (const a of MARKS) root.querySelectorAll(`[${a}]`).forEach((n) => n.removeAttribute(a))
  for (const el of els) {
    el.setAttribute(SHOW, '')
    for (let n = el.parentElement; n && n !== root; n = n.parentElement) {
      if (n.hasAttribute(OPEN)) continue
      const cs = getComputedStyle(n)
      if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue
      if (cs.minWidth === 'auto') n.setAttribute(MINW, '')
      if (cs.minHeight === 'auto') n.setAttribute(MINH, '')
      n.setAttribute(OPEN, '')
    }
    if (grow) for (const n of [el, ...el.querySelectorAll('*')]) unclip(n)
  }
}

// A box that scrolls its overflow grows to its content. Outer boxes go first (document order), so an inner one is judged
// once the box around it has grown. Only the height changes: in a column flexbox it stops flexing, elsewhere it stops
// stretching to its row.
function unclip(n: Element) {
  const cs = getComputedStyle(n)
  // Scroll boxes only: a clamp or a crop that hides on purpose (`line-clamp`, `overflow-hidden`) stays as it is.
  if (!/auto|scroll/.test(cs.overflowY) || n.scrollHeight <= n.clientHeight + 1) return
  n.setAttribute(GROW, '')
  const parent = n.parentElement ? getComputedStyle(n.parentElement) : null
  if (parent?.display.includes('flex') && parent.flexDirection.startsWith('column')) n.setAttribute(GROW_COL, '')
}

// Where `els` sit in `root`, in `root`'s own px (the canvas may be zoomed).
export function boxIn(root: HTMLElement, els: Element[]): Crop | null {
  const rs = els.map((e) => e.getBoundingClientRect()).filter((r) => r.width || r.height)
  if (!rs.length) return null
  const fr = root.getBoundingClientRect()
  const k = root.offsetWidth ? fr.width / root.offsetWidth : 1
  const x = Math.min(...rs.map((r) => r.left)), y = Math.min(...rs.map((r) => r.top))
  const right = Math.max(...rs.map((r) => r.right)), bottom = Math.max(...rs.map((r) => r.bottom))
  const round = (n: number) => Math.round(n * 100) / 100
  return { x: round((x - fr.left) / k), y: round((y - fr.top) / k), w: round((right - x) / k), h: round((bottom - y) / k) }
}

// The first copy of a set as the page reads, top to bottom, then left to right: a set drawn many times (a card in a v-for)
// shows one, whatever order the code mounts them in. Document order breaks ties, and decides for copies not laid out.
export function firstCopy(copies: (() => Element[])[]): Element[] {
  let best: Element[] = []
  let at = { y: Infinity, x: Infinity }
  for (const get of copies) {
    const els = get().filter((e) => e.isConnected)
    if (!els.length) continue
    const r = els[0].getBoundingClientRect()
    const here = r.width || r.height ? { y: Math.round(r.top), x: Math.round(r.left) } : { y: Infinity, x: Infinity }
    const before =
      here.y < at.y ||
      (here.y === at.y && here.x < at.x) ||
      (here.y === at.y && here.x === at.x && !!best.length && !!(best[0].compareDocumentPosition(els[0]) & Node.DOCUMENT_POSITION_PRECEDING))
    if (!best.length || before) {
      best = els
      at = here
    }
  }
  return best
}

// Keeps a live page lifted onto the set while it changes: a state switch re-renders the option, something expands, the
// page scrolls itself. `report` gets the element's box each time it moves or resizes.
export function follow(root: HTMLElement, els: () => Element[], report: (box: Crop | null) => void, grow = false) {
  let raf = 0
  let last = ''
  let watched: Element[] = []
  const ro = new ResizeObserver(() => schedule())
  const run = () => {
    raf = 0
    const now = els()
    if (now.length !== watched.length || now.some((e, i) => e !== watched[i])) {
      watched.forEach((e) => ro.unobserve(e))
      now.forEach((e) => ro.observe(e))
      watched = now
    }
    lift(root, now, grow)
    const box = boxIn(root, now)
    const key = JSON.stringify(box)
    if (key !== last) {
      last = key
      report(box)
    }
  }
  const schedule = () => (raf ||= requestAnimationFrame(run))
  const mo = new MutationObserver((list) => {
    // Our own marks are attribute writes; only the page's changes count.
    if (list.some((m) => m.type === 'childList' || !String(m.attributeName).startsWith('data-sketch-lift'))) schedule()
  })
  mo.observe(root, { childList: true, subtree: true, attributes: true })
  ro.observe(root)
  root.addEventListener('scroll', schedule, true)
  run()
  return () => {
    cancelAnimationFrame(raf)
    ro.disconnect()
    mo.disconnect()
    root.removeEventListener('scroll', schedule, true)
  }
}
