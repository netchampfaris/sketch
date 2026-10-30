// The height of the Prototype's own fixed bottom bar (frappe-ui's MobileNav), 0 when there is none or the
// screen is not a phone. Anything floating at the bottom edge adds it to its bottom offset, so it rides
// above the bar instead of hiding its tabs. Same query and selector as the Variants pill's own measuring.
import { onMounted, ref, watch, type WatchSource } from 'vue'
import { useEventListener, useResizeObserver } from '@vueuse/core'

const PHONE = '(max-width: 767px)'
const NAV = '[data-slot="mobile-nav"]'

// `again` is anything that may add or remove the bar (the route); it is measured once the page has rendered.
export function useMobileNavHeight(again?: WatchSource) {
	const height = ref(0)
	const bar = ref<HTMLElement | null>(null)
	function measure() {
		bar.value = window.matchMedia(PHONE).matches ? document.querySelector<HTMLElement>(NAV) : null
		height.value = bar.value?.offsetHeight ?? 0
	}
	measure()
	// The bar may render after the toolbar does.
	onMounted(() => requestAnimationFrame(measure))
	useEventListener(window, 'resize', measure)
	useResizeObserver(bar, () => (height.value = bar.value?.offsetHeight ?? 0))
	if (again) watch(again, () => requestAnimationFrame(measure), { flush: 'post' })
	return height
}
