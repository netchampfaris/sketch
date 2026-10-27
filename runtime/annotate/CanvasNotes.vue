<script setup lang="ts">
// The canvas panel's Notes tab, for the owner: search, then every note, "This view" first, then a header per page.
// A note on a tile that has gone sits last, under "Removed from canvas".
import { computed, ref } from 'vue'
import { Button, ScrollArea, TextInput } from 'frappe-ui'
import { bridge, findTile, tileExists, tileLabel } from 'sketch:variants'
import { pageName } from './comments'
import { noteNumber, notes, type Note } from './annotate'

defineProps<{ selected?: string }>()
const emit = defineEmits<{ choose: [note: Note, el: HTMLElement] }>()

const query = ref('')

const spotOf = (n: Note) => (n.tile ? { route: n.route, tile: n.tile } : null)
const matches = computed(() => {
	const q = query.value.trim().toLowerCase()
	return notes.value.filter((n) => !q || [n.note, n.component, n.tile?.optionLabel ?? '', n.tile?.group ?? ''].some((w) => w.toLowerCase().includes(q)))
})
function placeOf(n: Note): 'here' | 'elsewhere' | 'removed' | 'page' {
	const spot = spotOf(n)
	if (!spot) return 'page'
	if (tileExists(bridge.model, spot) === false) return 'removed'
	return findTile(bridge.tiles, spot, bridge.view) ? 'here' : 'elsewhere'
}
const groups = computed(() => {
	const list = matches.value
	const here = list.filter((n) => placeOf(n) === 'here')
	const gone = list.filter((n) => placeOf(n) === 'removed')
	const by = new Map<string, Note[]>()
	for (const n of list) if (!here.includes(n) && !gone.includes(n)) by.set(n.route, [...(by.get(n.route) ?? []), n])
	return [
		...(here.length ? [{ key: 'here', name: 'This view', notes: here }] : []),
		...[...by].map(([r, ns]) => ({ key: r, name: ns[0].tile?.page || pageName(r), notes: ns })),
		...(gone.length ? [{ key: 'gone', name: 'Removed from canvas', notes: gone }] : []),
	]
})
const titleOf = (n: Note, g: { key: string }) => (n.tile ? tileLabel(n.tile, g.key === 'here') : n.component || n.element.split(/[.\s]/)[0] || 'Page')
</script>

<template>
	<div data-annotate-ui class="flex min-h-0 flex-col">
		<TextInput v-model="query" class="[&_input]:focus:ring-outline-gray-3" placeholder="Search" aria-label="Search notes" autocomplete="off">
			<template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
			<template #suffix>
				<Button v-if="query" class="-mr-[5px]" variant="ghost" size="xs" icon="lucide-x" aria-label="Clear search" @click="query = ''" />
			</template>
		</TextInput>
		<ScrollArea class="mt-1 min-h-0 shrink" style="max-height: calc(100dvh - 13rem)">
			<div class="w-[16.5rem] min-w-0">
				<div v-if="!notes.length" class="px-2 py-3">
					<p class="text-p-sm font-medium text-ink-gray-8">No notes yet</p>
					<p class="mt-0.5 text-p-sm text-ink-gray-5">Click a tile to leave a note for your agent.</p>
				</div>
				<p v-else-if="!matches.length" class="px-2 py-2 text-p-sm text-ink-gray-5">No notes match</p>
				<template v-else>
				<section v-for="g in groups" :key="g.key" class="flex flex-col gap-0.5" :aria-label="g.name">
					<p class="px-2 pb-1 pt-2 text-xs font-medium text-ink-gray-5">{{ g.name }}</p>
					<button
						v-for="n in g.notes"
						:key="n.id"
						type="button"
						:aria-current="selected === n.id ? 'true' : undefined"
						class="flex w-full shrink-0 items-start gap-2 rounded-[8px] px-2 py-1.5 text-left hover:bg-surface-gray-2"
						:class="[selected === n.id && 'bg-surface-gray-3 hover:bg-surface-gray-3', n.sent && 'opacity-60']"
						@click="emit('choose', n, $event.currentTarget as HTMLElement)"
					>
						<span
							class="mt-px flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums text-white"
							:class="n.sent ? 'bg-surface-gray-6' : 'bg-surface-blue-7'"
						>{{ noteNumber(n) }}</span>
						<span class="min-w-0 flex-1">
							<span class="block truncate text-p-sm font-medium text-ink-gray-8">{{ titleOf(n, g) }}</span>
							<span class="line-clamp-2 break-words text-p-sm text-ink-gray-6">{{ n.note }}</span>
						</span>
					</button>
				</section>
				</template>
			</div>
		</ScrollArea>
	</div>
</template>
