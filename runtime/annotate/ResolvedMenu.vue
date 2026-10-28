<script setup lang="ts">
// The ⋯ beside the comments search: "Show resolved" (a check when on, the count after it), and for the owner "Delete
// resolved…", which asks first because it cannot be undone. A thread whose canvas tile has gone counts as resolved.
// Its menu and dialog open in the toolbar's own layer: above the canvas, and outside the page the picking swallows.
import { computed, ref } from 'vue'
import { Button, Dialog, Dropdown, providePortalTarget, toast } from 'frappe-ui'
import { deleteResolved, resolvedCount, showResolved } from './comments'
import { isOwner } from './host'

providePortalTarget(() => document.querySelector<HTMLElement>('[data-annotate-menus]') ?? undefined)

const owner = isOwner()
const threads = (n: number) => `${n} ${n === 1 ? 'thread' : 'threads'}`
const resolvedThreads = (n: number) => `${n} resolved ${n === 1 ? 'thread' : 'threads'}`

const open = ref(false)
// The number the dialog was opened with, so its title holds still while it closes.
const asked = ref(0)
function ask() {
	asked.value = resolvedCount.value
	open.value = true
}
const options = computed(() => [
	{ group: 'show', hideLabel: true, options: [{ label: 'Show resolved', key: 'show', disabled: !resolvedCount.value, onClick: () => (showResolved.value = !showResolved.value) }] },
	...(owner ? [{ group: 'delete', hideLabel: true, options: [{ label: 'Delete resolved…', key: 'delete', theme: 'red', disabled: !resolvedCount.value, onClick: ask }] }] : []),
])

async function remove({ close }: { close: () => void }) {
	try {
		const n = await deleteResolved()
		close()
		toast.success(`${threads(n)} deleted`)
	} catch {
		toast.error("Couldn't delete the resolved threads. Try again.")
	}
}
const actions = computed(() => [
	{ label: 'Cancel', onClick: ({ close }: { close: () => void }) => close() },
	{ label: 'Delete', variant: 'solid', theme: 'red', onClick: remove },
])
</script>

<template>
	<Dropdown :options="options" align="end">
		<Button variant="ghost" icon="lucide-ellipsis" aria-label="Comment options" />
		<template #item-prefix="{ item }">
			<span class="size-4 shrink-0" :class="item.key === 'show' && showResolved ? 'lucide-check' : ''" aria-hidden="true" />
		</template>
		<template #item-suffix="{ item }">
			<span v-if="item.key === 'show' && resolvedCount" class="ml-auto pl-3 tabular-nums text-ink-gray-5">{{ resolvedCount }}</span>
		</template>
	</Dropdown>
	<Dialog v-model:open="open" :title="`Delete ${resolvedThreads(asked)}?`" message="Their replies go too. This can't be undone." size="sm" :actions="actions" />
</template>
