<script setup lang="ts">
// One avatar pin per thread on this page, in Comment mode only. Each follows its element, re-resolved
// by selector on every scroll, resize, route change and (throttled) DOM change, like the note pins.
// Pins that land on each other fan out sideways, so every one of them stays reachable by pointer;
// the panel lists them all as well.
import { computed, ref } from 'vue'
import { UI_ATTR, hoverEl, hoverFrac, hoverLabel, resolve, tagOf } from './annotate'
import { clearHover, usePinTracking } from './pinTracking'
import { matching, openThread, type Thread } from './comments'
import AuthorAvatar from './AuthorAvatar.vue'

const props = defineProps<{ route: string }>()
const emit = defineEmits<{ open: [thread: Thread, x: number, y: number] }>()

// Pins follow the panel's filter, so a search narrows the page as well.
// Threads on canvas tiles have their pins on the canvas (TilePins.vue).
const visible = computed(() => matching.value.filter((t) => t.anchor.route === props.route && !t.anchor.tile))
type Pos = { x: number; y: number; found: boolean }
const pos = ref<Record<string, Pos>>({})
const last: Record<string, { x: number; y: number }> = {}

// Within this distance two pins count as one pile; each further pin in a pile steps to the right.
const PILE = 20
const STEP = 14

function measure() {
	const next: Record<string, Pos> = {}
	const placed: { x: number; y: number }[] = []
	for (const t of visible.value) {
		const a = t.anchor
		const el = resolve(a.selector)
		let at: { x: number; y: number }
		if (el) {
			const r = el.getBoundingClientRect()
			at = { x: r.left + a.offset.x * r.width, y: r.top + a.offset.y * r.height }
			last[t.id] = at
		} else {
			at = last[t.id] ?? { x: a.rect.x + a.offset.x * a.rect.w, y: a.rect.y + a.offset.y * a.rect.h }
		}
		const k = placed.filter((p) => Math.abs(p.x - at.x) < PILE && Math.abs(p.y - at.y) < PILE).length
		placed.push(at)
		next[t.id] = { x: at.x + k * STEP, y: at.y, found: !!el }
	}
	pos.value = next
}

usePinTracking(measure, [visible, () => props.route])

const shown = computed(() => visible.value.filter((t) => pos.value[t.id]))
function enter(t: Thread) {
	const el = resolve(t.anchor.selector)
	hoverEl.value = el
	hoverLabel.value = el ? tagOf(el) : ''
	hoverFrac.value = el && t.anchor.box ? t.anchor.box : null
}
function click(t: Thread, e: MouseEvent) {
	const p = pos.value[t.id]
	emit('open', t, p?.x ?? e.clientX, p?.y ?? e.clientY)
}
const label = (t: Thread) => `Comment from ${t.name}${t.replies.length ? `, ${t.replies.length} ${t.replies.length === 1 ? 'reply' : 'replies'}` : ''}: ${t.text.slice(0, 80)}`
</script>

<template>
	<TransitionGroup
		enter-from-class="opacity-0 scale-[0.6] motion-reduce:scale-100"
		enter-active-class="transition duration-[160ms] ease-[cubic-bezier(0.34,1.56,0.64,1)] motion-reduce:transition-opacity"
	>
		<button
			v-for="t in shown"
			:key="t.id"
			:[UI_ATTR]="''"
			data-annotate-pin
			data-comment-pin
			type="button"
			:aria-label="label(t)"
			class="pointer-events-auto fixed flex size-7 origin-[50%_34px] -translate-x-1/2 -translate-y-[34px] items-center justify-center transition-transform duration-150 hover:z-[62] hover:scale-110 focus-visible:z-[62] motion-reduce:transition-none motion-reduce:hover:scale-100"
			:class="[openThread === t.id ? 'z-[62]' : 'z-[60]', pos[t.id]?.found === false && 'opacity-50', t.resolved && 'opacity-60']"
			:style="{ left: `${pos[t.id].x}px`, top: `${pos[t.id].y}px` }"
			@mouseenter="enter(t)"
			@mouseleave="clearHover"
			@click.stop="click(t, $event)"
		>
			<!-- The note pin's shape, so the tip is the spot and the words beside it stay readable; the avatar sits in it. -->
			<span
				class="absolute inset-0 rotate-45 rounded-full rounded-br-none shadow ring-2 ring-surface-base transition-colors duration-150"
				:class="t.resolved ? 'bg-surface-gray-6' : 'bg-surface-blue-7'"
				aria-hidden="true"
			/>
			<!-- The thread being read: a 2px ring in the pin's own colour, 2px off the edge. -->
			<span
				v-if="openThread === t.id"
				class="pointer-events-none absolute -inset-1 rotate-45 rounded-full rounded-br-none border-2 border-outline-blue-6"
				aria-hidden="true"
			/>
			<span class="relative flex"><AuthorAvatar :username="t.author" size="sm" /></span>
		</button>
	</TransitionGroup>
</template>
