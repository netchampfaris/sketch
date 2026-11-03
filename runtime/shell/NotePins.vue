<script setup lang="ts">
// Numbered markers on the page, drawn by the shell over the frame from the rects it reports. Each
// follows its element: the frame re-measures it on every scroll, resize, route change and (throttled) DOM change.
// A pin whose element has gone stays where it last was, faded. Sent notes turn gray.
import { computed, onBeforeUnmount } from 'vue'
import { UI_ATTR, notes, type Note } from './annotate'
import { rects, track, type Target } from './frame'
import { clearHover, pinHover } from './pinHover'

const props = defineProps<{ route: string; selected?: string; refs: Map<string, string[]> }>()
const emit = defineEmits<{ open: [note: Note, x: number, y: number] }>()

// Notes on canvas tiles have their pins on the canvas.
const visible = computed(() => notes.value.filter((n) => n.route === props.route && !n.tile))
const idOf = (n: Note) => `note:${n.id}`
onBeforeUnmount(track(() => Object.fromEntries(visible.value.map((n): [string, Target] => [idOf(n), { sel: n.selector, ref: props.refs.get(n.id)?.[0] }]))))
onBeforeUnmount(clearHover)

// Numbered by position among this page's notes, never stored: deleting one renumbers the rest.
const numberOf = (n: Note) => visible.value.findIndex((x) => x.id === n.id) + 1
const last: Record<string, { x: number; y: number }> = {}
type Pos = { x: number; y: number; found: boolean }
// A pin appears once the frame has answered for it, so it pops in instead of flashing at 0,0.
const pos = computed(() => {
	const out: Record<string, Pos> = {}
	for (const n of visible.value) {
		const id = idOf(n)
		if (!(id in rects)) continue
		const r = rects[id]
		if (r) {
			last[n.id] = { x: r.x + n.offset.x * r.w, y: r.y + n.offset.y * r.h }
			out[n.id] = { ...last[n.id], found: true }
		} else {
			// Never seen this visit: fall back to where it was when the note was made.
			const l = last[n.id] ?? { x: n.rect.x + n.offset.x * n.rect.w, y: n.rect.y + n.offset.y * n.rect.h }
			out[n.id] = { ...l, found: false }
		}
	}
	return out
})
const shown = computed(() => visible.value.filter((n) => pos.value[n.id]))

function enter(n: Note) {
	// A dragged-box note redraws its box instead of outlining the container.
	pinHover.value = rects[idOf(n)] ? { id: idOf(n), box: n.box } : null
}
function click(n: Note, e: MouseEvent) {
	const p = pos.value[n.id]
	emit('open', n, p?.x ?? e.clientX, p?.y ?? e.clientY)
}
</script>

<template>
	<TransitionGroup
		enter-from-class="opacity-0 scale-[0.6] motion-reduce:scale-100"
		enter-active-class="transition duration-[160ms] ease-[cubic-bezier(0.34,1.56,0.64,1)] motion-reduce:transition-opacity"
	>
		<button
			v-for="n in shown"
			:key="n.id"
			:[UI_ATTR]="''"
			data-annotate-pin
			type="button"
			:aria-label="`Note ${numberOf(n)}: ${n.note}`"
			class="pointer-events-auto fixed z-[2147482995] flex size-6 -translate-x-1/2 -translate-y-[29px] items-center justify-center text-xs font-semibold tabular-nums text-white transition-transform duration-150 origin-[50%_29px] hover:scale-110 motion-reduce:transition-none motion-reduce:hover:scale-100"
			:class="pos[n.id]?.found === false && 'opacity-50'"
			:style="{ left: `${pos[n.id].x}px`, top: `${pos[n.id].y}px` }"
			@mousedown.prevent
			@mouseenter="enter(n)"
			@mouseleave="clearHover"
			@click.stop="click(n, $event)"
		>
			<!-- A map pin: a square rounded on three corners, turned so the sharp one points at the spot. -->
			<span
				class="absolute inset-0 rotate-45 rounded-full rounded-br-none shadow ring-2 ring-surface-base transition-colors duration-150"
				:class="n.sent ? 'bg-surface-gray-6' : 'bg-surface-blue-7'"
				aria-hidden="true"
			/>
			<!-- The pin being edited: a 2px ring in its own colour, 2px off the edge. -->
			<span
				v-if="selected === n.id"
				class="pointer-events-none absolute -inset-1 rotate-45 rounded-full rounded-br-none border-2"
				:class="n.sent ? 'border-outline-gray-5' : 'border-outline-blue-6'"
				aria-hidden="true"
			/>
			<span class="relative">{{ numberOf(n) }}</span>
		</button>
	</TransitionGroup>
</template>
