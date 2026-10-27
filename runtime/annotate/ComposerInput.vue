<script setup lang="ts">
// The words box of a comment or a note: one line that grows with what is typed (to six), and a send
// arrow inside it on the right. Enter sends, Shift+Enter starts a new line; Escape is the popover's
// own (it cancels). No hint text: the arrow's tooltip names what it does.
import { nextTick, onMounted, ref, watch } from 'vue'
import { Button, Textarea, Tooltip } from 'frappe-ui'

const props = defineProps<{ modelValue: string; placeholder: string; sendLabel: string; canSend: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [text: string]; send: [] }>()

const MAX_ROWS = 6
const root = ref<HTMLElement | null>(null)

function fit() {
	const ta = root.value?.querySelector('textarea')
	if (!ta) return
	const cs = getComputedStyle(ta)
	const line = parseFloat(cs.lineHeight) || 20
	const chrome = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) + parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth)
	ta.style.height = 'auto'
	ta.style.height = `${Math.min(ta.scrollHeight, MAX_ROWS * line + chrome)}px`
	ta.style.overflowY = ta.scrollHeight > MAX_ROWS * line + chrome ? 'auto' : 'hidden'
}
onMounted(fit)
watch(() => props.modelValue, () => nextTick(fit))

function onKey(e: KeyboardEvent) {
	if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return
	e.preventDefault()
	if (props.canSend) emit('send')
}

defineExpose({ focus: () => root.value?.querySelector('textarea')?.focus() })
</script>

<template>
	<div ref="root" class="relative">
		<Textarea :model-value="modelValue" :rows="1" :placeholder="placeholder" class="w-full resize-none pr-9" @update:model-value="emit('update:modelValue', $event)" @keydown="onKey" />
		<Tooltip :text="sendLabel" :hover-delay="600">
			<Button class="absolute bottom-1 right-1" variant="solid" theme="gray" size="xs" icon="lucide-arrow-up" :aria-label="sendLabel" :disabled="!canSend" @click="emit('send')" />
		</Tooltip>
	</div>
</template>
