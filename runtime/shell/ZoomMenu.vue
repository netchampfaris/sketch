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
	<Dropdown v-model:open="open" :options="items">
		<template #trigger>
			<!-- Where the frame's % is: the menu hangs from it. -->
			<FrameAnchor :rect="at" />
		</template>
	</Dropdown>
</template>
