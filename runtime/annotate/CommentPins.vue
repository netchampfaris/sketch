<script setup lang="ts">
// One avatar pin per thread on this page, in Comment mode only. Each follows its element, re-resolved
// by selector on every scroll, resize, route change and (throttled) DOM change, like the note pins.
// Pins that land on each other fan out sideways, so every one of them stays reachable by pointer;
// the panel lists them all as well.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { UI_ATTR, hoverEl, hoverFrac, hoverLabel, isOurs, resolve, tagOf } from './annotate'
import { matching, openThread, type Thread } from './comments'
import AuthorAvatar from './AuthorAvatar.vue'

const props = defineProps<{ route: string }>()
const emit = defineEmits<{ open: [thread: Thread, x: number, y: number] }>()

// Pins follow the panel's filter, so a search narrows the page as well.
const visible = computed(() => matching.value.filter((t) => t.anchor.route === props.route))
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

let raf = 0
function schedule() {
	if (raf) return
	raf = requestAnimationFrame(() => {
		raf = 0
		measure()
	})
}
useEventListener(window, 'scroll', schedule, { capture: true, passive: true })
useEventListener(window, 'resize', schedule)

let mo: MutationObserver | null = null
let wait = 0
onMounted(() => {
	measure()
	mo = new MutationObserver((list) => {
		if (list.every((m) => isOurs(m.target))) return
		if (wait) return
		wait = window.setTimeout(() => {
			wait = 0
			schedule()
		}, 120)
	})
	mo.observe(document.body, { childList: true, subtree: true })
})
onBeforeUnmount(() => {
	mo?.disconnect()
	cancelAnimationFrame(raf)
	clearTimeout(wait)
	hoverEl.value = null
	hoverFrac.value = null
})
watch([visible, () => props.route], () => schedule(), { flush: 'post' })

const shown = computed(() => visible.value.filter((t) => pos.value[t.id]))
function enter(t: Thread) {
	const el = resolve(t.anchor.selector)
	hoverEl.value = el
	hoverLabel.value = el ? tagOf(el) : ''
	hoverFrac.value = el && t.anchor.box ? t.anchor.box : null
}
function leave() {
	hoverEl.value = null
	hoverFrac.value = null
}
function click(t: Thread, e: MouseEvent) {
	const p = pos.value[t.id]
	emit('open', t, p?.x ?? e.clientX, p?.y ?? e.clientY)
}
const label = (t: Thread) => `Comment from @${t.author}${t.replies.length ? `, ${t.replies.length} ${t.replies.length === 1 ? 'reply' : 'replies'}` : ''}: ${t.text.slice(0, 80)}`
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
			class="group pointer-events-auto fixed flex size-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full transition-transform duration-150 hover:z-[62] hover:scale-110 focus-visible:z-[62] motion-reduce:transition-none motion-reduce:hover:scale-100"
			:class="[openThread === t.id ? 'z-[62]' : 'z-[60]', pos[t.id]?.found === false && 'opacity-50', t.resolved && 'opacity-60']"
			:style="{ left: `${pos[t.id].x}px`, top: `${pos[t.id].y}px` }"
			@mouseenter="enter(t)"
			@mouseleave="leave"
			@click.stop="click(t, $event)"
		>
			<span
				class="rounded-full shadow ring-2 transition-colors duration-150"
				:class="openThread === t.id ? 'ring-outline-blue-6' : 'ring-surface-base'"
			>
				<AuthorAvatar :username="t.author" size="md" />
			</span>
		</button>
	</TransitionGroup>
</template>
