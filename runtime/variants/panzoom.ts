// Pan and zoom for the canvas viewport: wheel and trackpad, drag, touch pinch, and fit.
import { reactive } from 'vue'

export const MIN_ZOOM = 0.05
export const MAX_ZOOM = 2
const clamp = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z))

export function usePanZoom(getEl: () => HTMLElement | null) {
  const view = reactive({ x: 0, y: 0, z: 1 })
  let travel = 0
  // Set once the user pans or zooms, so a late re-fit doesn't undo it.
  const flags = { touched: false }

  function zoomAt(z: number, cx: number, cy: number) {
    flags.touched = true
    const next = clamp(z)
    const k = next / view.z
    view.x = cx - (cx - view.x) * k
    view.y = cy - (cy - view.y) * k
    view.z = next
  }
  function zoomBy(f: number) {
    const el = getEl()
    if (el) zoomAt(view.z * f, el.clientWidth / 2, el.clientHeight / 2)
  }
  function zoomTo(z: number) {
    const el = getEl()
    if (el) zoomAt(z, el.clientWidth / 2, el.clientHeight / 2)
  }
  // Fit a world rect inside the viewport with padding, never above `max`.
  function fit(r: { x: number; y: number; w: number; h: number }, pad = 48, max = 1) {
    const el = getEl()
    if (!el || !r.w || !r.h) return
    const vw = el.clientWidth, vh = el.clientHeight
    const z = clamp(Math.min(max, (vw - pad * 2) / r.w, (vh - pad * 2) / r.h))
    view.z = z
    view.x = (vw - r.w * z) / 2 - r.x * z
    view.y = (vh - r.h * z) / 2 - r.y * z
    flags.touched = false
  }

  function attach(el: HTMLElement) {
    const pts = new Map<number, { x: number; y: number }>()
    let pinch: { d: number; z: number } | null = null
    let dragging = false
    const local = (e: { clientX: number; clientY: number }) => {
      const r = el.getBoundingClientRect()
      return { x: e.clientX - r.left, y: e.clientY - r.top }
    }

    const onWheel = (e: WheelEvent) => {
      // Over a live tile too: the version is lifted out of its page (lift.ts), so there is nothing in it to scroll to.
      const zoom = e.ctrlKey || e.metaKey
      e.preventDefault()
      flags.touched = true
      if (zoom) {
        const p = local(e)
        zoomAt(view.z * Math.exp(Math.max(-0.3, Math.min(0.3, -e.deltaY * 0.01))), p.x, p.y)
      } else {
        view.x -= e.deltaX
        view.y -= e.deltaY
      }
    }
    const onDown = (e: PointerEvent) => {
      const t = e.target as HTMLElement
      travel = 0
      if (t.closest('[data-live]') || t.closest('[data-ui]')) return
      if (t.closest('[data-tile]') && e.pointerType === 'mouse') return
      if (e.pointerType === 'mouse' && e.button !== 0) return
      pts.set(e.pointerId, local(e))
      if (pts.size === 2) {
        const [a, b] = [...pts.values()]
        pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, z: view.z }
      }
    }
    const onMove = (e: PointerEvent) => {
      const prev = pts.get(e.pointerId)
      if (!prev) return
      const cur = local(e)
      pts.set(e.pointerId, cur)
      if (pts.size === 2 && pinch) {
        const [a, b] = [...pts.values()]
        zoomAt(pinch.z * (Math.hypot(a.x - b.x, a.y - b.y) / pinch.d), (a.x + b.x) / 2, (a.y + b.y) / 2)
        travel += 10
        return
      }
      travel += Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y)
      if (!dragging && travel > 4) {
        dragging = true
        el.setPointerCapture?.(e.pointerId)
        el.style.cursor = 'grabbing'
      }
      if (dragging) {
        flags.touched = true
        view.x += cur.x - prev.x
        view.y += cur.y - prev.y
      }
    }
    const onUp = (e: PointerEvent) => {
      pts.delete(e.pointerId)
      if (pts.size < 2) pinch = null
      if (!pts.size) {
        dragging = false
        el.style.cursor = ''
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointercancel', onUp)
    return () => {
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointercancel', onUp)
    }
  }

  return { view, zoomAt, zoomBy, zoomTo, fit, attach, flags, moved: () => travel > 4 }
}
