// The messages between the Viewer shell (Sketch's page, on Sketch's origin) and the Prototype's frame
// (sandboxed, an opaque origin). The frame runs code anyone may have written, so every message from it
// is untrusted input: the shell takes one only from its own iframe (`e.source === iframe.contentWindow`
// and `e.origin === 'null'`), only of a type named here, and only after that type's validator has
// rebuilt it from scratch with every number clamped and every string and list capped. A validator
// returns null for anything it cannot read, and the shell drops it.
//
// No message can cause a write. A write starts from a click or key on a shell element; a message can
// only move what the shell draws. Strings from the frame are shown as text, never as HTML.
//
// The shell posts to the frame with targetOrigin '*' (an opaque origin has no name to target), so
// nothing it sends is ever secret: never comment or note text, never people's data, never a token.

export const CHANNEL = 'sketch-shell'

export const CAPS = {
	number: 1e5,
	route: 2000,
	label: 300,
	selector: 2000,
	text: 2000,
	tiles: 500,
	rects: 200,
	options: 200,
	sets: 200,
	list: 200,
} as const

export type Rect = { x: number; y: number; w: number; h: number }
type Obj = Record<string, unknown>

// ---- Readers ------------------------------------------------------------------------------
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)

export function num(v: unknown): number | null {
	if (typeof v !== 'number' || !Number.isFinite(v)) return null
	return Math.max(-CAPS.number, Math.min(v, CAPS.number))
}
export const str = (v: unknown, cap: number = CAPS.label): string | null =>
	typeof v === 'string' ? v.slice(0, cap) : null
export const bool = (v: unknown): boolean | null => (typeof v === 'boolean' ? v : null)
export const oneOf = <T extends string>(v: unknown, values: readonly T[]): T | null =>
	typeof v === 'string' && (values as readonly string[]).includes(v) ? (v as T) : null

export function rect(v: unknown): Rect | null {
	if (!isObj(v)) return null
	const [x, y, w, h] = [num(v.x), num(v.y), num(v.w ?? v.width), num(v.h ?? v.height)]
	return x === null || y === null || w === null || h === null ? null : { x, y, w, h }
}
export function list<T>(v: unknown, cap: number, item: (x: unknown) => T | null): T[] | null {
	if (!Array.isArray(v)) return null
	const out: T[] = []
	for (const x of v.slice(0, cap)) {
		const read = item(x)
		if (read !== null) out.push(read)
	}
	return out
}
// A map of id to value, at most `cap` entries; ids are capped strings.
export function record<T>(v: unknown, cap: number, item: (x: unknown) => T | null): Record<string, T> | null {
	if (!isObj(v)) return null
	const out: Record<string, T> = {}
	for (const [k, x] of Object.entries(v).slice(0, cap)) {
		const read = item(x)
		if (read !== null) out[k.slice(0, CAPS.label)] = read
	}
	return out
}
const strings = (v: unknown, cap: number = CAPS.list, len: number = CAPS.label) => list(v, cap, (x) => str(x, len))

// Every field must read, or the whole message is dropped.
function all<T extends Obj>(out: { [K in keyof T]: T[K] | null }): T | null {
	return Object.values(out).some((x) => x === null) ? null : (out as T)
}
// Optional fields read when present and are left out when absent or unreadable.
function some<T extends Obj>(out: Obj): T {
	for (const k of Object.keys(out)) if (out[k] === null || out[k] === undefined) delete out[k]
	return out as T
}

// ---- Shared shapes --------------------------------------------------------------------------
export const THEMES = ['light', 'dark'] as const
export type Theme = (typeof THEMES)[number]
export const MODES = ['note', 'tweak', 'comment'] as const
export type Mode = (typeof MODES)[number]

