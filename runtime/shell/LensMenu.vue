<script setup lang="ts">
// "Role Approver" with a menu of the state's options: a state's picker in the shell's Demo pill. The state is what the
// frame reported, and a pick goes back to it.
// `fill` stretches it to its column, chevron at the right edge (the Demo pill).
import { computed } from 'vue'
import { Button, Dropdown } from 'frappe-ui'
import type { ModelState } from '../shared/protocol'
import { choose } from './demo'
import { menuBind } from '../shared/menus'

const props = withDefaults(defineProps<{ state: ModelState; showName?: boolean; fill?: boolean }>(), { showName: true })
const item = (o: string) => ({
	label: o,
	selected: o === props.state.value,
	onClick: () => choose(props.state.id, o),
})
// Grouped options get a heading each; a flat list is as it always was.
const options = computed(() =>
	props.state.groups ? props.state.groups.map((g) => ({ group: g.title, options: g.options.map(item) })) : props.state.options.map(item),
)
</script>

<template>
	<Dropdown v-bind="menuBind(`lens:${state.id}`)" :options="options">
		<Button variant="ghost" :class="fill ? 'w-full [&>span]:w-full' : ''" :aria-label="`${state.label}: ${state.value}`">
			<span class="flex items-center gap-1.5" :class="fill ? 'w-full min-w-0' : ''">
				<span v-if="showName" class="text-p-sm text-ink-gray-5">{{ state.label }}</span>
				<span class="text-p-sm text-ink-gray-8" :class="fill ? 'mr-auto truncate' : ''">{{ state.value }}</span>
				<span class="lucide-chevron-down size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
			</span>
		</Button>
		<template #item-prefix="{ item }">
			<span class="size-4 shrink-0" :class="item.selected ? 'lucide-check' : ''" aria-hidden="true" />
		</template>
	</Dropdown>
</template>
