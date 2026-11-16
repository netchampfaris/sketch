<script setup lang="ts">
// A pin's body: the map-pin shape (a square rounded on three corners, turned so the sharp one points at the spot),
// a ring when its box is open, and what sits in it: a person's avatar for a comment, a number for a note.
// Comment pins are the reader's blue-on-avatar pin; note pins are violet, the owner's colour, like Tweak. A comment typed
// and not sent is a Draft: a dashed outline on the page's own surface, the avatar dimmed. The selected pin is lifted, not
// ringed: the pin's wrapper scales it from the tip, and the body's shadow deepens here.
import AuthorAvatar from './AuthorAvatar.vue'

defineProps<{ kind: 'comment' | 'note'; username?: string; number?: number; muted?: boolean; selected?: boolean; draft?: boolean }>()
</script>

<template>
	<span
		v-if="draft"
		class="absolute inset-0 rotate-45 rounded-full rounded-br-none border-2 border-dashed border-outline-blue-6 bg-surface-base shadow"
		aria-hidden="true"
	/>
	<span
		v-else
		class="absolute inset-0 rotate-45 rounded-full rounded-br-none ring-2 ring-[color:var(--surface-base)] transition duration-150 ease-out"
		:class="[selected ? 'shadow-lg' : 'shadow', muted ? 'bg-surface-gray-6' : kind === 'note' ? 'bg-surface-violet-7' : 'bg-surface-blue-7']"
		aria-hidden="true"
	/>
	<span v-if="kind === 'comment'" class="relative flex" :class="draft && 'opacity-50'"><AuthorAvatar :username="username ?? ''" size="sm" /></span>
	<span v-else class="relative text-xs font-semibold tabular-nums text-white">{{ number }}</span>
</template>
