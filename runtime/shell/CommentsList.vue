<script setup lang="ts">
// The comments: one flat list, newest first, one row per thread. Nothing depends on the page or view in view, so a click
// never moves the list. Resolved ones show when asked for (ResolvedMenu.vue). A thread whose option or state has gone counts as
// resolved (comments.ts isGone). The live page's floating panel, the canvas panel's Comments tab and the phone sheet all draw this.
import { computed, nextTick, ref, watch } from 'vue'
import { Button, ScrollArea, Skeleton } from 'frappe-ui'
import { canvas } from './canvas'
import { load, matching, openThread, query, status, threads, type Thread } from './comments'
import CommentRow from './CommentRow.vue'
import { page } from './frame'
import { pageNameOf } from './host'

defineProps<{ embedded?: boolean; width: string; max: string }>()
const emit = defineEmits<{ choose: [thread: Thread, el: HTMLElement] }>()

const searching = computed(() => !!query.value.trim())
// Nothing to list, and why: nobody has commented, everything is resolved, or the search found nothing.
const empty = computed(() => {
	if (status.value !== 'ready' || matching.value.length) return null
	if (searching.value) return 'search'
	return threads.value.length ? 'resolved' : 'first'
})

const onCanvas = computed(() => canvas.open)
const nameOfRoute = (t: Thread) => t.anchor.tile?.page || pageNameOf(t.anchor.route)
// A row names its page when the prototype has more than one: what the page headers used to say.
const paged = computed(() => page.pages.length > 1)

// The open thread's row stays in view. A row that was clicked is already there, so nothing moves.
const area = ref<{ viewportElement: HTMLElement | null }>()
watch(
	openThread,
	async (id) => {
		if (!id) return
		await nextTick()
		const box = area.value?.viewportElement
		const row = box?.querySelector('[aria-current="true"]')
		if (!box || !row) return
		const b = box.getBoundingClientRect()
		const r = row.getBoundingClientRect()
		if (r.top < b.top) box.scrollTop -= b.top - r.top
		else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom
	},
	{ immediate: true, flush: 'post' },
)

// A phone has no hover or Escape; the words say what a finger does.
const touch = typeof matchMedia === 'function' && matchMedia('(hover: none)').matches
</script>

<template>
	<ScrollArea ref="area" class="mt-1 flex min-h-0 shrink flex-col" :style="{ maxHeight: max }">
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

			<div v-else-if="status === 'ready'" class="flex flex-col gap-0.5">
				<CommentRow v-for="t in matching" :key="t.id" :thread="t" :page="paged ? nameOfRoute(t) : undefined" :selected="openThread === t.id" @choose="emit('choose', t, $event)" />
			</div>
		</div>
	</ScrollArea>
</template>