// Which canvas tile a pin sits on: runtime/variants/bridge.ts TileRef, in plain data.
export type TileRef = {
	kind: 'set' | 'state' | 'default'
	view: string
	page: string
	group: string
	groupKey: string
	option: string
	optionLabel: string
}
export const tileRef = (v: unknown): TileRef | null =>
	isObj(v)
		? all<TileRef>({
				kind: oneOf(v.kind, ['set', 'state', 'default'] as const),
				view: str(v.view, CAPS.route),
				page: str(v.page),
				group: str(v.group),
				groupKey: str(v.groupKey),
				option: str(v.option),
				optionLabel: str(v.optionLabel),
			})
		: null

export type TileSpot = { route: string; tile: TileRef }
const tileSpot = (v: unknown): TileSpot | null => (isObj(v) ? all<TileSpot>({ route: str(v.route, CAPS.route), tile: tileRef(v.tile) }) : null)

export type ElInfo = { selector: string; component: string; element: string; text: string; state: string }
const elInfo = (v: unknown): ElInfo | null =>
	isObj(v)
		? all<ElInfo>({
				selector: str(v.selector, CAPS.selector),
				component: str(v.component),
				element: str(v.element),
				text: str(v.text, CAPS.text),
				state: str(v.state ?? '', CAPS.text),
			})
		: null

export type BoxInfo = {
	kind: 'content' | 'empty'
	fx: number
	fy: number
	fw: number
	fh: number
	covers?: string[]
	coversMore?: number
	before?: string
	after?: string
	gap?: number
	axis?: 'vertical' | 'horizontal'
}
const box = (v: unknown): BoxInfo | null => {
	if (!isObj(v)) return null
	const base = all({ kind: oneOf(v.kind, ['content', 'empty'] as const), fx: num(v.fx), fy: num(v.fy), fw: num(v.fw), fh: num(v.fh) })
	if (!base) return null
	return some<BoxInfo>({
		...base,
		covers: strings(v.covers, CAPS.list, CAPS.selector),
		coversMore: num(v.coversMore),
		before: str(v.before, CAPS.text),
		after: str(v.after, CAPS.text),
		gap: num(v.gap),
		axis: oneOf(v.axis, ['vertical', 'horizontal'] as const),
	})
}

// ---- Frame -> shell -----------------------------------------------------------------------
export type FromFrame = {
	ready: { status: string; routes: string[] }
	route: { fullPath: string }
	theme: { theme: Theme }
	layout: { vw: number; vh: number; navBottom: number; pageLayerOpen: boolean }
	model: { sets: ModelSet[]; states: ModelState[]; pages: string[] }
	hover: { rect: Rect; label: string } | { rect: null }
	pick: Pick
	rects: { req: string; map: Record<string, Rect | null> }
	track: { map: Record<string, Rect | null> }
	canvas: { open: boolean; phone: boolean; view: string; zoom: number; pan: { x: number; y: number }; tiles: CanvasTile[] }
	'tile:menu': { tileId: string; rect: Rect }
	'tile:pick': { spot: TileSpot; fx: number; fy: number; x: number; y: number }
	key: { key: string; mods: string[] }
	'tweak:info': { req: string } & Obj
}
export type ModelOption = { value: string; label: string; author: string }
export type ModelSet = { id: string; key: string; name: string; label: string; file: string; path: string; options: ModelOption[] }
export type ModelState = { id: string; label: string; value: string; options: string[] }
export type CanvasTile = { id: string; rect: Rect; tile: TileRef; label: string; isDefault: boolean; isNew: boolean; author: string }
export type Pick = {
	el: ElInfo
	componentChain: string[]
	file: string
	rect: Rect
	offset: { x: number; y: number }
	route: string
	viewport: string
	extras: ElInfo[]
	box?: BoxInfo
}

const point = (v: unknown) => (isObj(v) ? all({ x: num(v.x), y: num(v.y) }) : null)
const rectOrNull = (v: unknown): Rect | null => (v === null ? null : rect(v))
// `record` drops a null value, so a rect that is gone (null) is kept as a marker and read back here.
const rectMap = (v: unknown) => {
	if (!isObj(v)) return null
	const out: Record<string, Rect | null> = {}
	for (const [k, x] of Object.entries(v).slice(0, CAPS.rects)) out[k.slice(0, CAPS.label)] = rectOrNull(x)
	return out
}
const modelOption = (v: unknown): ModelOption | null =>
	isObj(v) ? all<ModelOption>({ value: str(v.value), label: str(v.label), author: str(v.author ?? '') }) : null
