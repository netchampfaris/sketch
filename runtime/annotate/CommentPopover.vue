<script setup lang="ts">
// The comment box that opens beside a clicked element (a new thread) or an avatar pin (a thread).
// Every change is its own call (comments.ts). A save that fails keeps what was typed and says so
// under the composer, with a Retry.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useElementSize } from '@vueuse/core'
import { Badge, Button, Textarea, toast } from 'frappe-ui'
import { host } from './host'
import {
	MAX_BYTES,
	ago,
	byteLength,
	createThread,
	edit,
	reply,
	remove,
	setResolved,
	toNote,
	whenOf,
	type Anchor,
	type Reply,
	type Thread,
} from './comments'
import type { Note } from './annotate'
import AuthorAvatar from './AuthorAvatar.vue'

const props = defineProps<{
	x: number
	y: number
	// A new thread's words (kept by the toolbar across a page change), and where it will sit.
	modelValue: string
	anchor?: Anchor
	thread?: Thread
	component?: string
	extra: number
	// The toolbar's box: the popover keeps clear of it when they would overlap sideways.
	avoid: { left: number; right: number; top: number; bottom: number } | null
}>()
const emit = defineEmits<{
	'update:modelValue': [text: string]
	created: [thread: Thread]
	gone: []
	noted: [note: Note]
	close: []
}>()

const root = ref<HTMLElement | null>(null)
const { height } = useElementSize(root, { width: 0, height: 220 }, { box: 'border-box' })
const W = 320
const GAP = 12
const EDGE = 8

// Right and below the point; flips above or left when it would run off the viewport.
const pos = computed(() => {
	const vw = window.innerWidth
	const vh = window.innerHeight
	const h = height.value || 220
	let left = props.x + GAP
	if (left + W > vw - EDGE) left = props.x - GAP - W
	left = Math.max(EDGE, Math.min(left, vw - W - EDGE))
	let lo = EDGE
	let hi = vh - EDGE - h
	const a = props.avoid
	if (a && left < a.right && left + W > a.left) {
		if (a.top > vh / 2) hi = a.top - EDGE - h
		else lo = a.bottom + EDGE
	}
	let top = props.y + GAP
	if (top > hi) top = props.y - GAP - h
	top = Math.max(lo, Math.min(top, Math.max(lo, hi)))
	return { left: `${left}px`, top: `${top}px`, transformOrigin: `${props.x - left}px ${props.y - top}px` }
})

onMounted(async () => {
	await nextTick()
	const ta = root.value?.querySelector('textarea')
	ta?.focus()
	ta?.setSelectionRange(ta.value.length, ta.value.length)
})

const me = host.me
const owner = host.role === 'owner'
const comments = computed<Reply[]>(() => (props.thread ? [props.thread, ...props.thread.replies] : []))
const canEdit = (c: Reply) => c.author === me
const canDelete = (c: Reply) => c.author === me || owner
const canResolve = computed(() => !!props.thread && (props.thread.author === me || owner))

// ---- Saving: one run at a time; a failure leaves the words where they are and offers a retry ----
const busy = ref(false)
const failed = ref<(() => Promise<void>) | null>(null)
async function run(fn: () => Promise<void>) {
	if (busy.value) return
	busy.value = true
	failed.value = null
	try {
		await fn()
	} catch {
		failed.value = () => run(fn)
	} finally {
		busy.value = false
	}
}

const tooLong = (s: string) => byteLength(s) > MAX_BYTES
const ready = (s: string) => !!s.trim() && !tooLong(s)

// A new thread.
const canStart = computed(() => ready(props.modelValue))
function start() {
	if (!canStart.value || !props.anchor) return
	const text = props.modelValue.trim()
	void run(async () => {
		const t = await createThread(props.anchor!, text)
		emit('update:modelValue', '')
		emit('created', t)
	})
}

// A reply.
const replyText = ref('')
function sendReply() {
	const t = props.thread
	const text = replyText.value.trim()
	if (!t || !ready(text)) return
	void run(async () => {
		await reply(t.id, text)
		replyText.value = ''
	})
}

// Editing one of your own.
const editing = ref<{ id: string; text: string } | null>(null)
function saveEdit() {
	const e = editing.value
	const t = props.thread
	if (!e || !t || !ready(e.text)) return
	void run(async () => {
		await edit(t.id, e.id, e.text.trim())
		editing.value = null
	})
}

// Deleting is for good, so it asks first, in place.
const confirming = ref<string | null>(null)
function del(c: Reply) {
	const t = props.thread
	if (!t) return
	void run(async () => {
		await remove(t.id, c.id)
		confirming.value = null
		if (c.id === t.id) emit('gone')
	})
}

function toggleResolved() {
	const t = props.thread
	if (!t) return
	void run(async () => {
		await setResolved(t.id, !t.resolved)
	})
}

function addToNotes(c: Reply) {
	void run(async () => {
		const row = await toNote(c.id)
		emit('noted', row)
		toast.success('Added to notes')
	})
}

function onKey(e: KeyboardEvent) {
	if (e.key !== 'Enter' || !(e.metaKey || e.ctrlKey)) return
	e.preventDefault()
	if (editing.value) saveEdit()
	else if (props.thread) sendReply()
	else start()
}
</script>

