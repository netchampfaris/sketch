<script setup lang="ts">
// The canvas panel's Comments tab: search, then the same list the live page shows. Registered with the canvas
// by the toolbar (Annotate.vue), so the panel draws it without importing comments.
import { Button, TextInput } from 'frappe-ui'
import { query, type Thread } from './comments'
import CommentsList from './CommentsList.vue'

defineProps<{ route: string }>()
const emit = defineEmits<{ choose: [thread: Thread, el: HTMLElement] }>()
</script>

<template>
	<div data-annotate-ui class="flex min-h-0 flex-col">
		<TextInput v-model="query" class="[&_input]:focus:ring-outline-gray-3" placeholder="Search" aria-label="Search comments by text or name" autocomplete="off">
			<template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
			<template #suffix>
				<Button v-if="query" class="-mr-[5px]" variant="ghost" size="xs" icon="lucide-x" aria-label="Clear search" @click="query = ''" />
			</template>
		</TextInput>
		<CommentsList :route="route" width="16.5rem" max="calc(100dvh - 13rem)" @choose="(t, el) => emit('choose', t, el)" />
	</div>
</template>