const modelSet = (v: unknown): ModelSet | null =>
	isObj(v)
		? all<ModelSet>({
				id: str(v.id),
				key: str(v.key),
				name: str(v.name),
				label: str(v.label),
				file: str(v.file, CAPS.route),
				path: str(v.path, CAPS.route),
				options: list(v.options, CAPS.options, modelOption),
			})
		: null
const modelState = (v: unknown): ModelState | null =>
	isObj(v) ? all<ModelState>({ id: str(v.id), label: str(v.label), value: str(v.value), options: strings(v.options, CAPS.options) }) : null
const canvasTile = (v: unknown): CanvasTile | null =>
	isObj(v)
		? all<CanvasTile>({
				id: str(v.id),
				rect: rect(v.rect),
				tile: tileRef(v.tile),
				label: str(v.label),
				isDefault: bool(v.isDefault ?? false),
				isNew: bool(v.isNew ?? false),
				author: str(v.author ?? ''),
			})
		: null

export const fromFrame: { [K in keyof FromFrame]: (d: Obj) => FromFrame[K] | null } = {
	ready: (d) => all({ status: str(d.status, 40), routes: strings(d.routes, CAPS.list, CAPS.route) }),
	route: (d) => all({ fullPath: str(d.fullPath, CAPS.route) }),
	theme: (d) => all({ theme: oneOf(d.theme, THEMES) }),
	layout: (d) => all({ vw: num(d.vw), vh: num(d.vh), navBottom: num(d.navBottom), pageLayerOpen: bool(d.pageLayerOpen) }),
	model: (d) =>
		all({ sets: list(d.sets, CAPS.sets, modelSet), states: list(d.states, CAPS.sets, modelState), pages: strings(d.pages, CAPS.list, CAPS.route) }),
	hover: (d) => (d.rect === null ? { rect: null } : all({ rect: rect(d.rect), label: str(d.label) })),
	pick: (d) => {
		const base = all({
			el: elInfo(d.el),
			componentChain: strings(d.componentChain),
			file: str(d.file ?? '', CAPS.route),
			rect: rect(d.rect),
			offset: point(d.offset),
			route: str(d.route, CAPS.route),
			viewport: str(d.viewport, 40),
			extras: list(d.extras ?? [], CAPS.rects, elInfo),
		})
		return base && some<Pick>({ ...base, box: d.box === undefined ? null : box(d.box) })
	},
	rects: (d) => all({ req: str(d.req, 40), map: rectMap(d.map) }),
	track: (d) => all({ map: rectMap(d.map) }),
	canvas: (d) =>
		all({
			open: bool(d.open),
			phone: bool(d.phone),
			view: str(d.view, 40),
			zoom: num(d.zoom),
			pan: point(d.pan),
			tiles: list(d.tiles, CAPS.tiles, canvasTile),
		}),
	'tile:menu': (d) => all({ tileId: str(d.tileId), rect: rect(d.rect) }),
	'tile:pick': (d) => all({ spot: tileSpot(d.spot), fx: num(d.fx), fy: num(d.fy), x: num(d.x), y: num(d.y) }),
	// Escape and the tool shortcuts only: the frame has the focus while a person works in the page.
	key: (d) => all({ key: oneOf(d.key, ['Escape', 'n', 't', 'c', 'N', 'T', 'C']), mods: list(d.mods, 4, (m) => oneOf(m, ['shift', 'alt', 'ctrl', 'meta'] as const)) }),
	// Tweak's shape is settled with Tweak (plan step 6); until then only the request id is read.
	'tweak:info': (d) => all({ req: str(d.req, 40) }),
}

