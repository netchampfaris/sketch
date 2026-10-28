<script setup lang="ts">
// The comments: one row per thread under a header per page. Resolved ones show when asked for (ResolvedMenu.vue).
// The canvas opens its own list first ("This view"). A thread whose option or state has gone counts as resolved
// (comments.ts isGone). The live page's floating panel, the canvas panel's Comments tab and the phone sheet all draw this.
import { computed } from 'vue'
import { Button, ScrollArea, Skeleton } from 'frappe-ui'
import { bridge, findTile } from 'sketch:variants'
import { load, matching, openThread, pageName, query, spotOfThread, status, threads, type Thread } from './comments'
import CommentRow from './CommentRow.vue'

const props = defineProps<{ route: string; embedded?: boolean; width: string; max: string }>()
const emit = defineEmits<{ choose: [thread: Thread, el: HTMLElement] }>()

const searching = computed(() => !!query.value.trim())
// Nothing to list, and why: nobody has commented, everything is resolved, or the search found nothing.
const empty = computed(() => {
	if (status.value !== 'ready' || matching.value.length) return null
	if (searching.value) return 'search'
	return threads.value.length ? 'resolved' : 'first'
})

type Group = { key: string; name: string; threads: Thread[] }
const onCanvas = computed(() => bridge.open)

// On the canvas, whether a thread sits on a tile in view.
function isHere(t: Thread) {
	const spot = spotOfThread(t)
	return !!spot && !!findTile(bridge.tiles, spot, bridge.view)
}
const pageOrder = (route: string) => {
	const i = bridge.model?.findIndex((p) => p.path === route) ?? -1
	return i < 0 ? 1e6 : i
}
const nameOfRoute = (t: Thread) => t.anchor.tile?.page || pageName(t.anchor.route)

const groups = computed<Group[]>(() => {
	const list = matching.value
	if (onCanvas.value) {
		const here = list.filter(isHere)
		const rest = list.filter((t) => !here.includes(t))
		const by = new Map<string, Thread[]>()
		for (const t of rest) by.set(t.anchor.route, [...(by.get(t.anchor.route) ?? []), t])
		const pages = [...by.keys()].sort((a, b) => pageOrder(a) - pageOrder(b))
		return [
			...(here.length ? [{ key: 'here', name: 'This view', threads: here }] : []),
			...pages.map((r) => ({ key: r, name: nameOfRoute(by.get(r)![0]), threads: by.get(r)! })),
		]
	}
	// This page's threads first, then each other page's; within a page the list's own order (newest unresolved first).
	const by = new Map<string, Thread[]>()
	for (const t of list) by.set(t.anchor.route, [...(by.get(t.anchor.route) ?? []), t])
	const routes = [...by.keys()].sort((a, b) => Number(b === props.route) - Number(a === props.route))
	return routes.map((r) => ({ key: r, name: r === props.route ? 'This page' : pageName(r), threads: by.get(r)! }))
})
// A header names the group when there is more than one, and always on the canvas, where "This view" is one of them.
const headers = computed(() => onCanvas.value || groups.value.length > 1)
// A view with no comments still gets its header, so the list does not start at another page without saying so.
const noneHere = computed(() => onCanvas.value && !searching.value && !groups.value.some((g) => g.key === 'here'))

// A phone has no hover or Escape; the words say what a finger does.
const touch = typeof matchMedia === 'function' && matchMedia('(hover: none)').matches
</script>

<template>
	<ScrollArea class="mt-1 min-h-0 shrink" :style="{ maxHeight: max }">
		<!-- A fixed width: the scroll area sizes its content to the widest row, which would push long names out of the card.
			In the sheet the toolbar floats over the bottom, so the last row scrolls clear of it. -->
		<div :style="{ width }" class="min-w-0" :class="embedded && 'pb-20'">
			<!-- Loading: one quiet row. -->
			<div v-if="status === 'loading' || status === 'idle'" class="flex items-start gap-2 px-2 py-1.5" role="status" aria-label="Loading comments">
				<Skeleton class="size-5 shrink-0 rounded-full" />
				<div class="min-w-0 flex-1 space-y-1.5 pt-0.5">
					<Skeleton class="h-3 w-24 rounded-[4px]" />
					<Skeleton class="h-3 w-40 rounded-[4px]" />
				</div>
			</div>

			<p v-else-if="status === 'error'" class="flex items-center gap-1 px-2 py-2 text-p-sm text-ink-red-7" role="alert">
				Couldn't load comments.
				<Button variant="ghost" size="sm" label="Retry" @click="load()" />
			</p>

			<div v-else-if="empty === 'first'" class="px-2 py-3">
				<p class="text-p-sm font-medium text-ink-gray-8">No comments yet</p>
				<p class="mt-0.5 text-p-sm text-ink-gray-5">{{ touch ? 'Tap' : 'Click' }} {{ onCanvas ? 'a tile' : 'anything on the page' }} to start a thread.</p>
			</div>
			<p v-else-if="empty === 'search'" class="break-words px-2 py-2 text-p-sm text-ink-gray-5">Nothing matches “{{ query.trim() }}”</p>
			<p v-else-if="empty === 'resolved'" class="px-2 py-3 text-p-sm font-medium text-ink-gray-8">Nothing left open</p>

			<template v-else-if="status === 'ready'">
				<section v-if="noneHere" class="flex flex-col gap-0.5" aria-label="This view">
					<p class="px-2 pb-1 pt-2 text-xs font-medium text-ink-gray-5">This view</p>
					<p class="px-2 py-1.5 text-p-sm text-ink-gray-5">No comments here yet</p>
				</section>
				<section v-for="g in groups" :key="g.key" class="flex flex-col gap-0.5" :aria-label="headers ? g.name : undefined">
					<p v-if="headers" class="px-2 pb-1 pt-2 text-xs font-medium text-ink-gray-5">{{ g.name }}</p>
					<CommentRow v-for="t in g.threads" :key="t.id" :thread="t" :selected="openThread === t.id" @choose="emit('choose', t, $event)" />
				</section>
			</template>
		</div>
	</ScrollArea>
</template>
