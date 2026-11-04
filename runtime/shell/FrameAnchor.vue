<script setup lang="ts">
// Where a box the frame reported is (its ⋯, its title pill's name): a shell popover hangs from it. It takes no pointer,
// the frame's button under it does.
//
// The frame may report the box, and so open the popover, whenever it likes, under a pointer that was aiming at the page.
// `take()` gives the element the person's last press here began on, only when it began at least 300 ms after the box was
// reported: a press already on its way (or one dragged in from the page) gives nothing. Whoever asks checks the press
// began on what is acting.
import { watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import type { Rect } from '../shared/protocol'

const GUARD_MS = 300

const props = defineProps<{ rect: Rect | null }>()

let openedAt = 0
let press: { el: Element | null; t: number } | null = null
watch(
	() => props.rect,
	(r) => {
		if (!r) return
		openedAt = performance.now()
		press = null
	},
)
useEventListener(
	document,
	'pointerdown',
	(e: PointerEvent) => (press = props.rect ? { el: e.target instanceof Element ? e.target : null, t: performance.now() } : null),
	{ capture: true },
)

function take(): Element | null {
	const p = press
	press = null
	return p && p.t - openedAt >= GUARD_MS ? p.el : null
}
defineExpose({ take })
</script>

<template>
	<div
		aria-hidden="true"
		class="pointer-events-none fixed"
		:style="rect ? { left: `${rect.x}px`, top: `${rect.y}px`, width: `${rect.w}px`, height: `${rect.h}px` } : { left: '-9999px', top: '0', width: '1px', height: '1px' }"
	/>
</template>