// ---- Shell -> frame -----------------------------------------------------------------------
export type ToFrame = {
	tool: { mode: Mode; active: boolean }
	resolve: { req: string; selectors: string[] }
	track: { map: Record<string, string> }
	nav: { path: string }
	'state:set': { id: string; value: string }
	'picks:apply': { picks: Record<string, string> }
	'canvas:open': { view?: string }
	'canvas:close': Obj
	'canvas:reveal': { tile: TileRef }
	display: { newOptions: string[]; reserve: number; corner: string; toolbarLift: number }
	theme: { theme: Theme }
	// The two facts the frame's status screen (empty, did not build) words itself by. Sent only with that screen up.
	copy: { owner: boolean; reloads: boolean }
	scrollTo: { selector: string }
	'tweak:inspect': { req: string; selector: string }
	'tweak:preview': { req: string } & Obj
	'tweak:commit': { req: string } & Obj
	'tweak:cancel': { req: string }
	'tweak:props': { req: string } & Obj
	'tweak:copy': { req: string }
	'tweak:reapply': Obj
}

// The frame checks `e.source === parent` and these, so a message from anywhere else does nothing.
export const toFrame: { [K in keyof ToFrame]: (d: Obj) => ToFrame[K] | null } = {
	tool: (d) => all({ mode: oneOf(d.mode, MODES), active: bool(d.active) }),
	resolve: (d) => all({ req: str(d.req, 40), selectors: strings(d.selectors, CAPS.rects, CAPS.selector) }),
	track: (d) => {
		const map = record(d.map, CAPS.rects, (x) => str(x, CAPS.selector))
		return map && { map }
	},
	nav: (d) => all({ path: str(d.path, CAPS.route) }),
	'state:set': (d) => all({ id: str(d.id), value: str(d.value) }),
	'picks:apply': (d) => {
		const picks = record(d.picks, CAPS.sets, (x) => str(x))
		return picks && { picks }
	},
	'canvas:open': (d) => some({ view: str(d.view, 40) }),
	'canvas:close': () => ({}),
	'canvas:reveal': (d) => all({ tile: tileRef(d.tile) }),
	display: (d) =>
		all({ newOptions: strings(d.newOptions, CAPS.options), reserve: num(d.reserve), corner: str(d.corner, 40), toolbarLift: num(d.toolbarLift) }),
	theme: (d) => all({ theme: oneOf(d.theme, THEMES) }),
	copy: (d) => all({ owner: bool(d.owner), reloads: bool(d.reloads) }),
	scrollTo: (d) => all({ selector: str(d.selector, CAPS.selector) }),
	'tweak:inspect': (d) => all({ req: str(d.req, 40), selector: str(d.selector, CAPS.selector) }),
	'tweak:preview': (d) => all({ req: str(d.req, 40) }),
	'tweak:commit': (d) => all({ req: str(d.req, 40) }),
	'tweak:cancel': (d) => all({ req: str(d.req, 40) }),
	'tweak:props': (d) => all({ req: str(d.req, 40) }),
	'tweak:copy': (d) => all({ req: str(d.req, 40) }),
	'tweak:reapply': () => ({}),
}

// ---- Envelope -----------------------------------------------------------------------------
export type Message<M, K extends keyof M = keyof M> = { type: K; data: M[K] }

// One message on the wire: { channel, type, data }.
export function envelope<M, K extends keyof M>(type: K, data: M[K]) {
	return { channel: CHANNEL, type, data }
}

// Read one message against a validator table: null unless it is ours, of a known type, and valid.
export function read<M>(raw: unknown, table: { [K in keyof M]: (d: Obj) => M[K] | null }): Message<M> | null {
	if (!isObj(raw) || raw.channel !== CHANNEL || typeof raw.type !== 'string') return null
	if (!Object.prototype.hasOwnProperty.call(table, raw.type)) return null
	const type = raw.type as keyof M
	const data = table[type](isObj(raw.data) ? raw.data : {})
	return data === null ? null : { type, data }
}
