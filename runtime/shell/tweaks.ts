// Tweak in the Viewer shell: the tweaks themselves, the list's rows and the prompt (the pure half is runtime/shared/tweak.ts,
// the same one the in-frame tool uses), and the edits the panel makes. The page is in the frame, so every edit is sent there
// to be written (runtime/agent/tweakPick.ts), and the frame answers with what the selected elements now are (`facts`).
//
// The tweaks are the person's own and are saved from here (notes.ts, sketch.viewer_api.save_annotations): only an edit made
// in the shell's panel or list changes them. The frame's answers only change what the panel shows. What goes to the frame
// is the tweaks' class, prop and copy edits, never anything about a person.
import { computed, ref, shallowRef, watch } from 'vue'
import {
	CANDIDATES,
	isChanged,
	itemsOf,
	restoreTweaks,
	rowsOf,
	tweakPrompt,
	type Copy,
	type GroupMeta,
	type Tokens,
	type Tweak,
	type TweakItem,
} from '../shared/tweak'
import type { ClassEdit, PropEdit, PropValue, Rect, TweakFacts, TweakSync } from '../shared/protocol'
import { newId } from '../annotate/annotate'
import { pageNameOf, subject } from '../annotate/host'
import { onFrame, page, post } from './frame'

// ---- The tweaks -------------------------------------------------------------------------------
export const tweaks = ref<Tweak[]>([])
export const restoreTweakRows = (rows: unknown) => (tweaks.value = restoreTweaks(rows))
// The ref of the element each tweak made this visit was made on, for the frame to find it by.
const madeOn = new Map<string, string>()

// What the frame last said: the selected elements, their alike count, the tokens, each stack's size, the outlines.
export const facts = shallowRef<TweakFacts[]>([])
export const alike = ref({ total: 0, joinable: 0 })
export const anchor = shallowRef<{ fx: number; fy: number } | null>(null)
export const tokens = shallowRef<Tokens>(CANDIDATES)
const stacks = shallowRef<Record<string, number>>({})
export const say = shallowRef<{ text: string; x: number; y: number } | null>(null)
export const outlines = shallowRef<{ sel: Rect | null; others: Rect[]; faint: Rect[]; hover: Rect | null; hoverName: string; hl: Rect[]; peek: boolean }>({
	sel: null,
	others: [],
	faint: [],
	hover: null,
	hoverName: '',
	hl: [],
	peek: false,
})
// Bumped after every commit so the panel reads again.
export const rev = ref(0)
const touch = () => void rev.value++

let req = 0
const nextReq = () => `t${++req}`
const finding = new Map<string, (found: boolean) => void>()
let sayTimer = 0
onFrame('tweak:info', (d) => {
	if (d.sels) {
		facts.value = d.sels
		alike.value = { total: d.total ?? 0, joinable: d.joinable ?? 0 }
		anchor.value = d.anchor ?? null
	}
	if (d.tokens) {
		const t = { ...CANDIDATES }
		// Only candidates: a token name the frame made up is never offered.
		for (const g of Object.keys(CANDIDATES) as (keyof Tokens)[]) if (d.tokens[g]) t[g] = CANDIDATES[g].filter((c) => d.tokens![g].includes(c))
		tokens.value = t
	}
	if (d.stacks) stacks.value = d.stacks
	if (d.say) {
		say.value = d.say
		clearTimeout(sayTimer)
		sayTimer = window.setTimeout(() => (say.value = null), 1200)
	}
	if (d.found !== undefined) {
		finding.get(d.req)?.(d.found)
		finding.delete(d.req)
	}
})
onFrame('tweak:rects', (r) => (outlines.value = r))

