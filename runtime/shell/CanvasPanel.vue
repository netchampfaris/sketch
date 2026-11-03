<script setup lang="ts">
// The canvas's panel on the right, drawn by the Viewer shell over the frame's canvas. Browse is the "Show" list
// (ShowList.vue, which the phone's title pill opens too). Next to it Comments, or Notes for the owner while noting;
// their content is the toolbar's (bridge.tabs), so this file reads no comment or note.
import { computed } from 'vue'
import { Button, TabButtons, Tooltip } from 'frappe-ui'
import type { PickItem } from '../shared/protocol'
import ShowList from './ShowList.vue'
import { bridge, type Tab } from './variants'

defineProps<{ items: PickItem[]; selected: string }>()
const emit = defineEmits<{ choose: [value: string]; hide: [] }>()

// While it has tabs the panel takes the full height, so a tab switch changes what is inside and never the outline.
// Browse, and next to it Comments, or Notes for the owner while noting. The tab and the toolbar's tool follow
// each other (the toolbar does the following). Without a tool to pick with (a guest) there is nothing to tab to.
const tabbed = computed(() => bridge.canComment || bridge.canNote)
const second = computed<Tab>(() => (bridge.tab === 'notes' ? 'notes' : 'comments'))
const tabOptions = computed(() => [
	{ label: 'Browse', value: 'browse', onClick: () => (bridge.tab = 'browse') },
	{ label: second.value === 'notes' ? 'Notes' : 'Comments', value: second.value, onClick: () => (bridge.tab = second.value) },
])
const extra = computed(() => (bridge.tab === 'browse' ? null : (bridge.tabs[bridge.tab] ?? null)))
</script>

<template>
	<aside
		data-canvas-panel
		aria-label="Show on the canvas"
		class="pointer-events-auto absolute right-3 top-3 z-10 flex w-72 flex-col overflow-hidden rounded-[16px] bg-surface-elevation-2 p-3 shadow-lg ring-1 ring-outline-gray-2"
		:class="tabbed ? 'bottom-3' : 'max-h-[calc(100%-1.5rem)]'"
		data-ui
	>
		<!-- The tabs. The hide button sits at the end of the search row, on every tab, as it does in the live page's panel. -->
		<div v-if="tabbed" class="flex items-center gap-1">
			<TabButtons :options="tabOptions" :model-value="bridge.tab === 'browse' ? 'browse' : second">
				<template #suffix="{ button }">
					<span v-if="button.value !== 'browse' && bridge.counts[second]" class="tabular-nums text-ink-gray-5">{{ bridge.counts[second] }}</span>
				</template>
			</TabButtons>
		</div>

		<component :is="extra" v-if="extra" class="min-h-0 flex-1" :class="tabbed ? 'mt-2' : ''" @hide="emit('hide')" />

		<ShowList v-show="!extra" :items="items" :selected="selected" width="16.5rem" :class="tabbed ? 'mt-2' : ''" @choose="(v) => emit('choose', v)">
			<template #end>
				<Tooltip text="Hide panel">
					<Button variant="ghost" icon="lucide-panel-right" aria-label="Hide panel" @click="emit('hide')" />
				</Tooltip>
			</template>
		</ShowList>
	</aside>
</template>
