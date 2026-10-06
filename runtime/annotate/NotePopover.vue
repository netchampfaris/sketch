<script setup lang="ts">
// The note box that opens beside a clicked element (new) or a pin (edit).
import { computed, nextTick, onMounted, ref } from 'vue'
import { Button, Textarea } from 'frappe-ui'

const props = defineProps<{
	x: number
	y: number
	modelValue: string
	component?: string
	extra: number
	editing: boolean
	// The toolbar's box: the popover keeps clear of it when they would overlap sideways.
	avoid: { left: number; right: number; top: number; bottom: number } | null
}>()
const emit = defineEmits<{ 'update:modelValue': [text: string]; save: []; cancel: []; delete: [] }>()

const root = ref<HTMLElement | null>(null)
const height = ref(220)
const W = 320
const GAP = 12
const EDGE = 8

// Right and below the point; flips above or left when it would run off the viewport.
const pos = computed(() => {
	const vw = window.innerWidth
	const vh = window.innerHeight
	let left = props.x + GAP
	if (left + W > vw - EDGE) left = props.x - GAP - W
	left = Math.max(EDGE, Math.min(left, vw - W - EDGE))
	let lo = EDGE
	let hi = vh - EDGE - height.value
	const a = props.avoid
	if (a && left < a.right && left + W > a.left) {
		if (a.top > vh / 2) hi = a.top - EDGE - height.value
		else lo = a.bottom + EDGE
	}
	let top = props.y + GAP
	if (top > hi) top = props.y - GAP - height.value
	top = Math.max(lo, Math.min(top, Math.max(lo, hi)))
	// It grows out of the point it was opened from.
	return { left: `${left}px`, top: `${top}px`, transformOrigin: `${props.x - left}px ${props.y - top}px` }
})

onMounted(async () => {
	await nextTick()
	if (root.value) height.value = root.value.offsetHeight
	const ta = root.value?.querySelector('textarea')
	ta?.focus()
	ta?.setSelectionRange(ta.value.length, ta.value.length)
})

const canSave = computed(() => !!props.modelValue.trim())
function onKey(e: KeyboardEvent) {
	if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
		e.preventDefault()
		if (canSave.value) emit('save')
	}
}
</script>

<template>
	<div
		ref="root"
		data-annotate-ui
		role="dialog"
		aria-label="Note"
		class="pointer-events-auto fixed z-[60] w-80 rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-3 shadow-xl"
		:style="pos"
		@keydown="onKey"
	>
		<p class="flex items-baseline gap-2 text-base">
			<span class="min-w-0 truncate font-medium text-ink-gray-8">{{ component }}</span>
			<span v-if="extra" class="shrink-0 tabular-nums text-ink-gray-5">+{{ extra }} more</span>
		</p>
		<Textarea :model-value="modelValue" :rows="3" placeholder="What should change?" class="mt-2 text-base" @update:model-value="emit('update:modelValue', $event)" />
		<div class="mt-3 flex items-center gap-2">
			<Button v-if="editing" variant="ghost" theme="red" icon="lucide-trash-2" aria-label="Delete note" @click="emit('delete')" />
			<span class="text-xs text-ink-gray-4">⌘↵ to save</span>
			<span class="ml-auto flex items-center gap-2">
				<Button variant="ghost" label="Cancel" @click="emit('cancel')" />
				<Button variant="solid" theme="gray" :label="editing ? 'Save' : 'Add'" :disabled="!canSave" @click="emit('save')" />
			</span>
		</div>
	</div>
</template>
