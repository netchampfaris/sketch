<script setup lang="ts">
// A pin's body: the map-pin shape (a square rounded on three corners, turned so the sharp one points at the spot),
// a ring when its box is open, and what sits in it: a person's avatar for a comment, a number for a note.
// Comment pins are the reader's blue-on-avatar pin; note pins are the owner's colour.
import AuthorAvatar from './AuthorAvatar.vue'

defineProps<{ kind: 'comment' | 'note'; username?: string; number?: number; muted?: boolean; selected?: boolean }>()
</script>

<template>
	<span
		class="absolute inset-0 rotate-45 rounded-full rounded-br-none shadow ring-2 ring-surface-base transition-colors duration-150"
		:class="muted ? 'bg-surface-gray-6' : 'bg-surface-blue-7'"
		aria-hidden="true"
	/>
	<span
		v-if="selected"
		class="pointer-events-none absolute -inset-1 rotate-45 rounded-full rounded-br-none border-2"
		:class="muted && kind === 'note' ? 'border-outline-gray-5' : 'border-outline-blue-6'"
		aria-hidden="true"
	/>
	<span v-if="kind === 'comment'" class="relative flex"><AuthorAvatar :username="username ?? ''" size="sm" /></span>
	<span v-else class="relative text-xs font-semibold tabular-nums text-white">{{ number }}</span>
</template>
