<script setup lang="ts">
// What the Viewer shell draws over the frame's canvas: the pins on the tiles, the panel on the right (or its "Show
// panel" button), an option's empty States view with Ask agent, and on a phone the Show list under the title pill's
// name, all in the places the in-frame canvas had them (runtime/variants/Canvas.vue). The canvas itself and its title
// and zoom pills stay in the frame; the zoom menu is ZoomMenu.vue.
//
// The pins sit in one layer moved by the canvas's pan and zoom (a single CSS transform), each pin at its place on
// its tile in the canvas's own coordinates, so they stay on their tiles as the frame reports each frame of a pan.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { Button, Popover, Tooltip, toast } from 'frappe-ui'
import type { Pill, Rect } from '../shared/protocol'
import CanvasPanel from './CanvasPanel.vue'
import ShowList from './ShowList.vue'
import FrameAnchor from './FrameAnchor.vue'
import { placeToasts } from './actions'
import { addNote, notes, removeNote } from './annotate'
import { saveNow } from './notes'
import { tileAnchor } from './tiles'
import { sameTile } from '../shared/tiles'
import { onFrame, onGone, page, post } from './frame'
import { PANEL_W, canvas, showView } from './canvas'

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
// to close it; a press in the frame while it is open closes it too, as a press outside does. The frame may open it
// whenever it likes, so a row shows only on a press that began on it at least 300 ms after the list opened, and the
// search's Enter only after such a press in the list (FrameAnchor.vue): keys typed into a field as it opens pick nothing.
const showAt = ref<Rect | null>(null)
const showOpen = computed({
	get: () => !!showAt.value && canvas.open && canvas.phone,
	set: (o: boolean) => !o && (showAt.value = null),
})
onBeforeUnmount(onFrame('canvas:show', (d) => (showAt.value = d.open && canvas.open && canvas.phone ? d.rect : null)))
onBeforeUnmount(onGone(() => (showAt.value = null)))
watch(showOpen, (o) => post('display', { showOpen: o }))
useEventListener(window, 'blur', () => showOpen.value && document.activeElement?.tagName === 'IFRAME' && (showOpen.value = false))
const anchor = ref<InstanceType<typeof FrameAnchor> | null>(null)
const list = ref<HTMLElement | null>(null)
let clicked: Element | null = null
function chooseOnPhone(v: string) {
	const el = anchor.value?.take() ?? null
	// A click names its row; the search's Enter names none, so the press must have been in the list.
	const on = clicked ? clicked.closest('button') : list.value
	clicked = null
	if (!el || !on?.contains(el)) return
	showOpen.value = false
	choose(v)
}

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
// The frame's title and zoom pills sit over the pins, as they did when both were in the frame: the pins' layer is cut
// out where the pills are, rounded as they are, so a pin under one neither shows nor takes the pointer.
const roundRect = ({ x, y, w, h, r }: Pill) => {
	const k = Math.min(r, w / 2, h / 2)
	return `M${x + k} ${y}H${x + w - k}A${k} ${k} 0 0 1 ${x + w} ${y + k}V${y + h - k}A${k} ${k} 0 0 1 ${x + w - k} ${y + h}H${x + k}A${k} ${k} 0 0 1 ${x} ${y + h - k}V${y + k}A${k} ${k} 0 0 1 ${x + k} ${y}Z`
}
const pinClip = computed(() => (canvas.pills.length ? `path(evenodd, "M-1e5 -1e5H1e5V1e5H-1e5Z${canvas.pills.map(roundRect).join('')}")` : undefined))

// One option's States view with nothing declared: one line and a way to ask the agent for it. The note is the one the
// Note tool makes, on the option's own tile of its set; while it waits for the agent the view says so. The note is on
// the server before the view says it is there: if it cannot be saved it is taken back, and the reason is shown.
const OPENING = 'Build the states for'
const pendingNote = computed(() => {
	const spot = canvas.empty?.spot
	if (!spot) return null
	return notes.value.find((n) => !!n.tile && !n.sent && n.note.startsWith(OPENING) && sameTile({ route: n.route, tile: n.tile }, spot))?.id ?? null
})
const asking = ref(false)
async function askAgent() {
	const v = canvas.empty
	if (!v || !canvas.canNote || asking.value) return
	asking.value = true
	try {
		const note = `${OPENING} ${v.set} · ${v.option}${v.file ? ` (${v.file})` : ''}. Follow the States section of the Sketch skill.`
		const id = addNote({ ...tileAnchor(v.spot, { fx: 0.5, fy: 0.5 }), note })
		const why = await saveNow()
		if (why) {
			removeNote(id)
			toast.error(`Could not add the note: ${why}. Try again.`)
		}
	} finally {
		asking.value = false
	}
}
const undoAsk = () => pendingNote.value && removeNote(pendingNote.value)
</script>

<template>
	<template v-if="canvas.open">
		<!-- The pins on the tiles: one layer under the pan and zoom, below the panel and the toolbar. Only the pins take the pointer. -->
		<div class="pointer-events-none absolute inset-0 overflow-hidden" :style="{ clipPath: pinClip }">
			<div
				class="absolute left-0 top-0 origin-top-left"
				:style="{ transform: `translate(${canvas.pan.x}px, ${canvas.pan.y}px) scale(${canvas.zoom})`, '--inv': inv }"
			>
				<component :is="canvas.Pins" v-if="canvas.Pins" :tiles="canvas.tiles" :zoom="canvas.zoom" />
			</div>
		</div>

		<!-- An option with no states built: say so, and offer the agent. -->
		<div
			v-if="canvas.empty"
			data-ui
			class="pointer-events-none absolute inset-y-0 left-0 flex flex-col items-center justify-center gap-2 px-6 text-center"
			:style="{ right: panelShown ? `${PANEL_W}px` : '0' }"
		>
			<template v-if="pendingNote">
				<p class="text-base text-ink-gray-8">Added to your notes for the agent.</p>
				<p class="text-p-sm text-ink-gray-5">Tell your agent to apply your notes.</p>
				<Button class="pointer-events-auto" variant="ghost" label="Undo" @click="undoAsk" />
			</template>
			<template v-else>
				<p class="text-base text-ink-gray-8">No states built yet</p>
				<Button v-if="canvas.canNote" class="pointer-events-auto" variant="subtle" theme="gray" label="Ask agent" :loading="asking" @click="askAgent" />
			</template>
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
				<!-- Where the frame's name is: the list hangs from it. -->
				<FrameAnchor ref="anchor" :rect="showAt" />
			</template>
			<div ref="list" class="flex flex-col p-2" style="width: calc(100vw - 24px)" data-ui @click.capture="clicked = $event.target as Element" @keydown.capture="clicked = null">
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
