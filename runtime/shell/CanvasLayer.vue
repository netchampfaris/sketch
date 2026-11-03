<script setup lang="ts">
// What the Viewer shell draws over the frame's canvas: the pins on the tiles, the panel on the right (or its "Show
// panel" button), and on a phone the Show list under the title pill's name, all in the places the in-frame canvas had
// them (runtime/variants/Canvas.vue). The canvas itself and its title and zoom pills stay in the frame.
//
// The pins sit in one layer moved by the canvas's pan and zoom (a single CSS transform), each pin at its place on
// its tile in the canvas's own coordinates, so they stay on their tiles as the frame reports each frame of a pan.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { Button, Popover, Tooltip } from 'frappe-ui'
import type { Rect } from '../shared/protocol'
import CanvasPanel from './CanvasPanel.vue'
import ShowList from './ShowList.vue'
import { placeToasts } from './actions'
import { lookAt } from './badges'
import { onFrame, onGone, page, post } from './frame'
import { PANEL_W, canvas, showView, takeChosen } from './canvas'

const panelShown = computed(() => !canvas.phone && canvas.panelOpen)
// The canvas fits its tiles in the room the panel leaves. The frame hears it before the canvas opens too, so the first
// fit is already right (and a fresh frame hears it again); the toolbar keeps out of that room while the canvas is open.
watch(
	[() => (panelShown.value ? PANEL_W : 0), () => canvas.open, () => page.ready],
	([reserve, open]) => {
		canvas.reserve = open ? reserve : 0
		post('display', { reserve })
		// Toasts stand left of the panel (actions.ts placeToasts): it is 12px off the right edge and PANEL_W - 24 wide.
		if (open) placeToasts()
		if (open && reserve) document.documentElement.style.setProperty('--sketch-panel-w', `${reserve - 12}px`)
		else document.documentElement.style.removeProperty('--sketch-panel-w')
	},
	{ immediate: true },
)

// A row picked in the panel shows that in the canvas, in place.
function choose(v: string) {
	if (!v || v === canvas.view) return
	showView(v)
}
// The phone's Show list, under the title pill's name where the frame says it is. The frame's name asks to open it or
// to close it; a press in the frame while it is open closes it too, as a press outside does.
const showAt = ref<Rect | null>(null)
const showOpen = computed({
	get: () => !!showAt.value && canvas.open && canvas.phone,
	set: (o: boolean) => !o && (showAt.value = null),
})
onBeforeUnmount(onFrame('canvas:show', (d) => (showAt.value = d.open && canvas.open && canvas.phone ? d.rect : null)))
onBeforeUnmount(onGone(() => (showAt.value = null)))
watch(showOpen, (o) => post('display', { showOpen: o }))
useEventListener(window, 'blur', () => showOpen.value && document.activeElement?.tagName === 'IFRAME' && (showOpen.value = false))
function chooseOnPhone(v: string) {
	showOpen.value = false
	choose(v)
}

// Opening a set from the shell is looking at all of its options: the ones a teammate made stop being new (the rows lose
// their dot; the tiles keep their "New" badge until the next visit, so nothing vanishes under the pointer). Only a view
// the person picked here counts, once the canvas shows it, and only options the server named new (badges.ts lookAt).
watch(
	() => [canvas.view, canvas.items] as const,
	([view, items]) => {
		const item = items.find((i) => i.value === view)
		if (!item || !takeChosen(view)) return
		if (view.startsWith('set:')) lookAt(item.options)
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
	if (e.key !== 'Escape' || e.defaultPrevented || e.isComposing || layered || !canvas.open) return
	post('escape', {})
})

const inv = computed(() => 1 / canvas.zoom)
</script>

<template>
	<template v-if="canvas.open">
		<!-- The pins on the tiles: one layer under the pan and zoom, below the panel and the toolbar. Only the pins take the pointer. -->
		<div class="pointer-events-none absolute inset-0 overflow-hidden">
			<div
				class="absolute left-0 top-0 origin-top-left"
				:style="{ transform: `translate(${canvas.pan.x}px, ${canvas.pan.y}px) scale(${canvas.zoom})`, '--inv': inv }"
			>
				<component :is="canvas.Pins" v-if="canvas.Pins" :tiles="canvas.tiles" :zoom="canvas.zoom" />
			</div>
		</div>

		<CanvasPanel v-if="panelShown" :items="canvas.items" :selected="canvas.view" @choose="choose" @hide="canvas.panelOpen = false" />
		<!-- Where the hide button sits in the open panel, so the icon stays put when toggled. -->
		<div
			v-else-if="!canvas.phone"
			data-ui
			class="pointer-events-auto absolute right-6 top-6 z-10 rounded-[8px] bg-surface-elevation-2 shadow-sm ring-1 ring-outline-gray-2"
		>
			<Tooltip text="Show panel">
				<Button variant="ghost" icon="lucide-panel-right" aria-label="Show panel" @click="canvas.panelOpen = true" />
			</Tooltip>
		</div>

		<Popover v-model:open="showOpen" trigger="manual" side="bottom" align="start" :offset="8" :collision-padding="12">
			<template #trigger>
				<!-- Where the frame's name is: the list hangs from it. It takes no pointer, the frame's button under it does. -->
				<div
					aria-hidden="true"
					class="pointer-events-none fixed"
					:style="showAt ? { left: `${showAt.x}px`, top: `${showAt.y}px`, width: `${showAt.w}px`, height: `${showAt.h}px` } : { left: '-9999px', top: '0', width: '1px', height: '1px' }"
				/>
			</template>
			<div class="flex flex-col p-2" style="width: calc(100vw - 24px)" data-ui>
				<ShowList
					:items="canvas.items"
					:selected="canvas.view"
					width="calc(var(--reka-popover-trigger-width) - 1rem)"
					max-height="calc(100dvh - 7.5rem)"
					@choose="chooseOnPhone"
				/>
			</div>
		</Popover>
	</template>
</template>
