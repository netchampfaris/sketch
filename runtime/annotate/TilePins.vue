<script setup lang="ts">
// The pins on the canvas's tiles, in the world's own coordinates: a pin sits at a fraction of its tile, so it stays
// on the tile through pan, zoom, the panel closing and a new layout. The canvas draws this inside its scaled
// world; each pin undoes the zoom (`--inv`), so it keeps its size on screen. Comment pins show in Comment mode,
// note pins in Note mode, and none while browsing.
// Pins that land on each other fan out sideways, so every one of them stays reachable by pointer.
import { computed } from 'vue'
import { bridge, sameTile, spotOf, type TileSpot } from 'sketch:variants'
import { noteNumber, notes, type Note } from './annotate'
import { matching, openThread, spotOfThread, type Thread } from './comments'
import { canvasUi, handlers } from './tiles'
import PinShape from './PinShape.vue'

const props = defineProps<{ tiles: any[]; zoom: number; view: string }>()

// Within this many screen px two pins count as one pile; each further pin in a pile steps this far to the right.
const PILE = 20
const STEP = 14

type Item = { id: string; kind: 'comment' | 'note'; spot: TileSpot; fx: number; fy: number; thread?: Thread; note?: Note }
const items = computed<Item[]>(() => {
	if (bridge.tool === 'comment') {
		return matching.value.flatMap((t) => {
			const spot = spotOfThread(t)
			return spot ? [{ id: t.id, kind: 'comment' as const, spot, fx: t.anchor.offset.x, fy: t.anchor.offset.y, thread: t }] : []
		})
	}
	if (bridge.tool === 'note') {
		return notes.value.flatMap((n) => (n.tile ? [{ id: n.id, kind: 'note' as const, spot: { route: n.route, tile: n.tile }, fx: n.offset.x, fy: n.offset.y, note: n }] : []))
	}
	return []
})

const pins = computed(() => {
	const placed: { x: number; y: number }[] = []
	const out: (Item & { x: number; y: number; k: number })[] = []
	const byTile = new Map<string, any>()
	for (const t of props.tiles) {
		const s = spotOf(t, props.view)
		if (s) byTile.set(t.id, { t, s })
	}
	const tiles = [...byTile.values()]
	for (const it of items.value) {
		const hit = tiles.find((x) => sameTile(x.s, it.spot))
		if (!hit) continue
		const x = hit.t.x + it.fx * hit.t.w
		const y = hit.t.y + it.fy * hit.t.h
		const near = (p: { x: number; y: number }) => Math.abs(p.x - x) * props.zoom < PILE && Math.abs(p.y - y) * props.zoom < PILE
		const k = placed.filter(near).length
		placed.push({ x, y })
		out.push({ ...it, x, y, k })
	}
	return out
})

function open(p: Item & { k: number }, e: MouseEvent) {
	// The wrapper is a point at the pin's tip; the fan-out is on-screen px from there.
	const r = (e.currentTarget as HTMLElement).parentElement!.getBoundingClientRect()
	const x = r.left + p.k * STEP
	if (p.thread) handlers.thread?.(p.thread, x, r.top)
	else if (p.note) handlers.note?.(p.note, x, r.top)
}
const label = (p: Item) =>
	p.thread
		? `Comment from ${p.thread.name}${p.thread.replies.length ? `, ${p.thread.replies.length} ${p.thread.replies.length === 1 ? 'reply' : 'replies'}` : ''}: ${p.thread.text.slice(0, 80)}`
		: `Note ${noteNumber(p.note!)}: ${p.note!.note.slice(0, 80)}`
</script>

<template>
	<div data-ui data-annotate-ui class="pointer-events-none absolute left-0 top-0 z-30">
		<TransitionGroup enter-from-class="opacity-0" enter-active-class="transition-opacity duration-150 motion-reduce:transition-none">
			<div
				v-for="p in pins"
				:key="p.id"
				class="absolute size-0 origin-top-left"
				:class="p.thread ? (openThread === p.id ? 'z-10' : '') : canvasUi.noteId === p.id ? 'z-10' : ''"
				:style="{ left: `${p.x}px`, top: `${p.y}px`, transform: 'scale(var(--inv))' }"
			>
				<button
					type="button"
					data-annotate-pin
					:data-comment-pin="p.thread ? '' : undefined"
					:aria-label="label(p)"
					class="pointer-events-auto absolute left-0 top-0 flex -translate-x-1/2 items-center justify-center transition-transform duration-150 hover:z-10 hover:scale-110 focus-visible:z-10 motion-reduce:transition-none motion-reduce:hover:scale-100"
					:class="[p.kind === 'comment' ? 'size-7 origin-[50%_34px] -translate-y-[34px]' : 'size-6 origin-[50%_29px] -translate-y-[29px]', p.thread?.resolved && 'opacity-60', p.note?.sent && 'opacity-60']"
					:style="{ marginLeft: `${p.k * STEP}px` }"
					@click.stop="open(p, $event)"
				>
					<PinShape
						:kind="p.kind"
						:username="p.thread?.author"
						:number="p.note ? noteNumber(p.note) : undefined"
						:muted="p.thread ? p.thread.resolved : !!p.note?.sent"
						:selected="p.thread ? openThread === p.id : canvasUi.noteId === p.id"
					/>
				</button>
			</div>
		</TransitionGroup>
	</div>
</template>
