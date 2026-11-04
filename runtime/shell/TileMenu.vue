<script setup lang="ts">
// The live tile's ⋯ menu, drawn by the shell. The frame's ⋯ (runtime/variants/Tile.vue) only says where it is (`tile:menu`); the menu opens there with the items and copy the tile had:
// Make default and Keep only this for the owner, Open page for everyone, States on a set's option, Delete variant on a
// teammate's option for the owner and on an editor's own. A state tile of a component only opens its page.
//
// The frame may post `tile:menu` whenever it likes, so the menu could open under a pointer that was aiming at the page.
// An item acts only on a press that began on it, at least 300 ms after the menu opened (FrameAnchor.vue), so a press
// already on its way (or one dragged in from the page) does nothing. The menu takes the focus as it opens (frappe-ui's
// Dropdown has no way to stop it), so keys meant for a field (a letter, Enter) would land in it: no key acts on an item.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { Dropdown, toast } from 'frappe-ui'
import type { Rect } from '../shared/protocol'
import { canDelete, deleteFailure, deleteVariant, isOwner, keepFailure, keepOnly, makeDefault, makeFailure } from './actions'
import { onFrame, onGone, post } from './frame'
import { canvas, type ShellTile } from './canvas'
import { menuBind } from '../shared/menus'
import FrameAnchor from './FrameAnchor.vue'

const at = ref<{ tileId: string; rect: Rect } | null>(null)
const tile = computed<ShellTile | null>(() => (at.value ? (canvas.tiles.find((t) => t.id === at.value!.tileId) ?? null) : null))
const bind = computed(() => menuBind('tile-menu'))
const open = computed({
	get: () => !!tile.value && bind.value.open,
	set: (o: boolean) => {
		bind.value['onUpdate:open'](o)
		if (!o) at.value = null
	},
})

const anchor = ref<InstanceType<typeof FrameAnchor> | null>(null)
onBeforeUnmount(
	onFrame('tile:menu', (d) => {
		// Only a tile the canvas shows now, and only while it is open.
		if (!canvas.open || !canvas.tiles.some((t) => t.id === d.tileId)) return
		at.value = d
		bind.value['onUpdate:open'](true)
	}),
)
onBeforeUnmount(onGone(() => (open.value = false)))
// The frame's ⋯ holds its pressed look while its menu is open, as a menu's trigger does.
watch(open, (o) => post('display', { menuTile: o && at.value ? at.value.tileId : '' }))
watch(() => canvas.open, (o) => !o && (open.value = false))

// Which item a press began on. A key that activates an item (Enter, Space) drops the press.
const itemOf = (el: Element | null) => el?.closest('[role="menuitem"]')?.textContent?.trim() ?? ''
let keyed = false
useEventListener(document, 'pointerdown', () => (keyed = false), { capture: true })
useEventListener(document, 'keydown', (e: KeyboardEvent) => open.value && (e.key === 'Enter' || e.key === ' ') && (keyed = true), { capture: true })
// A refused activation keeps the menu open (reka closes it unless the select is prevented).
function guarded(label: string, run: () => void) {
	return (e: Event) => {
		const el = anchor.value?.take() ?? null
		const ok = !keyed && !!el && itemOf(el) === label
		keyed = false
		if (!ok) return e.preventDefault()
		run()
	}
}

// The set's default tile on the canvas now, for where Make default's Undo lands.
const firstOf = (t: ShellTile) => {
	const d = canvas.tiles.find((x) => x.isDefault && x.spot.route === t.spot.route && x.spot.tile.kind === 'set' && x.spot.tile.groupKey === t.spot.tile.groupKey)
	return d ? { value: d.spot.tile.option } : undefined
}

async function act(run: () => Promise<void>, failure: (e: Error) => string) {
	try {
		await run()
	} catch (e) {
		toast.error(failure(e as Error))
	}
}

const items = computed(() => {
	const t = tile.value
	if (!t) return []
	const { kind, option } = t.spot.tile
	const set = kind === 'set' && !!option && !!t.setFile && !!t.setName
	const owner = isOwner() && !canvas.tool
	return [
		...(set && owner && !t.isDefault
			? [{ label: 'Make default', icon: 'lucide-star', onClick: guarded('Make default', () => act(() => makeDefault({ name: t.setName, file: t.setFile, first: firstOf(t) }, option, t.id, t.id), makeFailure)) }]
			: []),
		{ label: 'Open page', icon: 'lucide-arrow-up-right', onClick: guarded('Open page', () => post('tile:open', { tileId: t.id })) },
		...(kind === 'set' && option ? [{ label: 'States', icon: 'lucide-layers', onClick: guarded('States', () => post('tile:states', { tileId: t.id })) }] : []),
		...(set && owner && t.setCount > 1
			? [{ label: 'Keep only this', icon: 'lucide-check', onClick: guarded('Keep only this', () => act(() => keepOnly({ name: t.setName, file: t.setFile }, option, t.id, t.id), keepFailure)) }]
			: []),
		...(canDelete(option, t.author)
			? [{ label: 'Delete variant', icon: 'lucide-trash-2', onClick: guarded('Delete variant', () => act(() => deleteVariant(option, t.id, t.id), deleteFailure)) }]
			: []),
	]
})
</script>

<template>
	<Dropdown v-model:open="open" :options="items">
		<template #trigger>
			<!-- Where the frame's ⋯ is: the menu hangs from it. -->
			<FrameAnchor ref="anchor" :rect="at?.rect ?? null" />
		</template>
	</Dropdown>
</template>
