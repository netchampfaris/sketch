// The messages between the Viewer shell (Sketch's page, on Sketch's origin) and the Prototype's frame
// (sandboxed, an opaque origin). The frame runs code anyone may have written, so every message from it
// is untrusted input: the shell takes one only from its own iframe (`e.source === iframe.contentWindow`
// and `e.origin === 'null'`), only of a type named here, and only after that type's validator has
// rebuilt it from scratch with every number clamped and every string and list capped. A validator
// returns null for anything it cannot read, and the shell drops it.
//
// No message can cause a write, but one: `theme:choose`, the Prototype's own theme switch, which the shell saves only
// as one of three values on the reader's own display preference, and only right after the person's own click or key.
// Every other write starts from a click or key on a shell element; a message can only move what the shell draws. Strings from the frame are shown as text, never as HTML.
//
// The shell posts to the frame with targetOrigin '*' (an opaque origin has no name to target), so
// nothing it sends is ever secret: never comment or note text, never people's data, never a token.

import type { DemoEntry, DemoPick } from './picks'

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
	// Tweak: the alike elements of a pick (runtime/agent/tweakDom.ts alikeOf stops at 300), the tweaks kept, the classes
	// of one element, the token names of one group.
	alike: 300,
	tweaks: 500,
	classes: 120,
	tokens: 200,
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
// A computed CSS colour, or ''. Only colour functions and hex: nothing the shell's style could fetch.
export const color = (v: unknown): string | null =>
	typeof v === 'string' && /^(|transparent|#[0-9a-f]{3,8}|(rgba?|hsla?|oklch|oklab|lab|lch|color)\([a-z0-9.,%\s/+-]*\))$/i.test(v) && v.length <= 80 ? v : null
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

// The Demo picks a comment was made on (runtime/shared/picks.ts), as the frame reports them.
const demoPick = (v: unknown): DemoPick | null =>
	isObj(v)
		? all<DemoPick>({
				kind: oneOf(v.kind, ['set', 'state'] as const),
				path: str(v.path, CAPS.route),
				key: str(v.key),
				label: str(v.label),
				option: str(v.option),
				optionLabel: str(v.optionLabel),
				default: bool(v.default),
			})
		: null
const demoEntry = (v: unknown): DemoEntry | null =>
	isObj(v)
		? all<DemoEntry>({
				kind: oneOf(v.kind, ['set', 'state'] as const),
				path: str(v.path, CAPS.route),
				key: str(v.key),
				value: str(v.value),
				options: strings(v.options, CAPS.options),
			})
		: null

export type Redline = Rect & { label: string; lx: number; ly: number }
const redline = (v: unknown): Redline | null => {
	const r = rect(v)
	if (!r || !isObj(v)) return null
	const rest = all({ label: str(v.label, 20), lx: num(v.lx), ly: num(v.ly) })
	return rest && { ...r, ...rest }
}

// ---- Frame -> shell -----------------------------------------------------------------------
export type FromFrame = {
	// `pages` names each route record the way the canvas does (meta.title, else the component), for the lists.
	ready: { status: string; routes: string[]; pages: Page[] }
	// `key` is the route a note belongs to (runtime/agent/dom.ts routeKey); `path` the route's path alone.
	route: { fullPath: string; path: string; key: string }
	theme: { theme: Theme }
	// The Prototype's own theme switch chose light, dark or system (runtime/viewer/boot.js): the shell saves it, only
	// on the person's own click or key (runtime/shell/theme.ts).
	'theme:choose': { theme: Theme | 'system' }
	// `backdrop` is the colour a page dialog's backdrop lays over the page ('' with none open), and `layers` the rects of
	// what the page draws above it (the dialog's panel, a menu from it): the shell's Demo pill sits under both, as it
	// did in the page.
	layout: { vw: number; vh: number; navBottom: number; pageLayerOpen: boolean; dialogOpen: boolean; backdrop: string; layers: Rect[] }
	// The Demo pill's rows on this page, in page order, and whether the card's foot offers "Open canvas".
	model: { sets: ModelSet[]; states: ModelState[]; canOpen: boolean }
	// The element under the pointer while a tool picks, its label, and with Alt held the distances to the selection.
	hover: { rect: Rect | null; label: string; lines: Redline[]; alt: boolean; shift: boolean }
	pick: Pick
	// A box being dragged out while a tool picks, or null when the drag ends.
	drag: { rect: Rect | null }
	// Every mounted Demo set and state, with what it shows.
	demo: { entries: DemoEntry[] }
	rects: { req: string; map: Record<string, Rect | null> }
	track: { map: Record<string, Rect | null>; labels: Record<string, string> }
	// The canvas as it is drawn: what it shows (`view`), the pan and zoom, and how wide the zoom pill in the bottom-right
	// corner is. `tiles` (in the canvas's own coordinates, before pan and zoom), `pages` and `items` (the Show list's rows)
	// come only when they changed: the pan and zoom alone come once per frame while they move.
	canvas: {
		open: boolean
		phone: boolean
		view: string
		zoom: number
		pan: { x: number; y: number }
		corner: number
		tiles?: CanvasTile[]
		pages?: CanvasPage[]
		items?: PickItem[]
		// One option's states with none built: the option's own tile of its set (where its note goes), and its words.
		empty?: EmptyView | null
	}
	'tile:menu': { tileId: string; rect: Rect }
	// The phone's title pill: open the Show list under its name, at the name's box, or close it.
	'canvas:show': { rect: Rect; open: boolean }
	'tile:pick': { spot: TileSpot; fx: number; fy: number; x: number; y: number }
	// A click on the canvas off every tile while a tool is in hand: the shell's comment box closes, as a click outside does.
	'canvas:click': Obj
	// The answer to `canvas:reveal`: where the spot is on the screen now, or null when the canvas has no such tile.
	'canvas:revealed': { req: string; point: { x: number; y: number } | null }
	// `layer` says what was open in the page when the key went down: a dialog, another layer (a menu, a popover,
	// a list), or nothing. That layer takes Escape itself, before the shell hears of it.
	key: { key: string; mods: string[]; layer: '' | 'dialog' | 'layer' }
	// Tweak's answers: what the selected elements are and hold (`sels`, with the count of alike elements and how many of
	// them could join), the tokens this Runtime styles, how many things each tweaked stack holds, a word next to the
	// pointer (a pick that cannot join), and whether a list row's elements were found. Each part comes only when it
	// changed or was asked for; `req` names the ask it answers ('' when the frame speaks first).
	'tweak:info': TweakInfo
	// Where Tweak's outlines go, once a frame while something moves: the last pick, the others, their alike copies on
	// screen, the hovered element and its name, the elements of a hovered list row. `peek` is Space held in the page.
	'tweak:rects': TweakRects
}
export type TweakCopy = { i: number; from: string; to: string; files: string[]; stem: boolean }
// The element's own facts, for the tweak a first edit makes: where it is and what it says.
export type TweakWhere = {
	selector: string
	component: string
	file: string
	path: string[]
	element: string
	text: string
	label: string
	items: number
	opener: string
	viewport: string
}
// One selected element. `tweak` is the id of the tweak the frame holds for it ('' for none); `classes` and `props` are what
// it has now (props only for a frappe-ui component, `known` being the ones its instance declares); `cs` the computed
// sizes the empty fields show; `notes` the responsive and state variants per category.
export type TweakFacts = {
	ref: string
	tweak: string
	name: string
	kind: string
	classes: string[]
	known: string[]
	props: Record<string, PropValue>
	cs: Record<string, string>
	notes: Record<string, string>
	hasText: boolean
	bordered: boolean
	rolled: string
	stack: boolean
	copies: TweakCopy[]
	where: TweakWhere
}
export type PropValue = string | number | boolean
export type TweakInfo = {
	req: string
	sels?: TweakFacts[]
	total?: number
	joinable?: number
	anchor?: { fx: number; fy: number } | null
	tokens?: Record<string, string[]>
	stacks?: Record<string, number>
	say?: { text: string; x: number; y: number }
	found?: boolean
	// The page was pressed or scrolled while Tweak is the tool: what the shell has open closes, as on a press outside it.
	outside?: boolean
}
export type TweakRects = { sel: Rect | null; others: Rect[]; faint: Rect[]; hover: Rect | null; hoverName: string; hl: Rect[]; peek: boolean }
export type Page = { path: string; title: string }
export type ModelOption = { value: string; label: string; author: string }
// `id` is `set:<path>::<key>` (or `state:…`), what `state:set` names. `value` is the option on show, `view` the canvas view
// that shows the set, `rect` its box on the page when last measured (null when it draws nothing). `path` '' is app-wide.
export type ModelSet = {
	id: string
	key: string
	name: string
	label: string
	file: string
	path: string
	value: string
	view: string
	rect: Rect | null
	options: ModelOption[]
}
// `groups` is there only when the state was declared in groups ({ Data: ['Default', 'Loading'], Access: [...] }).
export type ModelState = { id: string; label: string; path: string; value: string; options: string[]; groups?: { title: string; options: string[] }[] }
// `rect` is in the canvas's own coordinates: the screen point is pan + rect * zoom.
// A set's tile also says which `<Variants>` it is (its name and file) and how many options the set has: what Make default
// and Keep only this ask the server for. A lying frame can only name another option for the owner's real click.
export type CanvasTile = {
	id: string
	route: string
	rect: Rect
	tile: TileRef
	label: string
	isDefault: boolean
	author: string
	setName: string
	setFile: string
	setCount: number
}
// What the canvas found on a page, enough to tell whether a pinned tile still exists (sets by key with their option
// values, states by key with their options, and the set options a component state can name, as slugs).
export type CanvasPage = { path: string; title: string; sets: { key: string; options: string[] }[]; states: { key: string; options: string[] }[]; ofs: string[] }
// An option's States view that has nothing to show (runtime/variants/Canvas.vue): the shell says so and offers Ask
// agent, a note on `spot` that opens with the set, the option and its file.
export type EmptyView = { spot: TileSpot; set: string; option: string; file: string }
const emptyView = (v: unknown): EmptyView | null =>
	isObj(v) ? all<EmptyView>({ spot: tileSpot(v.spot), set: str(v.set), option: str(v.option), file: str(v.file ?? '', CAPS.route) }) : null
// One row of the Show list (runtime/variants/picker.ts PickItem).
export type PickItem = { value: string; label: string; sub: string; short: string; group: 'sets' | 'pages'; options: string[] }
export type ComponentInfo = { component: string; chain: string[]; file: string }
// One element picked in the page. `ref` names it for later messages (selection, step, track), so the frame
// can find the same element again while it lives; `selector` is the fallback once it is gone.
// `kind` is how: a click (`keyboard` when Enter on a focused element made it), a dragged box, or a step to
// the parent or child of the selection. `x, y` is where the box points.
export type Pick = {
	kind: 'click' | 'box' | 'step'
	ref: string
	el: ElInfo
	label: string
	component: ComponentInfo
	rect: Rect
	x: number
	y: number
	shift: boolean
	keyboard: boolean
	picks: DemoPick[]
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
// `rect` may be null (a set that draws nothing), which `all` would read as unreadable: it is read on its own.
const modelSet = (v: unknown): ModelSet | null => {
	if (!isObj(v)) return null
	const base = all<Omit<ModelSet, 'rect'>>({
		id: str(v.id),
		key: str(v.key),
		name: str(v.name),
		label: str(v.label),
		file: str(v.file, CAPS.route),
		path: str(v.path, CAPS.route),
		value: str(v.value),
		view: str(v.view, CAPS.route),
		options: list(v.options, CAPS.options, modelOption),
	})
	return base && { ...base, rect: v.rect == null ? null : rect(v.rect) }
}
const stateGroup = (v: unknown) => (isObj(v) ? all<{ title: string; options: string[] }>({ title: str(v.title), options: strings(v.options, CAPS.options) }) : null)
const modelState = (v: unknown): ModelState | null => {
	if (!isObj(v)) return null
	const base = all<Omit<ModelState, 'groups'>>({ id: str(v.id), label: str(v.label), path: str(v.path, CAPS.route), value: str(v.value), options: strings(v.options, CAPS.options) })
	return base && some<ModelState>({ ...base, groups: v.groups === undefined ? null : list(v.groups, CAPS.options, stateGroup) })
}
const canvasTile = (v: unknown): CanvasTile | null =>
	isObj(v)
		? all<CanvasTile>({
				id: str(v.id),
				route: str(v.route, CAPS.route),
				rect: rect(v.rect),
				tile: tileRef(v.tile),
				label: str(v.label),
				isDefault: bool(v.isDefault ?? false),
				author: str(v.author ?? ''),
				setName: str(v.setName ?? ''),
				setFile: str(v.setFile ?? '', CAPS.route),
				setCount: num(v.setCount ?? 0),
			})
		: null
const keyed = (v: unknown) => (isObj(v) ? all<{ key: string; options: string[] }>({ key: str(v.key), options: strings(v.options, CAPS.options) }) : null)
const canvasPage = (v: unknown): CanvasPage | null =>
	isObj(v)
		? all<CanvasPage>({
				path: str(v.path, CAPS.route),
				title: str(v.title),
				sets: list(v.sets, CAPS.sets, keyed),
				states: list(v.states, CAPS.sets, keyed),
				ofs: strings(v.ofs ?? [], CAPS.tiles),
			})
		: null
const pickItem = (v: unknown): PickItem | null =>
	isObj(v)
		? all<PickItem>({
				value: str(v.value, CAPS.route),
				label: str(v.label),
				sub: str(v.sub ?? ''),
				short: str(v.short, 40),
				group: oneOf(v.group, ['sets', 'pages'] as const),
				options: strings(v.options ?? [], CAPS.options),
			})
		: null
// A list that may be left out: absent stays absent, present must read.
const maybe = <T>(v: unknown, read: (v: unknown) => T | null): T | null | undefined => (v === undefined ? undefined : read(v))
const page = (v: unknown): Page | null => (isObj(v) ? all<Page>({ path: str(v.path, CAPS.route), title: str(v.title) }) : null)
const componentInfo = (v: unknown): ComponentInfo | null =>
	isObj(v) ? all<ComponentInfo>({ component: str(v.component), chain: strings(v.chain, 10), file: str(v.file ?? '', CAPS.route) }) : null

// ---- Tweak ---------------------------------------------------------------------------------
const point2 = (v: unknown, a: string, b: string) => {
	if (!isObj(v)) return null
	const [x, y] = [num(v[a]), num(v[b])]
	return x === null || y === null ? null : ({ [a]: x, [b]: y } as { fx: number; fy: number })
}
const classList = (v: unknown) => strings(v, CAPS.classes, 200)
// A prop value: the enum string a frappe-ui prop takes, or a number or boolean. Anything else is left out.
const propValue = (v: unknown): PropValue | null => (typeof v === 'string' ? v.slice(0, CAPS.label) : typeof v === 'number' ? num(v) : typeof v === 'boolean' ? v : null)
const props = (v: unknown) => record(v ?? {}, 20, propValue)
const tweakCopy = (v: unknown): TweakCopy | null =>
	isObj(v)
		? all<TweakCopy>({
				i: typeof v.i === 'number' && Number.isInteger(v.i) && v.i >= 0 && v.i < 1000 ? v.i : null,
				from: str(v.from, CAPS.text),
				to: str(v.to, CAPS.text),
				files: strings(v.files ?? [], 3, CAPS.route),
				stem: bool(v.stem ?? false),
			})
		: null
const tweakWhere = (v: unknown): TweakWhere | null =>
	isObj(v)
		? all<TweakWhere>({
				selector: str(v.selector, CAPS.selector),
				component: str(v.component ?? ''),
				file: str(v.file ?? '', CAPS.route),
				path: strings(v.path ?? [], 10),
				element: str(v.element ?? ''),
				text: str(v.text ?? '', CAPS.text),
				label: str(v.label ?? ''),
				items: num(v.items ?? 0),
				opener: str(v.opener ?? '', CAPS.selector),
				viewport: str(v.viewport ?? '', 40),
			})
		: null
const tweakFacts = (v: unknown): TweakFacts | null =>
	isObj(v)
		? all<TweakFacts>({
				ref: str(v.ref, 40),
				tweak: str(v.tweak ?? '', 40),
				name: str(v.name ?? ''),
				kind: str(v.kind ?? ''),
				classes: classList(v.classes),
				known: strings(v.known ?? [], 20, 40),
				props: props(v.props),
				cs: record(v.cs ?? {}, 30, (x) => str(x, 60)),
				notes: record(v.notes ?? {}, 20, (x) => str(x)),
				hasText: bool(v.hasText ?? false),
				bordered: bool(v.bordered ?? false),
				rolled: str(v.rolled ?? '', 40),
				stack: bool(v.stack ?? false),
				copies: list(v.copies ?? [], 6, tweakCopy),
				where: tweakWhere(v.where),
			})
		: null

export const fromFrame: { [K in keyof FromFrame]: (d: Obj) => FromFrame[K] | null } = {
	ready: (d) => all({ status: str(d.status, 40), routes: strings(d.routes, CAPS.list, CAPS.route), pages: list(d.pages ?? [], CAPS.list, page) }),
	route: (d) => all({ fullPath: str(d.fullPath, CAPS.route), path: str(d.path, CAPS.route), key: str(d.key, CAPS.route) }),
	theme: (d) => all({ theme: oneOf(d.theme, THEMES) }),
	'theme:choose': (d) => all({ theme: oneOf(d.theme, [...THEMES, 'system'] as const) }),
	layout: (d) =>
		all({
			vw: num(d.vw),
			vh: num(d.vh),
			navBottom: num(d.navBottom),
			pageLayerOpen: bool(d.pageLayerOpen),
			dialogOpen: bool(d.dialogOpen ?? false),
			// Only a tint: one that does not read is no tint, and the rest of the layout still holds.
			backdrop: color(d.backdrop ?? '') ?? '',
			layers: list(d.layers ?? [], CAPS.list, rect) ?? [],
		}),
	model: (d) => all({ sets: list(d.sets, CAPS.sets, modelSet), states: list(d.states, CAPS.sets, modelState), canOpen: bool(d.canOpen ?? false) }),
	hover: (d) => {
		const keys = all({ alt: bool(d.alt ?? false), shift: bool(d.shift ?? false) })
		if (!keys) return null
		if (d.rect === null) return { rect: null, label: '', lines: [], ...keys }
		const r = all({ rect: rect(d.rect), label: str(d.label), lines: list(d.lines ?? [], CAPS.list, redline) })
		return r && { ...r, ...keys }
	},
	pick: (d) => {
		const base = all({
			kind: oneOf(d.kind, ['click', 'box', 'step'] as const),
			ref: str(d.ref, 40),
			el: elInfo(d.el),
			label: str(d.label),
			component: componentInfo(d.component),
			rect: rect(d.rect),
			x: num(d.x),
			y: num(d.y),
			shift: bool(d.shift ?? false),
			keyboard: bool(d.keyboard ?? false),
			picks: list(d.picks ?? [], CAPS.sets, demoPick),
		})
		return base && some<Pick>({ ...base, box: d.box === undefined ? null : box(d.box) })
	},
	drag: (d) => ({ rect: d.rect === null ? null : rect(d.rect) }),
	demo: (d) => all({ entries: list(d.entries, CAPS.sets, demoEntry) }),
	rects: (d) => all({ req: str(d.req, 40), map: rectMap(d.map) }),
	track: (d) => all({ map: rectMap(d.map), labels: record(d.labels ?? {}, CAPS.rects, (x) => str(x)) }),
	canvas: (d) => {
		const base = all({
			open: bool(d.open),
			phone: bool(d.phone),
			view: str(d.view, CAPS.route),
			// A zoom of zero or less cannot be drawn (the pins divide by it).
			zoom: typeof d.zoom === 'number' && d.zoom > 0 ? num(Math.max(d.zoom, 0.01)) : null,
			pan: point(d.pan),
			corner: num(d.corner ?? 0),
		})
		if (!base) return null
		// Unreadable, it is no empty view: the canvas still draws.
		const empty = d.empty == null ? null : emptyView(d.empty)
		const parts = {
			tiles: maybe(d.tiles, (v) => list(v, CAPS.tiles, canvasTile)),
			pages: maybe(d.pages, (v) => list(v, CAPS.list, canvasPage)),
			items: maybe(d.items, (v) => list(v, CAPS.tiles, pickItem)),
		}
		if (Object.values(parts).some((x) => x === null)) return null
		return { ...some<typeof base & typeof parts>({ ...base, ...parts }), empty }
	},
	'tile:menu': (d) => all({ tileId: str(d.tileId), rect: rect(d.rect) }),
	'canvas:show': (d) => all({ rect: rect(d.rect), open: bool(d.open) }),
	'tile:pick': (d) => all({ spot: tileSpot(d.spot), fx: num(d.fx), fy: num(d.fy), x: num(d.x), y: num(d.y) }),
	'canvas:click': () => ({}),
	'canvas:revealed': (d) => {
		const req = str(d.req, 40)
		if (req === null) return null
		if (d.point === null) return { req, point: null }
		const p = point(d.point)
		return p && { req, point: p }
	},
	// Escape and the tool shortcuts only: the frame has the focus while a person works in the page.
	key: (d) =>
		all({
			key: oneOf(d.key, ['Escape', 'n', 't', 'c', 'N', 'T', 'C']),
			mods: list(d.mods, 4, (m) => oneOf(m, ['shift', 'alt', 'ctrl', 'meta'] as const)),
			layer: oneOf(d.layer ?? '', ['', 'dialog', 'layer'] as const),
		}),
	'tweak:info': (d) => {
		const req = str(d.req ?? '', 40)
		if (req === null) return null
		const out: TweakInfo = { req }
		if (d.sels !== undefined) {
			const sels = list(d.sels, CAPS.alike, tweakFacts)
			if (!sels) return null
			out.sels = sels
		}
		for (const k of ['total', 'joinable'] as const) if (d[k] !== undefined) out[k] = num(d[k]) ?? 0
		if (d.anchor !== undefined) out.anchor = d.anchor === null ? null : point2(d.anchor, 'fx', 'fy')
		if (d.tokens !== undefined) out.tokens = record(d.tokens, 20, (x) => strings(x, CAPS.tokens, 60)) ?? undefined
		if (d.stacks !== undefined) out.stacks = record(d.stacks, CAPS.tweaks, num) ?? undefined
		if (d.say !== undefined) out.say = (isObj(d.say) && all({ text: str(d.say.text), x: num(d.say.x), y: num(d.say.y) })) || undefined
		if (d.found !== undefined) out.found = bool(d.found) ?? false
		if (d.outside !== undefined) out.outside = bool(d.outside) ?? false
		return out
	},
	// `sel` and `hover` may be null (nothing picked, nothing under the pointer), which `all` would read as unreadable.
	'tweak:rects': (d) => {
		const sel = d.sel == null ? null : rect(d.sel)
		const hover = d.hover == null ? null : rect(d.hover)
		if ((d.sel != null && !sel) || (d.hover != null && !hover)) return null
		const rest = all({
			others: list(d.others ?? [], CAPS.alike, rect),
			faint: list(d.faint ?? [], CAPS.alike, rect),
			hoverName: str(d.hoverName ?? ''),
			hl: list(d.hl ?? [], CAPS.alike, rect),
			peek: bool(d.peek ?? false),
		})
		return rest && { sel, hover, ...rest }
	},
}

// ---- Shell -> frame -----------------------------------------------------------------------
// A pick to put the Demo back on: which set or state, and the option.
export type PickRef = { kind: 'set' | 'state'; path: string; key: string; option: string }
const pickRef = (v: unknown): PickRef | null =>
	isObj(v) ? all<PickRef>({ kind: oneOf(v.kind, ['set', 'state'] as const), path: str(v.path, CAPS.route), key: str(v.key), option: str(v.option) }) : null

export type ToFrame = {
	// `active` is the tool picking in the page now: the frame catches the pointer only then.
	tool: { mode: Mode; active: boolean }
	// The elements of the open box (by the refs their picks carried), and its dragged box, for Alt's distances. `drop`:
	// the box has just closed, and the hover outline waits for the pointer to move.
	selection: { refs: string[]; box?: BoxInfo; drop?: boolean }
	// Parent or child of the box's first element (the \ and Enter keys). The frame answers with a `step` pick.
	step: { dir: 'parent' | 'child'; ref: string }
	resolve: { req: string; selectors: string[] }
	// What the shell draws on page elements (pins, outlines): id -> selector, and id -> ref for an element picked
	// this visit, tried first. The frame answers with `track` now and whenever they move.
	track: { map: Record<string, string>; refs: Record<string, string> }
	nav: { path: string }
	'state:set': { id: string; value: string }
	'picks:apply': { picks: PickRef[] }
	// Open the canvas on a view, or show another view in it when it is open.
	'canvas:open': { view?: string }
	'canvas:close': Obj
	// Bring a tile into view, `fx, fy` being the spot on it as a fraction. The frame answers with `canvas:revealed`.
	'canvas:reveal': { req: string; spot: TileSpot; fx: number; fy: number }
	// The tool picking tiles, '' while browsing: a click on a tile is then a `tile:pick`, not opening it live.
	'canvas:tool': { tool: '' | 'comment' | 'note' }
	// Where the shell's chrome sits, for the page's own chrome to keep clear of it. Any field may be left out.
	// `busyTile` is the tile whose action the shell is saving and `menuTile` the one whose menu is open ('' for none);
	// `landed` the option a write has just put in place, which the canvas rings once it is drawn; `showOpen` whether the
	// phone's Show list is open.
	display: {
		newOptions?: string[]
		reserve?: number
		corner?: string
		busyTile?: string
		menuTile?: string
		landed?: { set: string; option: string }
		showOpen?: boolean
	}
	// Sort and measure the Demo's rows again (the card opened, a row is hovered): the frame answers with `model`.
	'model:measure': Obj
	// The tile menu's Open page, and States (the option's component states).
	'tile:open': { tileId: string }
	'tile:states': { tileId: string }
	// The two facts the frame's status screen (empty, did not build) words itself by. Sent only with that screen up.
	copy: { owner: boolean; reloads: boolean }
	scrollTo: { selector: string; smooth: boolean }
	// Escape pressed in the shell while a page menu, popover or list is open: the page's own layer takes it.
	escape: Obj
	// A press on the Demo pill: the page's open menus, popovers and dialog close as on a press outside them.
	outside: Obj
	// Tweak's selection, which the frame holds (the page's elements are there): clear it, take every alike copy in, step
	// to the parent or child, find a list row's tweaks (`ids`; the answer says `found`) and then select them, outline a
	// hovered row's elements, or ask for the facts again. `keys` is Shift and Space as the shell hears them.
	'tweak:inspect': { req: string; op: TweakOp; ids?: string[]; shift?: boolean; peek?: boolean }
	// A class list per element, by its ref: tried on while a dropdown hovers a row, kept, or put back.
	'tweak:preview': { req: string; edits: ClassEdit[] }
	'tweak:commit': { req: string; edits: ClassEdit[] }
	'tweak:cancel': { req: string; edits: ClassEdit[] }
	// A frappe-ui prop per element: tried on, kept, or put back. A null value is no value.
	'tweak:props': { req: string; key: string; phase: 'preview' | 'commit' | 'cancel'; edits: PropEdit[] }
	// One of an element's hard-coded texts, written in place.
	'tweak:copy': { req: string; ref: string; i: number; to: string; stem: boolean }
	// The tweaks the person keeps (their own design data: classes, props and copy edits), for the frame to keep applied,
	// and the elements each new one was made on (`bind`: tweak id -> ref).
	'tweak:reapply': { tweaks: TweakSync[]; bind: Record<string, string> }
}
export const TWEAK_OPS = ['clear', 'all', 'parent', 'child', 'find', 'select', 'highlight', 'refresh', 'keys'] as const
export type TweakOp = (typeof TWEAK_OPS)[number]
export type ClassEdit = { ref: string; classes: string[] }
export type PropEdit = { ref: string; value: PropValue | null }
// What the frame needs of a tweak to keep it on the page: never who made it, never a note.
export type TweakSync = {
	id: string
	route: string
	selector: string
	// What opens the floating layer the element lives in, for a list row to open it again.
	opener: string
	original: { classes: string[]; props: Record<string, PropValue> }
	classes: string[]
	props: Record<string, PropValue>
	copies: { i: number; from: string; to: string; stem: boolean }[]
}
const classEdit = (v: unknown): ClassEdit | null => (isObj(v) ? all<ClassEdit>({ ref: str(v.ref, 40), classes: classList(v.classes) }) : null)
const propEdit = (v: unknown): PropEdit | null => {
	if (!isObj(v)) return null
	const ref = str(v.ref, 40)
	if (ref === null) return null
	return { ref, value: v.value === null || v.value === undefined ? null : propValue(v.value) }
}
const tweakSync = (v: unknown): TweakSync | null => {
	if (!isObj(v) || !isObj(v.original)) return null
	const original = all<TweakSync['original']>({ classes: classList(v.original.classes), props: props(v.original.props) })
	return all<TweakSync>({
		id: str(v.id, 40),
		route: str(v.route, CAPS.route),
		selector: str(v.selector, CAPS.selector),
		opener: str(v.opener ?? '', CAPS.selector),
		original,
		classes: classList(v.classes),
		props: props(v.props),
		copies: list(v.copies ?? [], 6, (c) => {
			const r = tweakCopy(c)
			return r && { i: r.i, from: r.from, to: r.to, stem: r.stem }
		}),
	})
}

// The frame checks `e.source === parent` and these, so a message from anywhere else does nothing.
export const toFrame: { [K in keyof ToFrame]: (d: Obj) => ToFrame[K] | null } = {
	tool: (d) => all({ mode: oneOf(d.mode, MODES), active: bool(d.active) }),
	selection: (d) => {
		const refs = strings(d.refs, CAPS.rects, 40)
		return refs && some({ refs, box: d.box === undefined ? null : box(d.box), drop: d.drop === undefined ? null : bool(d.drop) })
	},
	step: (d) => all({ dir: oneOf(d.dir, ['parent', 'child'] as const), ref: str(d.ref, 40) }),
	resolve: (d) => all({ req: str(d.req, 40), selectors: strings(d.selectors, CAPS.rects, CAPS.selector) }),
	track: (d) => {
		const map = record(d.map, CAPS.rects, (x) => str(x, CAPS.selector))
		const refs = record(d.refs ?? {}, CAPS.rects, (x) => str(x, 40))
		return map && refs && { map, refs }
	},
	nav: (d) => all({ path: str(d.path, CAPS.route) }),
	'state:set': (d) => all({ id: str(d.id), value: str(d.value) }),
	'picks:apply': (d) => all({ picks: list(d.picks, CAPS.sets, pickRef) }),
	'canvas:open': (d) => some({ view: str(d.view, CAPS.route) }),
	'canvas:close': () => ({}),
	'canvas:reveal': (d) => all({ req: str(d.req, 40), spot: tileSpot(d.spot), fx: num(d.fx), fy: num(d.fy) }),
	'canvas:tool': (d) => all({ tool: oneOf(d.tool, ['', 'comment', 'note'] as const) }),
	display: (d) =>
		some({
			newOptions: strings(d.newOptions, CAPS.options),
			reserve: num(d.reserve),
			corner: str(d.corner, 40),
			busyTile: str(d.busyTile),
			menuTile: str(d.menuTile),
			landed: isObj(d.landed) ? all({ set: str(d.landed.set), option: str(d.landed.option) }) : null,
			showOpen: d.showOpen === undefined ? null : bool(d.showOpen),
		}),
	'model:measure': () => ({}),
	'tile:open': (d) => all({ tileId: str(d.tileId) }),
	'tile:states': (d) => all({ tileId: str(d.tileId) }),
	copy: (d) => all({ owner: bool(d.owner), reloads: bool(d.reloads) }),
	scrollTo: (d) => all({ selector: str(d.selector, CAPS.selector), smooth: bool(d.smooth ?? false) }),
	escape: () => ({}),
	outside: () => ({}),
	'tweak:inspect': (d) => {
		const base = all({ req: str(d.req, 40), op: oneOf(d.op, TWEAK_OPS) })
		return base && some({ ...base, ids: d.ids === undefined ? null : strings(d.ids, CAPS.alike, 40), shift: d.shift === undefined ? null : bool(d.shift), peek: d.peek === undefined ? null : bool(d.peek) })
	},
	'tweak:preview': (d) => all({ req: str(d.req, 40), edits: list(d.edits, CAPS.alike, classEdit) }),
	'tweak:commit': (d) => all({ req: str(d.req, 40), edits: list(d.edits, CAPS.alike, classEdit) }),
	'tweak:cancel': (d) => all({ req: str(d.req, 40), edits: list(d.edits, CAPS.alike, classEdit) }),
	'tweak:props': (d) =>
		all({
			req: str(d.req, 40),
			key: str(d.key, 40),
			phase: oneOf(d.phase, ['preview', 'commit', 'cancel'] as const),
			edits: list(d.edits, CAPS.alike, propEdit),
		}),
	'tweak:copy': (d) =>
		all({
			req: str(d.req, 40),
			ref: str(d.ref, 40),
			i: typeof d.i === 'number' && Number.isInteger(d.i) && d.i >= 0 && d.i < 1000 ? d.i : null,
			to: str(d.to, CAPS.text),
			stem: bool(d.stem ?? false),
		}),
	'tweak:reapply': (d) => all({ tweaks: list(d.tweaks, CAPS.tweaks, tweakSync), bind: record(d.bind ?? {}, CAPS.alike, (x) => str(x, 40)) }),
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
