// Make default, Keep only this and Delete variant, and their Undo, from the shell's own Demo pill and tile menu. The
// shell is on Sketch's origin with the reader's session, so each is a same-origin POST with Frappe's CSRF token to the
// session methods the server checks itself: `sketch.api.*_variant*` by slug (the owner only), and
// `sketch.viewer_api.delete_variant` (the owner any, an invited editor their own). Only a click on a shell element calls
// these; no frame message does.
//
// A write reloads the frame alone, so the toast and its Undo stay up through it: the shell never reloads. The owner's
// live reload is held while a write is in flight, and its baseline moves to the revision the write left, so the
// change is one reload, not two. The toast says what the server answered it did ({file, set, option, label}).
import { ref } from 'vue'
import { toast } from 'frappe-ui'
import { write } from './api'
import { onFrame, post } from './frame'

// How long an Undo toast stays: the frame takes a moment to reload, and the person then looks for the change before
// reaching for Undo.
export const UNDO_MS = 10000

type Answer = { file: string; set: string; option: string; label: string; sequence?: number | null; removed?: number; replaced?: boolean }

const ctx = {
	name: '',
	slug: '',
	role: '' as string,
	me: '',
	reload: () => {},
	// Holds the live reload; the release resolves once its baseline is the revision now.
	hold: async () => async () => {},
}
export function initActions(c: Partial<typeof ctx>) {
	Object.assign(ctx, c)
}

// What the person looking may do. The server checks each again: these only decide which buttons are drawn.
export const isOwner = () => ctx.role === 'owner'
// Every teammate's option for the owner, their own for an invited editor. Adopted variants are the owner's files now.
export const canDelete = (option: string, author: string) =>
	!!author && !!option && (isOwner() || (ctx.role === 'editor' && !!ctx.me && option.startsWith(`@${ctx.me}/`)))

// The row or tile whose write is in flight: its button spins until the frame comes back. One write at a time.
export const saving = ref<string | null>(null)
function busy(key: string | null, tileId = '') {
	if (key) placeToasts()
	saving.value = key
	post('display', { busyTile: tileId })
}
// The option a write has just put in place: the frame's canvas rings its tile once it has reloaded and drawn it.
let landing: { set: string; option: string } | null = null
onFrame('ready', () => {
	saving.value = null
	if (landing) post('display', { landed: landing })
	landing = null
})

// The write, with the live reload held around it; the frame reloads once it is saved. A refusal leaves the frame as it is.
async function landed(call: () => Promise<Answer>, land?: (a: Answer) => { set: string; option: string } | null) {
	const release = await ctx.hold()
	let answer: Answer
	try {
		answer = await call()
	} catch (e) {
		await release()
		throw e
	}
	await release()
	landing = land?.(answer) ?? null
	ctx.reload()
	return answer
}

// Toasts sit above the pill stack and the toolbar's trigger in the corner, not over them, as the frame's do
// (runtime/variants/toasts.ts): the stack's height is --sketch-variants-h, the canvas panel's room
// --sketch-panel-w.
let placed = false
export function placeToasts() {
	if (placed) return
	placed = true
	const style = document.createElement('style')
	style.textContent =
		'[data-sonner-toaster]{--offset-bottom:calc(var(--sketch-variants-h,0px) + 72px)!important;--mobile-offset-bottom:calc(var(--sketch-variants-h,0px) + 72px)!important;--offset-right:max(24px,calc(var(--sketch-panel-w,0px) + 16px))!important;}'
	document.head.append(style)
}

function withUndo(message: string, undo: (() => Promise<void>) | null) {
	if (!undo) return void toast.success(message)
	toast.success(message, {
		duration: UNDO_MS,
		action: {
			label: 'Undo',
			onClick: () => void undo().catch((e: Error) => toast.error(`Couldn't undo. ${e.message}`)),
		},
	})
}

// ---- Make default --------------------------------------------------------------------------
// `first` is the set's default before the change: where Undo lands, for the canvas's ring.
type Defaultable = { name: string; file: string; first?: { value: string } }

export const makeFailure = (e: Error) =>
	e instanceof TypeError ? "Couldn't make it the default. Check your connection and try again." : `Couldn't make it the default. ${e.message}`

// Moves `option` first in the source and saves a version. Rejects with an error fit for `makeFailure`.
export async function makeDefault(set: Defaultable, option: string, key: string, tileId = '') {
	if (saving.value) return
	busy(key, tileId)
	let done: Answer
	try {
		done = await landed(
			() => write('sketch.api.set_variant_default', { slug: ctx.slug, file: set.file, name: set.name, option }),
			(a) => ({ set: a.set, option: a.option }),
		)
	} catch (e) {
		busy(null)
		// The source already has this default: this tab is stale. The frame reloads so the row tells the truth.
		if (/already the default/.test((e as Error).message)) {
			toast.error(`Couldn't make it the default. ${(e as Error).message}`)
			return ctx.reload()
		}
		throw e
	}
	const back = set.first
	const sequence = done.sequence
	withUndo(
		`${done.label} is now the default for ${done.set}`,
		sequence
			? async () => {
					await landed(
						() => write('sketch.api.undo_variant_default', { slug: ctx.slug, file: done.file, sequence: String(sequence), name: done.set, option: done.option }),
						() => (back ? { set: done.set, option: back.value } : null),
					)
					toast.success('Default restored')
				}
			: null,
	)
}

// ---- Keep only this ------------------------------------------------------------------------
export const keepFailure = (e: Error) =>
	e instanceof TypeError ? "Couldn't keep only this. Check your connection and try again." : `Couldn't keep only this. ${e.message}`

const others = (n = 0) => (n ? `, removed ${n} other${n === 1 ? '' : 's'}` : '')

// Cuts every other option of the set (a teammate's too) and saves a version. A teammate's option is adopted first: the
// server answers with the option's new name.
export async function keepOnly(set: { name: string; file: string }, option: string, key: string, tileId = '') {
	if (saving.value) return
	busy(key, tileId)
	let done: Answer
	try {
		done = await landed(
			() => write('sketch.api.keep_variant', { slug: ctx.slug, file: set.file, name: set.name, option }),
			(a) => ({ set: a.set, option: a.option }),
		)
	} catch (e) {
		busy(null)
		throw e
	}
	const sequence = done.sequence
	withUndo(
		`Kept ${done.replaced ? `${done.set} · ` : ''}${done.label}${others(done.removed)}`,
		sequence
			? async () => {
					await landed(
						() => write('sketch.api.undo_keep_variant', { slug: ctx.slug, file: done.file, sequence: String(sequence), name: done.set, option: done.option }),
						() => ({ set: done.set, option: done.option }),
					)
					toast.success('Options restored')
				}
			: null,
	)
}

// ---- Delete variant ------------------------------------------------------------------------
export const deleteFailure = (e: Error) =>
	e instanceof TypeError ? "Couldn't delete the variant. Check your connection and try again." : `Couldn't delete the variant. ${e.message}`

export async function deleteVariant(option: string, key: string, tileId = '') {
	if (saving.value) return
	busy(key, tileId)
	let done: Answer
	try {
		done = await landed(() => write('sketch.viewer_api.delete_variant', { name: ctx.name, option }))
	} catch (e) {
		busy(null)
		throw e
	}
	const sequence = done.sequence
	withUndo(
		`Deleted ${done.label}`,
		sequence
			? async () => {
					const back = await landed(() => write('sketch.viewer_api.undo_delete_variant', { name: ctx.name, sequence: String(sequence) }))
					toast.success(`Restored ${back.label || done.label}`)
				}
			: null,
	)
}
