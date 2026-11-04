<script setup lang="ts">
// The "Show" list: search, then the groups of things to show on the canvas: variant sets, and the pages that have states. The canvas panel holds it on desktop
// (CanvasPanel.vue), the title pill's dropdown on a phone (CanvasLayer.vue). The rows are what the frame's canvas
// reported; a dot is the server's word that an option is new to this person (badges.ts).
import { computed, nextTick, ref, watch } from 'vue'
import { ScrollArea, TextInput, Tooltip } from 'frappe-ui'
import type { PickItem } from '../shared/protocol'
import { freshIn } from './badges'

const props = defineProps<{ items: PickItem[]; selected: string; width: string; maxHeight?: string }>()
const emit = defineEmits<{ choose: [value: string] }>()

const GROUPS = [
	{ key: 'sets', title: 'Variant sets' },
	{ key: 'pages', title: 'States' },
] as const

const query = ref('')
const folded = ref<Record<string, boolean>>({})
const groups = computed(() => {
	const q = query.value.trim().toLowerCase()
	return GROUPS.map((g) => ({
		...g,
		items: props.items.filter((i) => i.group === g.key && (!q || `${i.label} ${i.sub ?? ''}`.toLowerCase().includes(q))),
	})).filter((g) => g.items.length)
})
const isFolded = (key: string) => !query.value.trim() && !!folded.value[key]
// Rows the arrow keys can reach, in order.
const rows = computed(() => groups.value.flatMap((g) => (isFolded(g.key) ? [] : g.items)))
const indexOf = (i: PickItem) => rows.value.indexOf(i)

const active = ref(-1)
watch([query, () => props.items], () => (active.value = query.value.trim() ? 0 : -1))
function move(d: number) {
	const n = rows.value.length
	if (!n) return
	const from = active.value < 0 ? rows.value.findIndex((r) => r.value === props.selected) : active.value
	active.value = (from + d + n) % n
	nextTick(() => document.querySelector(`[data-panel-row="${active.value}"]`)?.scrollIntoView({ block: 'nearest' }))
}
function enter() {
	const r = rows.value[active.value < 0 ? 0 : active.value]
	if (r) emit('choose', r.value)
}
// How many options of a set are new to this person and not looked at yet. A page's states have none.
const freshOf = (i: PickItem) => (i.options.length ? freshIn(i.options) : 0)
const countClass = (i: PickItem) => (i.value === props.selected ? 'text-ink-gray-7' : 'text-ink-gray-5')
</script>

<template>
	<div class="flex min-h-0 flex-col">
		<!-- The search row; the panel puts its hide button at the end. -->
		<div class="flex items-center gap-1">
			<TextInput
				v-model="query"
				class="min-w-0 flex-1 [&_input]:focus:ring-outline-gray-3"
				placeholder="Search"
				aria-label="Search variant sets and states"
				autocomplete="off"
				@keydown.down.prevent="move(1)"
				@keydown.up.prevent="move(-1)"
				@keydown.enter.prevent="enter"
			>
				<template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
			</TextInput>
			<slot name="end" />
		</div>

		<ScrollArea class="mt-2 min-h-0 shrink" :style="maxHeight ? { maxHeight } : undefined">
		<!-- A fixed width: the scroll area sizes its content to the widest row, which would push long names out of the card. -->
		<div :style="{ width }" class="min-w-0">
			<p v-if="!groups.length" class="px-2 py-2 text-p-sm text-ink-gray-5">Nothing matches “{{ query.trim() }}”</p>
			<section v-for="(g, gi) in groups" :key="g.key" class="flex flex-col gap-0.5" :class="gi ? 'mt-1' : ''">
				<button
					type="button"
					class="group flex h-7 w-full items-center gap-1 px-2 text-left text-xs font-medium text-ink-gray-5"
					:aria-expanded="!isFolded(g.key)"
					@click="folded[g.key] = !folded[g.key]"
				>
					<span class="truncate">{{ g.title }}</span>
					<span
						class="size-3 shrink-0 text-ink-gray-4 group-hover:opacity-100"
						:class="isFolded(g.key) ? 'lucide-chevron-right' : 'lucide-chevron-down opacity-0'"
						aria-hidden="true"
					/>
				</button>
				<template v-if="!isFolded(g.key)">
					<button
						v-for="i in g.items"
						:key="i.value"
						type="button"
						:data-panel-row="indexOf(i)"
						:aria-current="i.value === selected ? 'true' : undefined"
						:title="i.sub ? `${i.label} · ${i.sub}` : i.label"
						class="flex h-8 w-full shrink-0 items-center gap-1.5 rounded-[8px] px-2 text-left text-p-sm hover:bg-surface-gray-2"
						:class="i.value === selected ? 'bg-surface-gray-3 hover:bg-surface-gray-3' : indexOf(i) === active ? 'bg-surface-gray-2' : ''"
						@click="emit('choose', i.value)"
					>
						<span class="min-w-0 truncate" :class="i.value === selected ? 'font-medium text-ink-gray-9' : 'text-ink-gray-8'">{{ i.label }}</span>
						<span v-if="i.sub" class="shrink-0 text-ink-gray-5">{{ i.sub }}</span>
						<span v-if="freshOf(i)" class="ml-auto flex shrink-0 items-center pl-2">
							<Tooltip :text="`${freshOf(i)} new since you last looked`" :hover-delay="300">
								<span class="block size-1.5 rounded-full bg-surface-blue-6" role="img" :aria-label="`${freshOf(i)} new since you last looked`" />
							</Tooltip>
						</span>
						<span class="shrink-0 tabular-nums" :class="[countClass(i), freshOf(i) ? 'pl-1.5' : 'ml-auto pl-2']">{{ i.short }}</span>
					</button>
				</template>
			</section>
		</div>
	</ScrollArea>
	</div>
</template>
