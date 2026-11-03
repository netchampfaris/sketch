<script setup lang="ts">
// One avatar pin per thread on this page, in Comment mode only, drawn by the shell over the frame
// (runtime/annotate/CommentPins.vue, by rects). Each follows its element as the frame re-measures it. Pins that
// land on each other fan out sideways, so every one of them stays reachable by pointer; the panel lists them all
// as well. A new comment typed and not sent stays as a Draft pin: a dashed outline and the author's avatar dimmed;
// clicking it reopens the box with the words.
import { computed, onBeforeUnmount } from 'vue'
import { UI_ATTR } from '../annotate/annotate'
import { heldDrafts, matching, openThread, plain, type HeldDraft, type Thread } from '../annotate/comments'
import { host } from '../annotate/host'
import AuthorAvatar from '../annotate/AuthorAvatar.vue'
import PinShape from '../annotate/PinShape.vue'
import { picksShown } from './variants'
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

// Within this distance two pins count as one pile; each further pin in a pile steps to the right.
const PILE = 20
const STEP = 22

type Pos = { x: number; y: number; found: boolean }
const last: Record<string, { x: number; y: number }> = {}
const pos = computed(() => {
	const next: Record<string, Pos> = {}
	const placed: { x: number; y: number }[] = []
	for (const t of visible.value) {
		if (!(idOf(t) in rects)) continue
		const a = t.anchor
		const r = rects[idOf(t)]
		let at: { x: number; y: number }
		if (r) {
			at = { x: r.x + a.offset.x * r.w, y: r.y + a.offset.y * r.h }
			last[t.id] = at
		} else at = last[t.id] ?? { x: a.rect.x + a.offset.x * a.rect.w, y: a.rect.y + a.offset.y * a.rect.h }
		const k = placed.filter((p) => Math.abs(p.x - at.x) < PILE && Math.abs(p.y - at.y) < PILE).length
		placed.push(at)
		next[t.id] = { x: at.x + k * STEP, y: at.y, found: !!r }
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
			:[UI_ATTR]="''"
			data-annotate-pin
			data-comment-pin
			type="button"
			:aria-label="label(t)"
			class="pointer-events-auto fixed flex size-7 origin-[50%_34px] -translate-x-1/2 -translate-y-[34px] items-center justify-center transition-transform duration-150 hover:z-[2147482997] hover:scale-110 focus-visible:z-[2147482997] motion-reduce:transition-none motion-reduce:hover:scale-100"
			:class="[openThread === t.id ? 'z-[2147482997]' : 'z-[2147482995]', (pos[t.id]?.found === false || !picksShown(t.anchor.picks)) && 'opacity-50', t.resolved && 'opacity-60']"
			:style="{ left: `${pos[t.id].x}px`, top: `${pos[t.id].y}px` }"
			@mousedown.prevent
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
		<button
			v-for="h in drafts.filter((d) => heldPos[d.id])"
			:key="h.id"
			:[UI_ATTR]="''"
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
