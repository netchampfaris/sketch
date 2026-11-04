<script setup lang="ts">
// The owner's one-time notice that a retired Runtime moved this Prototype to a newer frappe-ui
// (sketch/patches/v1_0/retire_old_runtimes.py). It is a toast that stays, drawn by the shell's toaster with the
// toaster's own surface, so it sits where every shell toast does: above the Demo pill and the toolbar's trigger
// (actions.ts placeToasts), never in the frame. Dismiss clears it on the server for good; a failure keeps it.
import { nextTick, ref } from 'vue'
import { toast } from 'frappe-ui'
import { write } from './api'
import { copyText } from './annotate'

// `toastId` is the toast this card is drawn in, so Dismiss closes it.
const props = defineProps<{ toastId: string; name: string; slug: string; from: string; to: string }>()

const prompt = `My Sketch prototype ${props.slug} was moved from frappe-ui ${props.from} to ${props.to}. Open every page in light and dark mode, look for anything that looks or works differently than intended (spacing, components, props, icons), fix it in the prototype's code, and commit.`

const copied = ref(false)
// The clipboard refused: the prompt shows, selected, so the person copies it themselves.
const blocked = ref(false)
const box = ref<HTMLElement | null>(null)
const dismissing = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function copy() {
	if (!(await copyText(prompt))) {
		blocked.value = true
		await nextTick()
		if (box.value) getSelection()?.selectAllChildren(box.value)
		return
	}
	copied.value = true
	clearTimeout(timer)
	timer = setTimeout(() => (copied.value = false), 2000)
}

async function dismiss() {
	if (dismissing.value) return
	dismissing.value = true
	try {
		await write('sketch.viewer_api.dismiss_moved_notice', { name: props.name })
		toast.dismiss(props.toastId)
	} catch (e) {
		toast.error(
			e instanceof TypeError ? "Couldn't dismiss it. Check your connection and try again." : `Couldn't dismiss it. ${(e as Error).message}`,
		)
	} finally {
		dismissing.value = false
	}
}
</script>

<template>
	<div data-sketch-ui="moved-notice" class="flex w-full min-w-0 flex-col gap-1 py-1">
		<p class="text-p-base font-medium text-ink-base">Moved to frappe-ui {{ to }}</p>
		<p class="text-p-base text-ink-base">
			This prototype was on {{ from }}, which Sketch no longer supports. If something looks off, ask your agent to fix it.
		</p>
		<template v-if="blocked">
			<p class="mt-1 text-p-sm text-ink-base">Couldn't copy. It's selected below, so copy it from there.</p>
			<div
				ref="box"
				tabindex="0"
				aria-label="Prompt for your agent"
				class="select-text whitespace-pre-wrap break-words rounded-4 bg-surface-gray-8 px-2 py-1.5 text-p-sm text-ink-base"
			>{{ prompt }}</div>
		</template>
		<div class="-mr-2 mt-1 flex justify-end gap-1">
			<button
				type="button"
				class="flex h-7 shrink-0 items-center rounded-4 bg-transparent px-2 py-1.5 text-base font-medium text-ink-blue-link hover:bg-surface-gray-8"
				@click="copy"
			>
				<!-- Both labels share one grid cell, so the button keeps the longer one's width and never moves. -->
				<span class="grid justify-items-center">
					<span class="[grid-area:1/1]" :class="{ invisible: copied }">Copy prompt</span>
					<span class="[grid-area:1/1]" :class="{ invisible: !copied }">Copied</span>
				</span>
			</button>
			<button
				type="button"
				class="flex h-7 shrink-0 items-center rounded-4 bg-transparent px-2 py-1.5 text-base font-medium text-ink-base hover:bg-surface-gray-8 disabled:opacity-50"
				:disabled="dismissing"
				@click="dismiss"
			>
				Dismiss
			</button>
		</div>
	</div>
</template>