// ---- Keeping the frame up to date -----------------------------------------------------------------
const syncOf = (t: Tweak): TweakSync => ({
	id: t.id,
	route: t.route,
	selector: t.selector,
	opener: t.opener ?? '',
	original: { classes: t.original.classes, props: plainProps(t.original.props) },
	classes: t.classes,
	props: plainProps(t.props),
	copies: (t.copies ?? []).map((c) => ({ i: c.i, from: c.from, to: c.to, stem: !!c.stem })),
})
const plainProps = (p: Record<string, any>) => {
	const out: Record<string, PropValue> = {}
	for (const [k, v] of Object.entries(p)) if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') out[k] = v
	return out
}
function sendTweaks() {
	const bind: Record<string, string> = {}
	for (const t of tweaks.value) {
		const r = madeOn.get(t.id)
		if (r) bind[t.id] = r
	}
	post('tweak:reapply', { tweaks: tweaks.value.map(syncOf), bind })
}
// Every change, and every fresh frame (a live reload knows nothing of them).
watch(() => JSON.stringify(tweaks.value), sendTweaks)
watch(
	() => page.ready,
	(ok) => ok && sendTweaks(),
)

// ---- Rows, count, prompt --------------------------------------------------------------------------
const rows = computed(() => rowsOf(tweaks.value.filter(isChanged)))
// One multi-select edit counts once, as the list shows it.
export const tweakCount = computed(() => rows.value.length)
// How many things a vertical stack holds: counted live where the frame can see it, else as it was when the tweak was made.
const stackCount = (t: Tweak) => stacks.value[t.id] ?? t.items ?? 0
export const tweakItems = computed<TweakItem[]>(() => itemsOf(rows.value, stackCount, pageNameOf))
export const buildTweakPrompt = (): string => tweakPrompt(rows.value, subject())
export const hasTweaks = () => tweaks.value.some(isChanged)
// The ids of a row's tweaks.
export const idsOfRow = (id: string): string[] => rows.value.find((x) => x.id === id)?.ts.map((t) => t.id) ?? []
export const routeOfRow = (id: string): string | undefined => rows.value.find((x) => x.id === id)?.ts[0].route

// ---- Editing --------------------------------------------------------------------------------------
// The tweak of a selected element: the one the frame knows it by, or the one made on it this visit.
export const tweakOf = (f: TweakFacts): Tweak | undefined =>
	tweaks.value.find((t) => t.id === f.tweak) ?? tweaks.value.find((t) => madeOn.get(t.id) === f.ref && t.route === page.key)

// Made on the first preview, before any write, so `original` is the page as it was.
function ensureTweak(f: TweakFacts): Tweak {
	const ex = tweakOf(f)
	if (ex) return ex
	const w = f.where
	const props: Record<string, any> = {}
	for (const k of f.known) props[k] = f.props[k]
	const t: Tweak = {
		id: newId(),
		route: page.key,
		selector: w.selector,
		component: w.component,
		file: w.file,
		path: w.path,
		kind: f.kind,
		element: w.element,
		text: w.text,
		label: w.label || undefined,
		items: f.stack ? w.items : undefined,
		opener: w.opener || undefined,
		viewport: w.viewport,
		original: { classes: [...f.classes], props: { ...props } },
		classes: [...f.classes],
		props,
	}
	madeOn.set(t.id, f.ref)
	tweaks.value = [...tweaks.value, t]
	return tweaks.value[tweaks.value.length - 1]
}

// Drop tweaks that match the page again.
function settle() {
	const keep = tweaks.value.filter(isChanged)
	if (keep.length !== tweaks.value.length) {
		for (const t of tweaks.value) if (!keep.includes(t)) madeOn.delete(t.id)
		tweaks.value = keep
	}
}

// A multi-element commit is one group; a later edit of an element alone leaves it.
function tagGroup(fs: TweakFacts[], g?: GroupMeta) {
	for (const f of fs) {
		const t = tweakOf(f)
		if (!t) continue
		if (g && fs.length > 1) {
			t.group = g.id
			t.alike = g.alike
		} else {
			delete t.group
			delete t.alike
		}
	}
}

