<script setup lang="ts">
// The words box of a comment or a note: frappe-ui's Textarea, one line that grows with what is typed (to six),
// and a send arrow beside it on the right. Enter sends, Shift+Enter starts a new line; Escape is the popover's
// own (it cancels). No hint text: the arrow's tooltip names what it does. Typing @ lists people to mention (MentionField).
import { nextTick, onMounted, ref, watch } from 'vue'
import { Button, Textarea, Tooltip } from 'frappe-ui'
import MentionField from './MentionField.vue'

const props = defineProps<{ modelValue: string; placeholder: string; sendLabel: string; canSend: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [text: string]; send: [] }>()

const MAX_ROWS = 6
const root = ref<HTMLElement | null>(null)

// The Textarea's minimum height is taller than one line and its padding, which would leave one line sitting high.
// The padding takes up the difference, so the words sit in the middle until they grow past it.
function fit() {
	const ta = root.value?.querySelector('textarea')
	if (!ta) return
	ta.style.paddingTop = ta.style.paddingBottom = ''
	const cs = getComputedStyle(ta)
	const line = parseFloat(cs.lineHeight) || 20
	const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
	const border = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth)
	ta.style.height = 'auto'
	const content = ta.scrollHeight - pad
	const extra = Math.max(0, (parseFloat(cs.minHeight) || 0) - border - pad - content)
	if (extra) ta.style.paddingTop = ta.style.paddingBottom = `${parseFloat(cs.paddingTop) + extra / 2}px`
	const chrome = pad + extra + border
	ta.style.height = `${Math.min(content + chrome, MAX_ROWS * line + chrome)}px`
	ta.style.overflowY = content > MAX_ROWS * line ? 'auto' : 'hidden'
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
	<!-- frappe-ui's own Textarea and Button at their default sizes, side by side. The Button sits level with the last line,
		so it stays at the bottom edge as the words grow. -->
	<div ref="root" class="flex items-end gap-2">
		<div class="min-w-0 flex-1">
			<MentionField :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
				<Textarea :model-value="modelValue" :rows="1" :placeholder="placeholder" class="w-full resize-none" @update:model-value="emit('update:modelValue', $event)" @keydown="onKey" />
			</MentionField>
		</div>
		<Tooltip :text="sendLabel" :hover-delay="600">
			<Button class="mb-1 shrink-0" variant="solid" theme="gray" icon="lucide-arrow-up" :aria-label="sendLabel" :disabled="!canSend" @click="emit('send')" />
		</Tooltip>
	</div>
</template>
