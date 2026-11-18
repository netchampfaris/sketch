<script setup lang="ts">
// One avatar pin per thread on this page, in Comment mode only, drawn by the shell over the frame from the rects
// it reports. Each follows its element as the frame re-measures it. Pins that
// would overlap another step to the right, side by side with a small gap, so every one of them stays reachable by
// pointer; the panel lists them all as well. A new comment typed and not sent stays as a Draft pin: a dashed outline and the author's avatar dimmed;
// clicking it reopens the box with the words.
import { computed, onBeforeUnmount } from 'vue'
import { heldDrafts, matching, openThread, plain, type HeldDraft, type Thread } from './comments'
import { host } from './host'
import AuthorAvatar from './AuthorAvatar.vue'
import PinShape from './PinShape.vue'
import { picksShown } from './canvas'
import { rects, track, type Target } from './frame'
import { clearHover, pinHover } from './pinHover'

const props = defineProps<{ route: string }>()
const emit = defineEmits<{ open: [thread: Thread, x: number, y: number]; draft: [id: string, x: number, y: number] }>()

// Pins follow the panel's filter, so a search narrows the page as well.
// Threads on canvas tiles have their pins on the canvas.
const visible = computed(() => matching.value.filter((t) => t.anchor.route === props.route && !t.anchor.tile))
const drafts = computed(() => heldDrafts.value.filter((h) => h.anchor.route === props.route && !h.anchor.tile))
const idOf = (t: Thread) => `thread:${t.id}`
const heldId = (h: HeldDraft) => `held:${h.id}`
onBeforeUnmount(
	track(() =>
		Object.fromEntries([
			...visible.value.map((t): [string, Target] => [idOf(t), { sel: t.anchor.selector }]),
			...drafts.value.map((h): [string, Target] => [heldId(h), { sel: h.anchor.selector }]),
		]),
	),
)
onBeforeUnmount(clearHover)

// A pin is 28px with its 2px ring on each side. One that would overlap an earlier pin steps right by this much,
// the pin's width and a 4px gap, until it is clear.
const WIDTH = 32
const STEP = WIDTH + 4

type Pos = { x: number; y: number; found: boolean }
const last: Record<string, { x: number; y: number }> = {}
const pos = computed(() => {
	const next: Record<string, Pos> = {}
	const placed: { x: number; y: number }[] = []
	const blocker = (x: number, y: number) => placed.find((p) => Math.abs(p.x - x) < WIDTH && Math.abs(p.y - y) < WIDTH)
	for (const t of visible.value) {
		if (!(idOf(t) in rects)) continue
		const a = t.anchor
		const r = rects[idOf(t)]
		let at: { x: number; y: number }
		if (r) {
			at = { x: r.x + a.offset.x * r.w, y: r.y + a.offset.y * r.h }
			last[t.id] = at
		} else at = last[t.id] ?? { x: a.rect.x + a.offset.x * a.rect.w, y: a.rect.y + a.offset.y * a.rect.h }
		let x = at.x
		for (let hit = blocker(x, at.y); hit; hit = blocker(x, at.y)) x = hit.x + STEP
		placed.push({ x, y: at.y })
		next[t.id] = { x, y: at.y, found: !!r }
	}
	return next
})
const heldPos = computed(() => {
	const held: Record<string, Pos> = {}
	for (const h of drafts.value) {
		if (!(heldId(h) in rects)) continue
		const a = h.anchor
		const r = rects[heldId(h)]
		held[h.id] = r ? { x: r.x + a.offset.x * r.w, y: r.y + a.offset.y * r.h, found: true } : { x: a.rect.x + a.offset.x * a.rect.w, y: a.rect.y + a.offset.y * a.rect.h, found: false }
	}
	return held
})

const shown = computed(() => visible.value.filter((t) => pos.value[t.id]))
function enter(t: Thread) {
	pinHover.value = rects[idOf(t)] ? { id: idOf(t), box: t.anchor.box } : null
}
function click(t: Thread, e: MouseEvent) {
	const p = pos.value[t.id]
	emit('open', t, p?.x ?? e.clientX, p?.y ?? e.clientY)
}
function reopen(h: HeldDraft) {
	const p = heldPos.value[h.id]
	if (p) emit('draft', h.id, p.x, p.y)
}
const label = (t: Thread) => `Comment from ${t.name}${t.replies.length ? `, ${t.replies.length} ${t.replies.length === 1 ? 'reply' : 'replies'}` : ''}: ${plain(t.text).slice(0, 80)}`
</script>

<template>
	<TransitionGroup
		enter-from-class="opacity-0 scale-[0.6] motion-reduce:scale-100"
		enter-active-class="transition duration-[160ms] ease-[cubic-bezier(0.34,1.56,0.64,1)] motion-reduce:transition-opacity"
	>
		<button
			v-for="t in shown"
			:key="t.id"
			data-annotate-pin
			data-comment-pin
			type="button"
			:aria-label="label(t)"
			class="pointer-events-auto fixed flex size-7 origin-[50%_34px] -translate-x-1/2 -translate-y-[34px] items-center justify-center transition-transform duration-150 ease-out hover:z-[2147482997] focus-visible:z-[2147482997] motion-reduce:transition-none"
			:class="[openThread === t.id ? 'z-[2147482997] scale-[1.15] motion-reduce:scale-100' : 'z-[2147482995] hover:scale-110 motion-reduce:hover:scale-100', (pos[t.id]?.found === false || !picksShown(t.anchor.picks)) && 'opacity-50', t.resolved && 'opacity-60']"
			:style="{ left: `${pos[t.id].x}px`, top: `${pos[t.id].y}px` }"
			@mousedown.prevent
			@mouseenter="enter(t)"
			@mouseleave="clearHover"
			@click.stop="click(t, $event)"
		>
			<!-- The note pin's shape, so the tip is the spot and the words beside it stay readable; the avatar sits in it.
			     The thread being read is the same pin lifted: scaled from its tip, with a deeper shadow. -->
			<span
				class="absolute inset-0 rotate-45 rounded-full rounded-br-none ring-2 ring-[color:var(--surface-base)] transition duration-150 ease-out"
				:class="[openThread === t.id ? 'shadow-lg' : 'shadow', t.resolved ? 'bg-surface-gray-6' : 'bg-surface-blue-7']"
				aria-hidden="true"
			/>
			<span class="relative flex"><AuthorAvatar :username="t.author" size="sm" /></span>
		</button>
		<button
			v-for="h in drafts.filter((d) => heldPos[d.id])"
			:key="h.id"
			data-annotate-pin
			data-held-draft
			type="button"
			:aria-label="`Draft comment: ${h.text.slice(0, 80)}`"
			class="pointer-events-auto fixed z-[2147482995] flex size-7 origin-[50%_34px] -translate-x-1/2 -translate-y-[34px] items-center justify-center transition-transform duration-150 hover:z-[2147482997] hover:scale-110 focus-visible:z-[2147482997] motion-reduce:transition-none motion-reduce:hover:scale-100"
			:style="{ left: `${heldPos[h.id].x}px`, top: `${heldPos[h.id].y}px` }"
			@mousedown.prevent
			@click.stop="reopen(h)"
		>
			<PinShape kind="comment" :username="host.me" draft />
		</button>
	</TransitionGroup>
</template>
