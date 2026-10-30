<script setup lang="ts">
// The words box of a comment or a note: frappe-ui's Textarea, one line that grows with what is typed (to five, then
// it scrolls), and a send arrow beside it on the right. Both are 28px at rest, frappe-ui's default control height. Enter sends, Shift+Enter starts a new line; Escape is the popover's
// own (it cancels). No hint text: the arrow's tooltip names what it does. Typing @ lists people to mention (MentionField).
import { nextTick, onMounted, ref, watch } from 'vue'
import { Button, Textarea, Tooltip } from 'frappe-ui'
import MentionField from './MentionField.vue'

const props = defineProps<{ modelValue: string; placeholder: string; sendLabel: string; canSend: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [text: string]; send: [] }>()

const MAX_ROWS = 5
const root = ref<HTMLElement | null>(null)

// The box is 28px at rest, a default Button's height: a 20px line, 3px of padding and a 1px border, top and bottom
// (frappe-ui's smallest Textarea is 36px). The sizes are set here rather than read from classes: the page's Tailwind
// draws classes after mount, so a box measured from them came out 34px.
const LINE = 20
const PAD = 3
const BORDER = 1
function fit() {
	const ta = root.value?.querySelector('textarea')
	if (!ta) return
	Object.assign(ta.style, { lineHeight: `${LINE}px`, paddingTop: `${PAD}px`, paddingBottom: `${PAD}px`, minHeight: '0px', height: 'auto' })
	const content = ta.scrollHeight - PAD * 2
	const chrome = (PAD + BORDER) * 2
	ta.style.height = `${Math.max(LINE, Math.min(content, MAX_ROWS * LINE)) + chrome}px`
	ta.style.overflowY = content > MAX_ROWS * LINE ? 'auto' : 'hidden'
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
	<!-- frappe-ui's own Textarea and Button, both 28px at rest, side by side. The Button's bottom meets the box's bottom,
		so it stays level with the last line as the words grow. -->
	<div ref="root" class="flex items-end gap-2">
		<div class="min-w-0 flex-1">
			<MentionField :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
				<Textarea :model-value="modelValue" :rows="1" :placeholder="placeholder" class="w-full resize-none" @update:model-value="emit('update:modelValue', $event)" @keydown="onKey" />
			</MentionField>
		</div>
		<Tooltip :text="sendLabel" :hover-delay="600">
			<Button class="shrink-0" variant="solid" theme="gray" icon="lucide-arrow-up" :aria-label="sendLabel" :disabled="!canSend" @click="emit('send')" />
		</Tooltip>
	</div>
</template>
