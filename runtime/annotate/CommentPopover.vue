<script setup lang="ts">
// The comment box that opens beside a clicked element (a new thread) or an avatar pin (a thread).
// Every change is its own call (comments.ts). A save that fails keeps what was typed and says so
// under the composer, with a Retry.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useElementSize } from '@vueuse/core'
import { Button, Dropdown, Textarea, Tooltip, toast } from 'frappe-ui'
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
import ComposerInput from './ComposerInput.vue'

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
const WIDTH = 300
const GAP = 12
const EDGE = 12

// Right and below the point; flips above or left when it would run off the viewport.
const pos = computed(() => {
	const vw = window.innerWidth
	const vh = window.innerHeight
	const W = Math.min(WIDTH, vw - 2 * EDGE)
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

// What each ⋯ offers, only to whoever may use it. The thread's own Delete lives in the header menu.
function startEdit(c: Reply) {
	editing.value = { id: c.id, text: c.text }
	// The menu hands focus back to its button as it closes; take it after that.
	setTimeout(() => root.value?.querySelector<HTMLTextAreaElement>('[data-editing] textarea')?.focus(), 50)
}
const commentMenu = (c: Reply) => {
	const first = c.id === props.thread?.id
	return [
		canEdit(c) && { label: 'Edit', icon: 'lucide-pencil', onClick: () => startEdit(c) },
		owner && { label: 'Add to notes', icon: 'lucide-sticky-note', onClick: () => addToNotes(c) },
		canDelete(c) && !first && { label: 'Delete', icon: 'lucide-trash-2', theme: 'red', onClick: () => (confirming.value = c.id) },
	].filter((o) => !!o) as any[]
}
const threadMenu = computed<any[]>(() =>
	props.thread && canDelete(props.thread)
		? [{ label: owner ? 'Delete thread' : 'Delete', icon: 'lucide-trash-2', theme: 'red', onClick: () => (confirming.value = props.thread!.id) }]
		: [],
)

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

// Enter sends from the words box itself (ComposerInput); here only an edit in place has keys of its own.
function onKey(e: KeyboardEvent) {
	if (!editing.value) return
	if (e.key === 'Escape') {
		e.preventDefault()
		e.stopPropagation()
		editing.value = null
	} else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
		e.preventDefault()
		saveEdit()
	}
}
</script>

<template>
	<div
		ref="root"
		data-annotate-ui
		role="dialog"
		aria-label="Comment"
		class="pointer-events-auto fixed z-[63] flex max-h-[calc(100dvh-1.5rem)] w-[min(18.75rem,calc(100vw-1.5rem))] flex-col rounded-[16px] bg-surface-elevation-2 p-3 shadow-lg ring-1 ring-outline-gray-2"
		:style="pos"
		@keydown="onKey"
	>
		<!-- A thread: its title on the left, the few things you can do to it as quiet icons on the right. -->
		<div v-if="thread" class="flex h-6 items-center gap-0.5">
			<p class="min-w-0 flex-1 truncate text-p-sm font-normal text-ink-gray-6">{{ thread.resolved ? 'Comment · Resolved' : 'Comment' }}</p>
			<Tooltip v-if="canResolve" :text="thread.resolved ? 'Reopen' : 'Resolve'" :hover-delay="600">
				<Button size="xs" variant="ghost" icon="lucide-check" :aria-label="thread.resolved ? 'Reopen' : 'Resolve'" :disabled="busy" @click="toggleResolved" />
			</Tooltip>
			<Dropdown v-if="threadMenu.length" :options="threadMenu" align="end">
				<Button size="xs" variant="ghost" icon="lucide-ellipsis" aria-label="Thread menu" />
			</Dropdown>
			<Tooltip text="Close" :hover-delay="600">
				<Button size="xs" variant="ghost" icon="lucide-x" aria-label="Close" @click="emit('close')" />
			</Tooltip>
		</div>
		<!-- A new comment has no header; on touch, with no Escape, it keeps a way out. -->
		<div v-else class="mb-1 hidden h-6 items-center justify-end [@media(hover:none)]:flex">
			<Button size="xs" variant="ghost" icon="lucide-x" aria-label="Close" @click="emit('close')" />
		</div>

		<template v-if="thread">
			<!-- Every icon button sits inside this box with room to spare: it scrolls, so anything past its edge would be cut. -->
			<div class="mt-2 min-h-0 flex-1 space-y-3 overflow-y-auto">
				<div v-for="c in comments" :key="c.id" class="group">
					<!-- One row, one centre line: avatar, name, time and the menu. -->
					<div class="flex h-6 items-center gap-2">
						<AuthorAvatar :username="c.author" size="sm" />
						<p class="flex min-w-0 flex-1 items-center gap-1 text-base">
							<span class="min-w-0 truncate font-medium text-ink-gray-8">{{ c.name || c.author }}</span>
							<span class="shrink-0 text-ink-gray-5" aria-hidden="true">·</span>
							<span class="shrink-0 text-ink-gray-5" :title="whenOf(c.ts)">{{ ago(c.ts) }}</span>
							<span v-if="c.edited" class="shrink-0 text-ink-gray-4">(edited)</span>
						</p>
						<Dropdown v-if="commentMenu(c).length && editing?.id !== c.id" :options="commentMenu(c)" align="end">
							<Button
								class="shrink-0 data-[state=open]:opacity-100 [@media(hover:hover)]:opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
								variant="ghost"
								size="xs"
								icon="lucide-ellipsis"
								aria-label="Comment actions"
							/>
						</Dropdown>
					</div>

					<!-- The words start under the name, not under the avatar. -->
					<div class="ml-7 mt-1">
						<template v-if="editing?.id === c.id">
							<div data-editing>
								<Textarea v-model="editing.text" :rows="3" class="w-full resize-none text-base" />
							</div>
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
						</template>
					</div>
				</div>
			</div>

			<ComposerInput v-model="replyText" class="mt-3" placeholder="Reply…" send-label="Reply" :can-send="ready(replyText) && !busy" @send="sendReply" />
			<p v-if="tooLong(replyText)" class="mt-1 text-p-sm text-ink-red-3">Over the 4 KB limit</p>
		</template>

		<!-- A new thread. -->
		<template v-else>
			<p v-if="extra" class="mb-1 text-p-sm tabular-nums text-ink-gray-5">On this and {{ extra }} more</p>
			<ComposerInput :model-value="modelValue" placeholder="Add a comment…" send-label="Comment" :can-send="canStart && !busy" @update:model-value="emit('update:modelValue', $event)" @send="start" />
			<p v-if="tooLong(modelValue)" class="mt-1 text-p-sm text-ink-red-3">Over the 4 KB limit</p>
		</template>

		<p v-if="failed" role="alert" class="mt-2 flex items-center gap-1 text-p-sm text-ink-red-3">
			<span class="lucide-triangle-alert size-3.5 shrink-0" aria-hidden="true" />
			Couldn't save ·
			<Button variant="ghost" size="sm" label="Retry" :disabled="busy" @click="failed()" />
		</p>
	</div>
</template>
