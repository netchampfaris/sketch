<script setup lang="ts">
// The live page's comments panel: search, the ⋯ menu (resolved threads), then the list. A floating card on the right on desktop, drawn like the
// canvas panel; inside a bottom sheet on a phone (`embedded`). The canvas does not mount this: its panel has a
// Comments tab that draws the same list (CommentsList.vue).
import { Button, TextInput, Tooltip } from 'frappe-ui'
import { query, type Thread } from './comments'
import CommentsList from './CommentsList.vue'
import ResolvedMenu from './ResolvedMenu.vue'

defineProps<{ embedded?: boolean; route: string }>()
const emit = defineEmits<{ choose: [thread: Thread, el: HTMLElement]; hide: [] }>()
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
			<ResolvedMenu />
			<Tooltip v-if="!embedded" text="Hide panel">
				<Button variant="ghost" icon="lucide-panel-right" aria-label="Hide panel" @click="emit('hide')" />
			</Tooltip>
		</div>

		<CommentsList
			:route="route"
			:embedded="embedded"
			:width="embedded ? 'calc(100vw - 1rem)' : '17rem'"
			:max="embedded ? 'calc(100dvh - 15rem)' : 'var(--comments-list-max, 60vh)'"
			@choose="(t, el) => emit('choose', t, el)"
		/>
	</component>
</template>
