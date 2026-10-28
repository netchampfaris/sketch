<script setup lang="ts">
// The comment box that opens beside a clicked element (a new thread) or an avatar pin (a thread).
// Every change is its own call (comments.ts). A save that fails keeps what was typed and says so
// under the composer, with a Retry.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useElementSize } from '@vueuse/core'
import { Badge, Button, Dropdown, Textarea, Tooltip, providePortalTarget } from 'frappe-ui'
import { applyPicks, picksShown, picksWords } from 'sketch:variants'
import { host } from './host'
import {
	MAX_BYTES,
	ago,
	byteLength,
	pieces,
	createThread,
	edit,
	reply,
	remove,
	noteDraft,
	setResolved,
	whenOf,
	type Anchor,
	type Reply,
	type Thread,
} from './comments'
import AuthorAvatar from './AuthorAvatar.vue'
import ComposerInput from './ComposerInput.vue'
import MentionField from './MentionField.vue'
import { decode, encode, forget } from './mentions'

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
	// The open comments panel: the popover flips to the left of the point rather than cover it.
	panel: { left: number; right: number; top: number; bottom: number } | null
	// Where this box's own menus open. The canvas draws its overlays in a layer below the box, so a menu opened from the
	// box would sit behind it; this layer is above it.
	menuHost?: HTMLElement | null
}>()
const emit = defineEmits<{
	'update:modelValue': [text: string]
	created: [thread: Thread]
	gone: []
	// The owner's "Add to notes": the thread as words, and its anchor, for the note composer to open on.
	noted: [draft: { note: string; anchor: Anchor }]
	close: []
}>()

const root = ref<HTMLElement | null>(null)
providePortalTarget(() => props.menuHost ?? undefined)
const { height } = useElementSize(root, { width: 0, height: 220 }, { box: 'border-box' })
const WIDTH = 300
const GAP = 12
const EDGE = 12

