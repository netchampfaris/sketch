<script setup lang="ts">
// One thread in a list: who, when, the first line, and the replies. Used by the live page's floating panel,
// the canvas panel's Comments tab and the phone sheet. `place` names the canvas tile a thread sits on.
import { ago, firstLine, type Thread } from './comments'
import AuthorAvatar from './AuthorAvatar.vue'

defineProps<{ thread: Thread; selected: boolean; place?: string }>()
const emit = defineEmits<{ choose: [el: HTMLElement] }>()
const replies = (n: number) => `${n} ${n === 1 ? 'reply' : 'replies'}`
</script>

<template>
	<button
		type="button"
		:title="`${thread.name}: ${firstLine(thread.text)}`"
		:aria-current="selected ? 'true' : undefined"
		class="flex w-full shrink-0 items-start gap-2 rounded-[8px] px-2 py-1.5 text-left hover:bg-surface-gray-2"
		:class="[selected && 'bg-surface-gray-3 hover:bg-surface-gray-3', thread.resolved && 'opacity-60']"
		@click="emit('choose', $event.currentTarget as HTMLElement)"
	>
		<span class="flex shrink-0"><AuthorAvatar :username="thread.author" size="sm" /></span>
		<span class="min-w-0 flex-1">
			<span class="flex items-center gap-2">
				<span class="flex min-w-0 flex-1 items-center gap-1.5 text-p-sm">
					<span class="min-w-0 truncate font-medium text-ink-gray-8">{{ thread.name }}</span>
					<span v-if="thread.noAccess" class="shrink-0 text-ink-gray-5">No access</span>
				</span>
				<span v-if="thread.mentioned" class="lucide-at-sign size-3 shrink-0 text-ink-gray-5" role="img" aria-label="Mentions you" title="Mentions you" />
				<span v-if="thread.unread" class="size-1.5 shrink-0 rounded-full bg-surface-blue-6" role="img" :aria-label="`${thread.unread} unread`" />
				<span class="w-10 shrink-0 text-right text-p-sm tabular-nums text-ink-gray-5">{{ ago(thread.ts) }}</span>
			</span>
			<span class="flex items-center gap-2">
				<span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-6">{{ firstLine(thread.text) }}</span>
				<span class="flex h-5 w-10 shrink-0 items-center justify-end gap-0.5 text-p-sm tabular-nums text-ink-gray-5" :aria-label="replies(thread.replies.length)">
					<template v-if="thread.replies.length">
						<span class="lucide-message-circle size-3" aria-hidden="true" />{{ thread.replies.length }}
					</template>
				</span>
			</span>
			<span v-if="place" class="block truncate text-xs text-ink-gray-5">{{ place }}</span>
		</span>
	</button>
</template>