export type ClassStep = [TweakFacts, string[]]
export type PropStep = [TweakFacts, any]
const classEdits = (list: ClassStep[]): ClassEdit[] => list.map(([f, classes]) => ({ ref: f.ref, classes }))
const propEdits = (list: PropStep[]): PropEdit[] =>
	list.map(([f, v]) => ({ ref: f.ref, value: typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' ? v : null }))

export function previewClasses(list: ClassStep[]) {
	list.forEach(([f]) => ensureTweak(f))
	post('tweak:preview', { req: nextReq(), edits: classEdits(list) })
}
export function commitClasses(list: ClassStep[], g?: GroupMeta) {
	for (const [f, n] of list) ensureTweak(f).classes = Array.from(new Set(n))
	post('tweak:commit', { req: nextReq(), edits: classEdits(list) })
	tagGroup(list.map(([f]) => f), g)
	settle()
	touch()
}
export function cancelPreview(list: ClassStep[]) {
	post('tweak:cancel', { req: nextReq(), edits: classEdits(list) })
	settle()
}
export function setProps(list: PropStep[], key: string, commit: boolean, g?: GroupMeta) {
	list.forEach(([f]) => ensureTweak(f))
	post('tweak:props', { req: nextReq(), key, phase: commit ? 'commit' : 'preview', edits: propEdits(list) })
	if (!commit) return
	for (const [f, v] of list) {
		const t = tweakOf(f)
		if (t && f.known.includes(key)) t.props[key] = v
	}
	tagGroup(list.map(([f]) => f), g)
	settle()
	touch()
}
export function cancelProps(list: PropStep[], key: string) {
	post('tweak:props', { req: nextReq(), key, phase: 'cancel', edits: propEdits(list) })
	settle()
}

// The Copy fields of one element: what the frame found, with the words as this list last left them.
export function copyFieldsOf(f: TweakFacts): Copy[] {
	const t = tweakOf(f)
	return f.copies.map((c) => {
		const kept = t?.copies?.find((x) => x.i === c.i)
		return kept ? { ...kept, files: kept.files ?? [] } : { ...c }
	})
}
export function setCopy(f: TweakFacts, i: number, to: string) {
	const info = copyFieldsOf(f).find((c) => c.i === i)
	if (!info) return
	const t = ensureTweak(f)
	t.copies ??= []
	let c = t.copies.find((x) => x.i === i)
	if (!c) t.copies.push((c = { i, from: info.from, to: info.from, files: info.files, stem: info.stem }))
	c.to = to
	post('tweak:copy', { req: nextReq(), ref: f.ref, i, to, stem: !!c.stem })
	settle()
	touch()
}

// "Add to prompt" on a hand-rolled element: a change that is only a note for the agent.
export function toggleSwap(f: TweakFacts, name: string) {
	const t = ensureTweak(f)
	t.swap = t.swap ? '' : name
	settle()
	touch()
}

// Revert one row, or every tweak: the frame puts the page back once the list no longer has them.
export function removeTweak(id: string) {
	const gone = new Set(idsOfRow(id))
	if (!gone.size) return
	for (const g of gone) madeOn.delete(g)
	tweaks.value = tweaks.value.filter((x) => !gone.has(x.id))
	touch()
}
export function resetAll() {
	madeOn.clear()
	tweaks.value = []
	touch()
}

// ---- The selection, which the frame holds -----------------------------------------------------------
export const inspect = (op: 'clear' | 'all' | 'parent' | 'child' | 'refresh' | 'select') => post('tweak:inspect', { req: nextReq(), op })
export const highlight = (id: string | null) => post('tweak:inspect', { req: nextReq(), op: 'highlight', ids: id ? idsOfRow(id) : [] })
export const tellKeys = (k: { shift?: boolean; peek?: boolean }) => post('tweak:inspect', { req: nextReq(), op: 'keys', ...k })
// Find a row's elements (opening the popover they live in): true once they are on the page.
export function findRow(id: string): Promise<boolean> {
	const r = nextReq()
	return new Promise((done) => {
		const t = setTimeout(() => {
			finding.delete(r)
			done(false)
		}, 6000)
		finding.set(r, (ok) => {
			clearTimeout(t)
			done(ok)
		})
		post('tweak:inspect', { req: r, op: 'find', ids: idsOfRow(id) })
	})
}