// Right and below the point; flips above or left when it would run off the viewport or onto the open panel.
// Under 640px it spans the screen, less an edge on each side.
const pos = computed(() => {
	const vw = window.innerWidth
	const vh = window.innerHeight
	const W = vw < 640 ? vw - 2 * EDGE : WIDTH
	const h = height.value || 220
	const a = props.avoid
	const topFor = (left: number) => {
		let lo = EDGE
		let hi = vh - EDGE - h
		if (a && left < a.right && left + W > a.left) {
			if (a.top > vh / 2) hi = a.top - EDGE - h
			else lo = a.bottom + EDGE
		}
		const top = props.y + GAP
		return Math.max(lo, Math.min(top > hi ? props.y - GAP - h : top, Math.max(lo, hi)))
	}
	let left = props.x + GAP
	if (left + W > vw - EDGE) left = props.x - GAP - W
	left = Math.max(EDGE, Math.min(left, vw - W - EDGE))
	let top = topFor(left)
	const p = props.panel
	if (p && left + W > p.left && left < p.right && top < p.bottom && top + h > p.top) {
		left = Math.max(EDGE, Math.min(props.x - GAP - W, p.left - EDGE - W))
		top = topFor(left)
	}
	return { left: `${left}px`, top: `${top}px`, width: `${W}px`, transformOrigin: `${props.x - left}px ${props.y - top}px` }
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
	editing.value = { id: c.id, text: decode(c.text) }
	// The menu hands focus back to its button as it closes; take it after that.
	setTimeout(() => root.value?.querySelector<HTMLTextAreaElement>('[data-editing] textarea')?.focus(), 50)
}
const commentMenu = (c: Reply) => {
	const first = c.id === props.thread?.id
	return [
		canEdit(c) && { label: 'Edit', icon: 'lucide-pencil', onClick: () => startEdit(c) },
		canDelete(c) && !first && { label: 'Delete', icon: 'lucide-trash-2', theme: 'red', onClick: () => (confirming.value = c.id) },
	].filter((o) => !!o) as any[]
}
// Add to notes takes the whole thread, so it sits with the thread's own actions.
const threadMenu = computed<any[]>(() => {
	const t = props.thread
	if (!t) return []
	return [
		owner && { label: 'Add to notes', icon: 'lucide-sticky-note', onClick: addToNotes },
		canDelete(t) && { label: owner ? 'Delete thread' : 'Delete', icon: 'lucide-trash-2', theme: 'red', onClick: () => (confirming.value = t.id) },
	].filter((o) => !!o) as any[]
})

// What the Demo showed when the thread was made. Said only when it was not the defaults; a click puts the page back that way.
const picks = computed(() => props.thread?.anchor.picks)
const picksWhere = computed(() => picksWords(picks.value))
const picksNow = computed(() => picksShown(picks.value))

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
// A lone "@" (a mention just begun) is not words yet.
const ready = (s: string) => !!s.replace(/@/g, '').trim() && !tooLong(s)

// A new thread.
const canStart = computed(() => ready(props.modelValue))
function start() {
	if (!canStart.value || !props.anchor) return
	const text = props.modelValue.trim()
	void run(async () => {
		const t = await createThread(props.anchor!, encode(text))
		forget()
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
		await reply(t.id, encode(text))
		forget()
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
		await edit(t.id, e.id, encode(e.text.trim()))
		forget()
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

function addToNotes() {
	const t = props.thread
	if (!t) return
	void run(async () => emit('noted', await noteDraft(t.id)))
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
		class="pointer-events-auto fixed z-[63] flex max-h-[calc(100dvh-1.5rem)] flex-col rounded-[16px] bg-surface-elevation-2 p-3 shadow-lg ring-1 ring-outline-gray-2"
		:style="pos"
		@keydown="onKey"
	>
		<!-- A thread: its title on the left, the few things you can do to it as quiet icons on the right. -->
		<div v-if="thread" class="flex h-6 items-center gap-0.5">
			<div class="flex min-w-0 flex-1 items-center gap-2">
				<p class="shrink-0 text-p-sm font-normal text-ink-gray-6">{{ thread.resolved ? 'Comment · Resolved' : 'Comment' }}</p>
				<!-- Made on other options than the defaults: the words, and when the page is not showing them, the way back to them. -->
				<Tooltip v-if="picksWhere && !picksNow" text="Show the page this was made on" :hover-delay="600">
					<button type="button" class="min-w-0 rounded-[6px] outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3" @click="applyPicks(picks, host.router)">
						<Badge theme="gray" size="sm" class="max-w-full cursor-pointer hover:bg-surface-gray-3"><span class="truncate">On {{ picksWhere }}</span></Badge>
					</button>
				</Tooltip>
				<Badge v-else-if="picksWhere" theme="gray" size="sm" class="min-w-0"><span class="truncate" :title="`On ${picksWhere}`">On {{ picksWhere }}</span></Badge>
			</div>
			<Tooltip v-if="canResolve" :text="thread.resolved ? 'Reopen' : 'Resolve'" :hover-delay="600">
				<Button size="xs" :variant="thread.resolved ? 'subtle' : 'ghost'" icon="lucide-check" :aria-label="thread.resolved ? 'Reopen' : 'Resolve'" :disabled="busy" @click="toggleResolved" />
			</Tooltip>
			<Dropdown v-if="threadMenu.length" :options="threadMenu" align="end">
				<Button size="xs" variant="ghost" icon="lucide-ellipsis" aria-label="Thread menu" />
			</Dropdown>
			<Tooltip text="Close" :hover-delay="600">
				<Button class="-mr-[5px]" size="xs" variant="ghost" icon="lucide-x" aria-label="Close" @click="emit('close')" />
			</Tooltip>
		</div>
		<!-- A new comment has no header; on touch, with no Escape, it keeps a way out. -->
		<div v-else class="mb-1 hidden h-6 items-center justify-end [@media(hover:none)]:flex">
			<Button class="-mr-[5px]" size="xs" variant="ghost" icon="lucide-x" aria-label="Close" @click="emit('close')" />
		</div>

		<template v-if="thread">
			<!-- Every icon button sits inside this box with room to spare: it scrolls, so anything past its edge would be cut. -->
			<div class="-mr-[5px] mt-2 min-h-0 flex-1 space-y-3 overflow-y-auto pr-[5px]">
				<div v-for="c in comments" :key="c.id" class="group">
					<!-- One row, one centre line: avatar, name, time and the menu. -->
					<div class="flex h-6 items-center gap-2">
						<AuthorAvatar :username="c.author" size="sm" />
						<p class="flex min-w-0 flex-1 items-center gap-1 text-p-sm">
							<span class="min-w-0 truncate font-medium text-ink-gray-8">{{ c.name || c.author }}</span>
							<span v-if="c.noAccess" class="shrink-0 text-ink-gray-5">No access</span>
							<span class="shrink-0 text-ink-gray-5" aria-hidden="true">·</span>
							<span class="shrink-0 text-ink-gray-5" :title="whenOf(c.ts)">{{ ago(c.ts) }}</span>
							<span v-if="c.edited" class="shrink-0 text-ink-gray-4">(edited)</span>
						</p>
						<Dropdown v-if="commentMenu(c).length && editing?.id !== c.id" :options="commentMenu(c)" align="end">
							<Button
								class="-mr-[5px] shrink-0 data-[state=open]:opacity-100 [@media(hover:hover)]:opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
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
								<MentionField v-model="editing.text"><Textarea v-model="editing.text" :rows="3" class="w-full resize-none" /></MentionField>
							</div>
							<p v-if="tooLong(editing.text)" class="mt-1 text-p-sm text-ink-red-7">Over the 4 KB limit</p>
							<div class="mt-2 flex justify-end gap-2">
								<Button variant="ghost" label="Cancel" @click="editing = null" />
								<Button variant="solid" theme="gray" label="Save" :disabled="!ready(editing.text) || busy" @click="saveEdit" />
							</div>
						</template>
						<template v-else>
							<p class="whitespace-pre-wrap break-words text-p-sm text-ink-gray-7"><template v-for="(piece, i) in pieces(c.text)" :key="i"><span v-if="piece.mention" class="text-ink-blue-6">{{ piece.text }}</span><template v-else>{{ piece.text }}</template></template></p>
							<div v-if="confirming === c.id" class="mt-2">
								<p class="text-p-sm text-ink-gray-6">{{ c.id === thread.id ? 'Delete this thread?' : 'Delete this reply?' }}</p>
								<div class="mt-2 flex justify-end gap-2">
									<Button variant="ghost" label="Cancel" @click="confirming = null" />
									<Button variant="subtle" theme="red" label="Delete" :disabled="busy" @click="del(c)" />
								</div>
							</div>
						</template>
					</div>
				</div>
			</div>

			<ComposerInput v-model="replyText" class="mt-3" placeholder="Reply…" send-label="Reply" :can-send="ready(replyText) && !busy" @send="sendReply" />
			<p v-if="tooLong(replyText)" class="mt-1 text-p-sm text-ink-red-7">Over the 4 KB limit</p>
		</template>

		<!-- A new thread. -->
		<template v-else>
			<p v-if="extra" class="mb-1 text-p-sm tabular-nums text-ink-gray-5">On this and {{ extra }} more</p>
			<ComposerInput :model-value="modelValue" placeholder="Add a comment…" send-label="Comment" :can-send="canStart && !busy" @update:model-value="emit('update:modelValue', $event)" @send="start" />
			<p v-if="tooLong(modelValue)" class="mt-1 text-p-sm text-ink-red-7">Over the 4 KB limit</p>
		</template>

		<p v-if="failed" role="alert" class="mt-2 flex items-center gap-1 text-p-sm text-ink-red-7">
			<span class="lucide-triangle-alert size-3.5 shrink-0" aria-hidden="true" />
			Couldn't save.
			<Button variant="ghost" size="sm" label="Retry" :disabled="busy" @click="failed()" />
		</p>
	</div>
</template>
