<script setup lang="ts">
// "Role Approver" with a menu of the state's options, in the shell's Demo pill. The shell's copy of
// runtime/variants/LensMenu.vue: the state is what the frame reported, and a pick goes back to it.
import { computed } from 'vue'
import { Button, Dropdown } from 'frappe-ui'
import type { ModelState } from '../shared/protocol'
import { choose } from './demo'
import { menuBind } from './variants'

const props = withDefaults(defineProps<{ state: ModelState; showName?: boolean }>(), { showName: true })
const options = computed(() =>
	props.state.options.map((o) => ({
		label: o,
		selected: o === props.state.value,
		onClick: () => choose(props.state.id, o),
	})),
)
</script>

<template>
	<Dropdown v-bind="menuBind(`lens:${state.label}`)" :options="options">
		<Button variant="ghost" :aria-label="`${state.label}: ${state.value}`">
			<span class="flex items-center gap-1.5">
				<span v-if="showName" class="text-p-sm text-ink-gray-5">{{ state.label }}</span>
				<span class="text-p-sm text-ink-gray-8">{{ state.value }}</span>
				<span class="lucide-chevron-down size-3.5 text-ink-gray-5" aria-hidden="true" />
			</span>
		</Button>
		<template #item-prefix="{ item }">
			<span class="size-4 shrink-0" :class="item.selected ? 'lucide-check' : ''" aria-hidden="true" />
		</template>
	</Dropdown>
</template>
