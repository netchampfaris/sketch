<script setup lang="ts">
// "Role Approver" with a menu of the state's options. Used by the top chip and the canvas bar.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dropdown } from 'frappe-ui'
import { menuBind } from './menus'
import { idOf, mirrorStates, stateOf, stateValues } from './state'
import type { DState } from './state'

const props = withDefaults(defineProps<{ state: DState; showName?: boolean }>(), { showName: true })
const router = useRouter()
const current = computed(() => stateOf(props.state))
const options = computed(() =>
  props.state.options.map((o) => ({
    label: o,
    selected: o === current.value,
    onClick: () => {
      stateValues[idOf(props.state.path, props.state.key)] = o
      mirrorStates(router)
    },
  })),
)
</script>

<template>
  <Dropdown v-bind="menuBind(`lens:${state.label}`)" :options="options">
    <Button variant="ghost" :aria-label="`${state.label}: ${current}`">
      <span class="flex items-center gap-1.5">
        <span v-if="showName" class="text-p-sm text-ink-gray-5">{{ state.label }}</span>
        <span class="text-p-sm text-ink-gray-8">{{ current }}</span>
        <span class="lucide-chevron-down size-3.5 text-ink-gray-5" aria-hidden="true" />
      </span>
    </Button>
    <template #item-prefix="{ item }">
      <span class="size-4 shrink-0" :class="item.selected ? 'lucide-check' : ''" aria-hidden="true" />
    </template>
  </Dropdown>
</template>
