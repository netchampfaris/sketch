<script setup lang="ts">
// The comments list: search, "Show resolved", then one row per thread. A floating card on the right on
// desktop, drawn like the canvas Show panel; inside a bottom sheet on a phone (`embedded`).
import { computed } from 'vue'
import { Button, ScrollArea, Skeleton, TextInput, Tooltip } from 'frappe-ui'
import { ago, firstLine, load, matching, openCount, openThread, query, resolvedCount, showResolved, status, threads, type Thread } from './comments'
import AuthorAvatar from './AuthorAvatar.vue'

defineProps<{ embedded?: boolean }>()
const emit = defineEmits<{ choose: [thread: Thread]; hide: [] }>()

const searching = computed(() => !!query.value.trim())
// Nothing to list, and why: nobody has commented, everything is resolved, or the search found nothing.
const empty = computed(() => {
	if (status.value !== 'ready' || matching.value.length) return null
	if (searching.value) return 'search'
	return threads.value.length ? 'resolved' : 'first'
})
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
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
			<TextInput v-model="query" class="min-w-0 flex-1 [&_input]:focus:ring-outline-gray-3" placeholder="Search" aria-label="Search comments by text or @user" autocomplete="off">
				<template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
			</TextInput>
			<Tooltip v-if="!embedded" text="Hide panel">
				<Button variant="ghost" icon="lucide-panel-right" aria-label="Hide panel" @click="emit('hide')" />
			</Tooltip>
		</div>

		<!-- Resolved threads stay out of the way until asked for. -->
		<div v-if="resolvedCount || showResolved" class="mt-1 flex h-7 items-center gap-1 px-2">
			<span class="text-xs font-medium text-ink-gray-5">{{ plural(openCount, 'open thread') }}</span>
			<Button class="ml-auto" size="sm" :variant="showResolved ? 'subtle' : 'ghost'" :label="showResolved ? `Hide resolved` : `Show resolved (${resolvedCount})`" :aria-pressed="showResolved" @click="showResolved = !showResolved" />
		</div>

		<ScrollArea class="mt-1 min-h-0 shrink" :style="embedded ? { maxHeight: 'calc(100dvh - 11rem)' } : { maxHeight: 'var(--comments-list-max, 60vh)' }">
			<!-- A fixed width: the scroll area sizes its content to the widest row, which would push long names out of the card. -->
			<div :style="{ width: embedded ? 'calc(100vw - 2.5rem)' : '17rem' }" class="min-w-0">
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
					<p class="mt-0.5 text-p-sm text-ink-gray-5">Click anything on the page to start a thread.</p>
				</div>
				<p v-else-if="empty === 'search'" class="px-2 py-2 text-p-sm text-ink-gray-5">No comments match</p>
				<div v-else-if="empty === 'resolved'" class="px-2 py-3">
					<p class="text-p-sm font-medium text-ink-gray-8">Nothing left open</p>
					<p class="mt-0.5 text-p-sm text-ink-gray-5">Every thread is resolved.</p>
				</div>

				<template v-else-if="status === 'ready'">
					<button
						v-for="t in matching"
						:key="t.id"
						type="button"
						:title="`@${t.author}: ${firstLine(t.text)}`"
						:aria-current="openThread === t.id ? 'true' : undefined"
						class="flex w-full items-start gap-2 rounded-[8px] px-2 py-1.5 text-left hover:bg-surface-gray-2"
						:class="[openThread === t.id && 'bg-surface-gray-3', t.resolved && 'opacity-60']"
						@click="emit('choose', t)"
					>
						<span class="mt-px shrink-0"><AuthorAvatar :username="t.author" size="sm" /></span>
						<span class="min-w-0 flex-1">
							<span class="flex items-baseline gap-2">
								<span class="min-w-0 flex-1 truncate text-p-sm font-medium text-ink-gray-8">@{{ t.author }}</span>
								<span class="w-10 shrink-0 text-right text-p-sm tabular-nums text-ink-gray-5">{{ ago(t.ts) }}</span>
							</span>
							<span class="flex items-baseline gap-2">
								<span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-6">{{ firstLine(t.text) }}</span>
								<span class="flex w-10 shrink-0 items-center justify-end gap-0.5 text-p-sm tabular-nums text-ink-gray-5" :aria-label="plural(t.replies.length, 'reply')">
									<template v-if="t.replies.length">
										<span class="lucide-message-circle size-3" aria-hidden="true" />{{ t.replies.length }}
									</template>
								</span>
							</span>
						</span>
					</button>
				</template>
			</div>
		</ScrollArea>
	</component>
</template>