<template>
	<div
		ref="root"
		data-annotate-ui
		role="dialog"
		aria-label="Comment"
		class="pointer-events-auto fixed z-[63] flex max-h-[calc(100dvh-1rem)] w-80 flex-col rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-3 shadow-xl"
		:style="pos"
		@keydown="onKey"
	>
		<div class="flex items-center gap-2">
			<p class="flex min-w-0 flex-1 items-baseline gap-2 text-base">
				<span class="min-w-0 truncate font-medium text-ink-gray-8">{{ thread?.anchor.component || component }}</span>
				<span v-if="extra" class="shrink-0 tabular-nums text-ink-gray-5">+{{ extra }} more</span>
			</p>
			<Badge v-if="thread?.resolved" class="shrink-0" theme="green" variant="subtle" size="sm" label="Resolved" />
			<Button v-if="canResolve" class="shrink-0" variant="ghost" :label="thread?.resolved ? 'Reopen' : 'Resolve'" :disabled="busy" @click="toggleResolved" />
			<Button class="shrink-0" variant="ghost" icon="lucide-x" aria-label="Close" @click="emit('close')" />
		</div>

		<!-- A thread: every comment, then a reply. -->
		<template v-if="thread">
			<div class="mt-1 min-h-0 flex-1 divide-y divide-outline-gray-1 overflow-y-auto">
				<div v-for="c in comments" :key="c.id" class="flex gap-2 py-2">
					<span class="mt-px shrink-0"><AuthorAvatar :username="c.author" size="sm" /></span>
					<div class="min-w-0 flex-1">
						<p class="flex items-baseline gap-2">
							<span class="min-w-0 truncate text-base font-medium text-ink-gray-8">@{{ c.author }}</span>
							<span class="shrink-0 text-sm text-ink-gray-5" :title="whenOf(c.ts)">{{ ago(c.ts) }}</span>
							<span v-if="c.edited" class="shrink-0 text-sm text-ink-gray-4">edited</span>
						</p>

						<template v-if="editing?.id === c.id">
							<Textarea v-model="editing.text" :rows="3" class="mt-1 text-base" />
							<p v-if="tooLong(editing.text)" class="mt-1 text-p-sm text-ink-red-3">Over the 4 KB limit</p>
							<div class="mt-2 flex items-center gap-2">
								<Button variant="ghost" label="Cancel" @click="editing = null" />
								<Button class="ml-auto" variant="solid" theme="gray" label="Save" :disabled="!ready(editing.text) || busy" @click="saveEdit" />
							</div>
						</template>
						<template v-else>
							<p class="whitespace-pre-wrap break-words text-base text-ink-gray-7">{{ c.text }}</p>
							<div v-if="confirming === c.id" class="mt-1 flex items-center gap-2">
								<span class="min-w-0 flex-1 text-p-sm text-ink-gray-6">
									{{ c.id === thread.id && thread.replies.length ? `Delete this and its ${thread.replies.length} ${thread.replies.length === 1 ? 'reply' : 'replies'}?` : 'Delete this for good?' }}
								</span>
								<Button variant="ghost" label="Cancel" @click="confirming = null" />
								<Button variant="subtle" theme="red" label="Delete" :disabled="busy" @click="del(c)" />
							</div>
							<div v-else class="-ml-2 mt-0.5 flex flex-wrap items-center">
								<Button v-if="canEdit(c)" variant="ghost" size="sm" label="Edit" @click="editing = { id: c.id, text: c.text }" />
								<Button v-if="canDelete(c)" variant="ghost" size="sm" label="Delete" @click="confirming = c.id" />
								<Button v-if="owner" variant="ghost" size="sm" label="Add to notes" :disabled="busy" @click="addToNotes(c)" />
							</div>
						</template>
					</div>
				</div>
			</div>

			<div class="mt-1 border-t border-outline-gray-1 pt-3">
				<Textarea v-model="replyText" :rows="2" placeholder="Reply…" class="text-base" />
				<p v-if="tooLong(replyText)" class="mt-1 text-p-sm text-ink-red-3">Over the 4 KB limit</p>
				<div class="mt-2 flex items-center gap-2">
					<span class="text-xs text-ink-gray-4">⌘↵ to send</span>
					<Button class="ml-auto" variant="solid" theme="gray" label="Reply" :disabled="!ready(replyText) || busy" @click="sendReply" />
				</div>
			</div>
		</template>

		<!-- A new thread. -->
		<template v-else>
			<Textarea :model-value="modelValue" :rows="3" placeholder="Add a comment…" class="mt-2 text-base" @update:model-value="emit('update:modelValue', $event)" />
			<p v-if="tooLong(modelValue)" class="mt-1 text-p-sm text-ink-red-3">Over the 4 KB limit</p>
			<div class="mt-3 flex items-center gap-2">
				<span class="text-xs text-ink-gray-4">⌘↵ to send</span>
				<span class="ml-auto flex items-center gap-2">
					<Button variant="ghost" label="Cancel" @click="emit('close')" />
					<Button variant="solid" theme="gray" label="Comment" :disabled="!canStart || busy" @click="start" />
				</span>
			</div>
		</template>

		<p v-if="failed" role="alert" class="mt-2 flex items-center gap-1 text-p-sm text-ink-red-3">
			<span class="lucide-triangle-alert size-3.5 shrink-0" aria-hidden="true" />
			Couldn't save ·
			<Button variant="ghost" size="sm" label="Retry" :disabled="busy" @click="failed()" />
		</p>
	</div>
</template>
