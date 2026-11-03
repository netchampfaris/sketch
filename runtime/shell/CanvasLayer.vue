<script setup lang="ts">
// What the Viewer shell draws over the frame's canvas: the pins on the tiles, the panel on the right (or its "Show
// panel" button), all in the places the in-frame canvas had them (runtime/variants/Canvas.vue). The canvas itself, its
// title and zoom pills and the phone's Show dropdown stay in the frame.
//
// The pins sit in one layer moved by the canvas's pan and zoom (a single CSS transform), each pin at its place on
// its tile in the canvas's own coordinates, so they stay on their tiles as the frame reports each frame of a pan.
import { computed, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { Button, Tooltip } from 'frappe-ui'
import CanvasPanel from './CanvasPanel.vue'
import { lookAt } from './badges'
import { page, post } from './frame'
import { PANEL_W, bridge } from './variants'

const panelShown = computed(() => !bridge.phone && bridge.panelOpen)
// The canvas fits its tiles in the room the panel leaves. The frame hears it before the canvas opens too, so the first
// fit is already right (and a fresh frame hears it again); the toolbar keeps out of that room while the canvas is open.
watch(
	[() => (panelShown.value ? PANEL_W : 0), () => bridge.open, () => page.ready],
	([reserve, open]) => {
		bridge.reserve = open ? reserve : 0
		post('display', { reserve })
	},
	{ immediate: true },
)

// A row picked in the panel shows that in the canvas, in place.
function choose(v: string) {
	if (!v || v === bridge.view) return
	post('canvas:open', { view: v })
}
// Opening a set is looking at all of its options: the ones a teammate made stop being new (the rows lose their dot; the
// tiles keep their "New" badge until the next visit, so nothing vanishes under the pointer).
watch(
	() => [bridge.view, bridge.items] as const,
	([view, items]) => {
		if (!view.startsWith('set:')) return
		lookAt(items.find((i) => i.value === view)?.options ?? [])
	},
	{ immediate: true },
)

// Escape with the focus here (in the panel, say) leaves the canvas as it does in the frame, once nothing of ours took it:
// the toolbar's box or tool, one of our menus or dialogs. It goes to the frame, whose canvas closes on it.
let layered = false
const LAYERS = '[role="menu"][data-state="open"],[role="dialog"][data-state="open"],[data-dismissable-layer]'
useEventListener(
	window,
	'keydown',
	(e: KeyboardEvent) => {
		if (e.key === 'Escape') layered = [...document.querySelectorAll(LAYERS)].some((l) => !l.querySelector('[role="tooltip"]'))
	},
	{ capture: true },
)
useEventListener(window, 'keydown', (e: KeyboardEvent) => {
	if (e.key !== 'Escape' || e.defaultPrevented || e.isComposing || layered || !bridge.open) return
	post('escape', {})
})

const inv = computed(() => 1 / bridge.zoom)
</script>

<template>
	<template v-if="bridge.open">
		<!-- The pins on the tiles: one layer under the pan and zoom, below the panel and the toolbar. Only the pins take the pointer. -->
		<div class="pointer-events-none absolute inset-0 overflow-hidden">
			<div
				class="absolute left-0 top-0 origin-top-left"
				:style="{ transform: `translate(${bridge.pan.x}px, ${bridge.pan.y}px) scale(${bridge.zoom})`, '--inv': inv }"
			>
				<component :is="bridge.Pins" v-if="bridge.Pins" :tiles="bridge.tiles" :zoom="bridge.zoom" :view="bridge.view" />
			</div>
		</div>

		<CanvasPanel v-if="panelShown" :items="bridge.items" :selected="bridge.view" @choose="choose" @hide="bridge.panelOpen = false" />
		<!-- Where the hide button sits in the open panel, so the icon stays put when toggled. -->
		<div
			v-else-if="!bridge.phone"
			data-ui
			class="pointer-events-auto absolute right-6 top-6 z-10 rounded-[8px] bg-surface-elevation-2 shadow-sm ring-1 ring-outline-gray-2"
		>
			<Tooltip text="Show panel">
				<Button variant="ghost" icon="lucide-panel-right" aria-label="Show panel" @click="bridge.panelOpen = true" />
			</Tooltip>
		</div>
	</template>
</template>
