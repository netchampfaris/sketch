<script setup lang="ts">
// Numbered markers on the page. Each follows its element: re-resolved by selector on every
// scroll, resize, route change and (throttled) DOM change. A pin whose element has gone
// stays where it last was, faded. Sent notes turn gray.
import { computed, ref } from 'vue'
import { UI_ATTR, hoverEl, hoverFrac, hoverLabel, notes, resolveNote, tagOf, type Note } from './annotate'
import { clearHover, usePinTracking } from './pinTracking'

const props = defineProps<{ route: string; selected?: string }>()
const emit = defineEmits<{ open: [note: Note, x: number, y: number] }>()

// Notes on canvas tiles have their pins on the canvas (TilePins.vue).
const visible = computed(() => notes.value.filter((n) => n.route === props.route && !n.tile))
type Pos = { x: number; y: number; found: boolean }
const pos = ref<Record<string, Pos>>({})
// A pin appears once it has a position, so it pops in instead of flashing at 0,0.
// Numbered by position among this page's notes, never stored: deleting one renumbers the rest.
const numberOf = (n: Note) => visible.value.findIndex((x) => x.id === n.id) + 1
const shown = computed(() => visible.value.filter((n) => pos.value[n.id]))
const last: Record<string, { x: number; y: number }> = {}

function measure() {
	const next: Record<string, Pos> = {}
	for (const n of visible.value) {
		const el = resolveNote(n)
		if (el) {
			const r = el.getBoundingClientRect()
			last[n.id] = { x: r.left + n.offset.x * r.width, y: r.top + n.offset.y * r.height }
			next[n.id] = { ...last[n.id], found: true }
		} else {
			// Never seen this session: fall back to where it was when the note was made.
			const l = last[n.id] ?? { x: n.rect.x + n.offset.x * n.rect.w, y: n.rect.y + n.offset.y * n.rect.h }
			next[n.id] = { ...l, found: false }
		}
	}
	pos.value = next
}

usePinTracking(measure, [visible, () => props.route])

function enter(n: Note) {
	const el = resolveNote(n)
	hoverEl.value = el
	hoverLabel.value = el ? tagOf(el) : ''
	// A dragged-box note redraws its box instead of outlining the container.
	hoverFrac.value = el && n.box ? n.box : null
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
			class="pointer-events-auto fixed z-[60] flex size-6 -translate-x-1/2 -translate-y-[29px] items-center justify-center text-xs font-semibold tabular-nums text-white transition-transform duration-150 origin-[50%_29px] hover:scale-110 motion-reduce:transition-none motion-reduce:hover:scale-100"
			:class="pos[n.id]?.found === false && 'opacity-50'"
			:style="{ left: `${pos[n.id].x}px`, top: `${pos[n.id].y}px` }"
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
