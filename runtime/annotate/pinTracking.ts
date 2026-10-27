// What the note pins and the comment pins share: each follows its element, re-measured on every
// scroll, resize, route change and (throttled) DOM change. The layer supplies `measure` and what it
// depends on; our own pins and outlines changing never trigger another measure.
import { onBeforeUnmount, onMounted, watch, type WatchSource } from 'vue'
import { useEventListener } from '@vueuse/core'
import { hoverEl, hoverFrac, isOurs } from './annotate'

export function usePinTracking(measure: () => void, watched: WatchSource[]) {
	let raf = 0
	function schedule() {
		if (raf) return
		raf = requestAnimationFrame(() => {
			raf = 0
			measure()
		})
	}

	// Scroll doesn't bubble, so listen in the capture phase to catch the shell's own scroller.
	useEventListener(window, 'scroll', schedule, { capture: true, passive: true })
	useEventListener(window, 'resize', schedule)

	let mo: MutationObserver | null = null
	let wait = 0
	onMounted(() => {
		measure()
		mo = new MutationObserver((list) => {
			if (list.every((m) => isOurs(m.target))) return
			if (wait) return
			wait = window.setTimeout(() => {
				wait = 0
				schedule()
			}, 120)
		})
		mo.observe(document.body, { childList: true, subtree: true })
	})
	onBeforeUnmount(() => {
		mo?.disconnect()
		cancelAnimationFrame(raf)
		clearTimeout(wait)
		clearHover()
	})
	watch(watched, schedule, { flush: 'post' })
	return schedule
}

// A pin's element is outlined while the pointer is on it.
export function clearHover() {
	hoverEl.value = null
	hoverFrac.value = null
}
