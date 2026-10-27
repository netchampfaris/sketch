<script setup lang="ts">
// The comments list: search, the count and "Show resolved", then one row per thread, grouped by page. A floating card on the right on
// desktop, drawn like the canvas Show panel; inside a bottom sheet on a phone (`embedded`).
import { computed } from 'vue'
import { Button, ScrollArea, Skeleton, TextInput, Tooltip } from 'frappe-ui'
import { ago, firstLine, load, matching, openThread, pageName, query, resolvedCount, showResolved, status, threads, type Thread } from './comments'
import AuthorAvatar from './AuthorAvatar.vue'

const props = defineProps<{ embedded?: boolean; route: string }>()
const emit = defineEmits<{ choose: [thread: Thread]; hide: [] }>()

const searching = computed(() => !!query.value.trim())
// Nothing to list, and why: nobody has commented, everything is resolved, or the search found nothing.
const empty = computed(() => {
	if (status.value !== 'ready' || matching.value.length) return null
	if (searching.value) return 'search'
	return threads.value.length ? 'resolved' : 'first'
})
const replies = (n: number) => `${n} ${n === 1 ? 'reply' : 'replies'}`

// This page's threads first, then each other page's; within a page the list's own order (newest unresolved first).
// A header names the page only when threads sit on more than one.
const groups = computed(() => {
	const by = new Map<string, Thread[]>()
	for (const t of matching.value) by.set(t.anchor.route, [...(by.get(t.anchor.route) ?? []), t])
	const routes = [...by.keys()].sort((a, b) => Number(b === props.route) - Number(a === props.route))
	return routes.map((r) => ({ route: r, name: r === props.route ? 'This page' : pageName(r), threads: by.get(r)! }))
})
// A phone has no hover or Escape; the words say what a finger does.
const touch = typeof matchMedia === 'function' && matchMedia('(hover: none)').matches
</script>

<template>
	<component
		:is="embedded ? 'div' : 'aside'"
		:data-comments-panel="embedded ? undefined : ''"
		:aria-label="embedded ? undefined : 'Comments'"
		data-annotate-ui
		class="flex flex-col p-2"
		:class="embedded ? 'min-h-0' : 'pointer-events-auto w-72 overflow-hidden rounded-[16px] bg-surface-elevation-2 shadow-lg ring-1 ring-outline-gray-2'"
	>
		<div class="flex items-center gap-1">
			<TextInput v-model="query" class="min-w-0 flex-1 [&_input]:focus:ring-outline-gray-3" placeholder="Search" aria-label="Search comments by text or name" autocomplete="off">
				<template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
				<template #suffix>
					<Button v-if="query" class="-mr-[5px]" variant="ghost" size="xs" icon="lucide-x" aria-label="Clear search" @click="query = ''" />
				</template>
			</TextInput>
			<Tooltip v-if="!embedded" text="Hide panel">
				<Button variant="ghost" icon="lucide-panel-right" aria-label="Hide panel" @click="emit('hide')" />
			</Tooltip>
		</div>

		<!-- Resolved threads stay out of the way until asked for. The count is the toolbar button's. -->
		<div v-if="resolvedCount || showResolved" class="mt-1 flex h-7 items-center px-2">
			<Button class="-mr-2 ml-auto !text-xs !font-medium" size="sm" :variant="showResolved ? 'subtle' : 'ghost'" :aria-pressed="showResolved" @click="showResolved = !showResolved">
				{{ showResolved ? 'Hide resolved' : 'Show resolved' }}<span v-if="!showResolved" class="ml-1 tabular-nums text-ink-gray-5">{{ resolvedCount }}</span>
			</Button>
		</div>

		<ScrollArea class="mt-1 min-h-0 shrink" :style="embedded ? { maxHeight: 'calc(100dvh - 15rem)' } : { maxHeight: 'var(--comments-list-max, 60vh)' }">
			<!-- A fixed width: the scroll area sizes its content to the widest row, which would push long names out of the card.
				In the sheet the toolbar floats over the bottom, so the last row scrolls clear of it. -->
			<div :style="{ width: embedded ? 'calc(100vw - 1rem)' : '17rem' }" class="min-w-0" :class="embedded && 'pb-20'">
				<!-- Loading: one quiet row. -->
				<div v-if="status === 'loading' || status === 'idle'" class="flex items-start gap-2 px-2 py-1.5" role="status" aria-label="Loading comments">
					<Skeleton class="size-5 shrink-0 rounded-full" />
					<div class="min-w-0 flex-1 space-y-1.5 pt-0.5">
						<Skeleton class="h-3 w-24 rounded-[4px]" />
						<Skeleton class="h-3 w-40 rounded-[4px]" />
					</div>
				</div>

				<p v-else-if="status === 'error'" class="flex items-center gap-1 px-2 py-2 text-p-sm text-ink-red-3" role="alert">
					Couldn't load comments ·
					<Button variant="ghost" size="sm" label="Retry" @click="load()" />
				</p>

				<div v-else-if="empty === 'first'" class="px-2 py-3">
					<p class="text-p-sm font-medium text-ink-gray-8">No comments yet</p>
					<p class="mt-0.5 text-p-sm text-ink-gray-5">{{ touch ? 'Tap' : 'Click' }} anything on the page to start a thread.</p>
				</div>
				<p v-else-if="empty === 'search'" class="break-words px-2 py-2 text-p-sm text-ink-gray-5">No comments match “{{ query.trim() }}”</p>
				<p v-else-if="empty === 'resolved'" class="px-2 py-3 text-p-sm font-medium text-ink-gray-8">Nothing left open</p>

				<template v-else-if="status === 'ready'">
					<section v-for="g in groups" :key="g.route" class="flex flex-col gap-0.5" :aria-label="groups.length > 1 ? g.name : undefined">
						<p v-if="groups.length > 1" class="px-2 pb-1 pt-2 text-xs font-medium text-ink-gray-5">{{ g.name }}</p>
						<button
							v-for="t in g.threads"
							:key="t.id"
							type="button"
							:title="`${t.name}: ${firstLine(t.text)}`"
							:aria-current="openThread === t.id ? 'true' : undefined"
							class="flex w-full items-start gap-2 rounded-[8px] px-2 py-1.5 text-left hover:bg-surface-gray-2"
							:class="[openThread === t.id && 'bg-surface-gray-3', t.resolved && 'opacity-60']"
							@click="emit('choose', t)"
						>
							<span class="flex shrink-0"><AuthorAvatar :username="t.author" size="sm" /></span>
							<span class="min-w-0 flex-1">
								<span class="flex items-baseline gap-2">
									<span class="min-w-0 flex-1 truncate text-p-sm font-medium text-ink-gray-8">{{ t.name }}</span>
									<span class="w-10 shrink-0 text-right text-p-sm tabular-nums text-ink-gray-5">{{ ago(t.ts) }}</span>
								</span>
								<span class="flex items-center gap-2">
									<span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-6">{{ firstLine(t.text) }}</span>
									<span class="flex h-5 w-10 shrink-0 items-center justify-end gap-0.5 text-p-sm tabular-nums text-ink-gray-5" :aria-label="replies(t.replies.length)">
										<template v-if="t.replies.length">
											<span class="lucide-message-circle size-3" aria-hidden="true" />{{ t.replies.length }}
										</template>
									</span>
								</span>
							</span>
						</button>
					</section>
				</template>
			</div>
		</ScrollArea>
	</component>
</template>
