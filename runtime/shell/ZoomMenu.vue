<script setup lang="ts">
// The canvas's zoom menu, drawn by the shell so it opens over the panel and the pins, as it did in the frame. The frame's
// % (runtime/variants/Canvas.vue) only says where it is (`zoom:menu`); the menu opens there with the items it had, and a
// pick goes back as `canvas:zoom`. A pick only zooms the frame's own canvas, which the frame could do itself, so unlike
// the tile menu no item waits for a press of its own.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Dropdown } from 'frappe-ui'
import type { Rect, ZoomTo } from '../shared/protocol'
import { onFrame, onGone, post } from './frame'
import { canvas } from './canvas'
import { menuBind } from '../shared/menus'
import FrameAnchor from './FrameAnchor.vue'

const at = ref<Rect | null>(null)
// The menu opens in the shell's own layer, under the toolbar and over the pins and the panel, as it did in the frame.
const host = ref<HTMLElement | null>(null)
const bind = computed(() => menuBind('zoom'))
const open = computed({
	get: () => !!at.value && bind.value.open,
	set: (o: boolean) => {
		bind.value['onUpdate:open'](o)
		if (!o) at.value = null
	},
})
onBeforeUnmount(
	onFrame('zoom:menu', (d) => {
		if (!canvas.open) return
		// Opened by a pointer, the menu takes the focus itself and lights no item, as it did in the frame: the shell's
		// menus read the last input they heard, and a press in the frame is not heard here.
		if (!d.keyboard) window.dispatchEvent(new PointerEvent('pointermove'))
		at.value = d.rect
		bind.value['onUpdate:open'](true)
	}),
)
onBeforeUnmount(onGone(() => (open.value = false)))
// The frame's % holds its pressed look while the menu is open, as a menu's trigger does.
watch(open, (o) => post('display', { zoomMenu: o }))
watch(() => canvas.open, (o) => !o && (open.value = false))

const zoom = (to: ZoomTo) => () => post('canvas:zoom', { to })
const items = [
	{ label: 'Zoom to fit', onClick: zoom('fit') },
	...(['0.5', '1', '2'] as const).map((z) => ({ label: `${Number(z) * 100}%`, onClick: zoom(z) })),
]
</script>

<template>
	<div ref="host" class="pointer-events-auto fixed left-0 top-0 z-[100] size-0" />
	<Dropdown v-model:open="open" :portal-to="host" :options="items">
		<template #trigger>
			<!-- Where the frame's % is: the menu hangs from it. -->
			<FrameAnchor :rect="at" />
		</template>
	</Dropdown>
</template>
