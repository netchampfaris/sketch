<script setup lang="ts">
// The Demo pill at the bottom right, drawn by the Viewer shell over the frame. It opens a card with the app-wide states (Role), this page's states and this
// page's Variants sets, one row each, as the frame reports them (demo.ts). The owner's rows also carry Make default and
// Keep only this, which the shell saves over the session (actions.ts).
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { createReusableTemplate, onClickOutside, useElementBounding, useElementSize, useEventListener } from '@vueuse/core'
import { Button, Dropdown, toast } from 'frappe-ui'
import type { ModelSet, ModelState, Rect } from '../shared/protocol'
import { badges, freshIn, lookAt, pageHasNew } from './badges'
import { choose, demo, measure } from './demo'
import { onFrame, page, post } from './frame'
import { isOwner, keepFailure, keepOnly, makeDefault, makeFailure, saving } from './actions'
import LensMenu from './LensMenu.vue'
import { canvas, showView } from './canvas'
import { menuBind } from '../shared/menus'

type Row = ModelSet | ModelState

const [DefineRow, RowOf] = createReusableTemplate<{ s: Row; role?: boolean }>({
	inheritAttrs: false,
	props: { s: { type: Object, required: true }, role: Boolean },
})

const isState = (s: Row): s is ModelState => !('key' in s)
const setRows = computed(() => demo.sets)
const appRows = computed(() => demo.states.filter((s) => s.path === ''))
const pageStateRows = computed(() => demo.states.filter((s) => s.path !== ''))
const count = computed(() => appRows.value.length + pageStateRows.value.length + setRows.value.length)

// What is new for this person on this page: options teammates made that nobody here has looked at. Unread threads mark
// the Comment tool instead.
const optionsOf = (s: ModelSet) => s.options.map((o) => o.value)
const freshOf = (s: Row) => (isState(s) ? 0 : freshIn(optionsOf(s)))
const dot = computed(() => pageHasNew(page.path, setRows.value.flatMap(optionsOf)))

const open = ref(false)
const pill = ref<HTMLElement | null>(null)
// The pill sat in the page, so a press on it was a press outside the page's open menu or popover: it closes, as before.
// A menu hands the focus back to its trigger in the page, which is no press outside the card it opens: the card keeps
// it.
let pressedAt = 0
function pressed() {
	pressedAt = performance.now()
	post('outside', {})
}
// A page dialog's backdrop covered the pill: it shows through the same tint, and a press on it is a press on the
// backdrop, which is outside the card too.
const covered = computed(() => !!page.backdrop)
function onBackdrop() {
	close()
	post('outside', {})
}
// The dialog's panel, or a menu over it, hid the pill where it met it: the pill is not drawn then.
const pillBox = useElementBounding(pill)
const meets = (r: Rect) => r.x < pillBox.right.value && r.x + r.w > pillBox.left.value && r.y < pillBox.bottom.value && r.y + r.h > pillBox.top.value
const pillUnder = computed(() => covered.value && pillBox.width.value > 0 && page.layers.some(meets))
const focusCard = () => document.querySelector<HTMLElement>('#sketch-demo-card button')?.focus()
const toggle = () => {
	open.value = !open.value
	if (open.value) {
		// Opening the card is looking at the page's news: the pill's dot clears. The rows keep theirs until opened.
		badges.opened[page.path] = true
		// The rows in page order, as the sets sit now.
		measure()
		// Tab then runs down the rows from the first dropdown.
		nextTick(focusCard)
	}
}
watch(count, (n) => !n && (open.value = false))
watch(() => page.path, () => (open.value = false))
const close = (refocus = false) => {
	if (!open.value) return
	open.value = false
	if (refocus) pill.value?.querySelector('button')?.focus()
}
// An open menu takes the Esc first: one of ours here, or the page's own (the frame says a layer was open).
useEventListener(document, 'keydown', (e: KeyboardEvent) => {
	if (e.key !== 'Escape' || !open.value || document.querySelector('[role="menu"]')) return
	close(true)
})
onBeforeUnmount(onFrame('key', (k) => k.key === 'Escape' && !k.layer && !document.querySelector('[role="menu"]') && close()))

const stack = ref<HTMLElement | null>(null)
// A menu opened from a row is portalled out of the stack; picking from it must not close the card. A press in the page
// (the frame) is outside too.
onClickOutside(stack, (e) => (e.type === 'blur' && performance.now() - pressedAt < 500 ? focusCard() : close()), { ignore: ['[role="menu"]'], detectIframe: true })
const { height } = useElementSize(stack, { width: 0, height: 0 }, { box: 'border-box' })
const { width: pillW } = useElementSize(pill, { width: 0, height: 0 }, { box: 'border-box' })
// On a phone the stack sits above the page's MobileNav bar, when it has one (the frame measures it), so the toolbar's
// trigger and the toasts rise with it. The stack rides the bar's height plus its own 12px, the same as the toolbar.
const lift = computed(() => {
	const bar = page.navBottom
	// The open toolbar on a phone sits at the bottom edge; the pill rides above it (the stack is 0.75rem, 12px, up already).
	const inTheWay = demo.toolbarLift > 0 && demo.toolbarRight + 8 > page.vw - 12 - pillW.value
	return Math.max(bar, inTheWay ? demo.toolbarLift - 12 : 0)
})
// The pill rides with the stack: where a page panel meets it is measured from where it is now.
watch(lift, () => nextTick(pillBox.update), { flush: 'post' })
const shown = computed(() => count.value > 0 && !canvas.open)
watch(
	[height, shown, lift],
	([h, on, bar]) => {
		// Under the canvas the pill is hidden, as the frame's was covered: what floats keeps the room it had.
		if (canvas.open) return
		demo.stackH = on && h ? h + bar : 0
		if (demo.stackH) document.documentElement.style.setProperty('--sketch-variants-h', `${demo.stackH}px`)
		else document.documentElement.style.removeProperty('--sketch-variants-h')
	},
	{ immediate: true },
)

// Hovering a Variants row outlines the set on the page, where the frame last measured it.
const hovered = ref<string | null>(null)
const box = computed(() => (hovered.value ? (demo.sets.find((s) => s.id === hovered.value)?.rect ?? null) : null))
function hover(s: ModelSet | null) {
	hovered.value = s ? s.id : null
	if (s) measure()
}
watch([() => page.path, open], () => hover(null))

const labelOf = (s: ModelSet) => s.options.find((o) => o.value === s.value)?.label ?? ''
const menuOf = (s: ModelSet) =>
	s.options.map((o) => ({
		label: o.label,
		selected: o.value === s.value,
		onClick: () => choose(s.id, o.value),
	}))

// Leaving for the canvas: Esc there, and Back, land on the Demo pill again.
let opener: HTMLElement | null = null
watch(
	() => canvas.open,
	(on) => {
		if (on || !opener) return
		const el = opener
		opener = null
		nextTick(() => el.isConnected && el.focus())
	},
)
function go(view: string) {
	close()
	opener = pill.value?.querySelector('button') ?? null
	showView(view)
}
// The foot of the card: this page's first set, else its states, else the first thing the canvas has.
function openHere() {
	const first = setRows.value.find((s) => s.path !== '')
	go(first ? first.view : pageStateRows.value.length ? `page:${pageStateRows.value[0].path}` : 'auto')
}
const off = (s: ModelSet) => s.value !== s.options[0]?.value
// The owner's rows carry two more actions. The column is only there while a row is off its default; otherwise the
// card is as narrow as a commenter's.
const actionsShown = computed(() => isOwner() && setRows.value.some(off))
const canMakeDefault = (s: ModelSet) => isOwner() && !!s.file && s.options[0]?.value !== undefined
const canKeepOnly = (s: ModelSet) => isOwner() && !!s.file
// Make default: the pick becomes the first slot in the source. The frame reloads once it is saved.
const held = ref(0)
async function makeIt(s: ModelSet, e: MouseEvent) {
	if (!s.value || saving.value) return
	held.value = (e.currentTarget as HTMLElement).offsetWidth
	try {
		await makeDefault({ name: s.name, file: s.file, first: s.options[0] }, s.value, s.id)
	} catch (err) {
		toast.error(makeFailure(err as Error))
	}
}
// Keep only this: the same server action as the canvas tile's menu. The frame reloads, and the toast says "Kept …" with Undo.
async function keepIt(s: ModelSet) {
	if (!s.value || saving.value) return
	hover(null)
	try {
		await keepOnly({ name: s.name, file: s.file }, s.value, s.id)
	} catch (err) {
		toast.error(keepFailure(err as Error))
	}
}
const rowLabel = (s: Row, role: boolean) => (isState(s) && !role ? 'State' : s.label)

</script>

<template>
	<DefineRow v-slot="{ s, role }">
		<!-- Each row is a subgrid of the card, so labels and controls line up across rows. -->
		<div
			class="col-span-full grid grid-cols-subgrid items-center py-0.5"
			@mouseenter="hover(isState(s) ? null : (s as ModelSet))"
			@mouseleave="hover(null)"
		>
			<span class="flex min-w-0 items-center pl-2 text-p-sm text-ink-gray-5 max-md:max-w-[7rem]">
				<span class="whitespace-nowrap max-md:whitespace-normal">{{ rowLabel(s, role) }}</span>
				<span
					v-if="freshOf(s)"
					class="ml-1.5 size-1.5 shrink-0 rounded-full bg-surface-blue-6"
					role="img"
					:title="`${freshOf(s)} new since you last looked`"
					:aria-label="`${freshOf(s)} new since you last looked`"
				/>
			</span>
			<div v-if="isState(s)" class="justify-self-start"><LensMenu :state="s" :show-name="false" /></div>
			<div v-else class="min-w-0 justify-self-start">
				<Dropdown v-bind="menuBind(`pill:${s.label}`, () => lookAt((s as ModelSet).key))" :options="menuOf(s as ModelSet)">
					<Button variant="ghost" :aria-label="`${s.label}: ${labelOf(s as ModelSet)}`">
						<span class="flex items-center gap-1.5">
							<span class="max-w-[16rem] truncate text-p-sm text-ink-gray-8 max-md:max-w-[9rem]" :title="labelOf(s as ModelSet)">{{ labelOf(s as ModelSet) }}</span>
							<span class="lucide-chevron-down size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
						</span>
					</Button>
					<template #item-prefix="{ item }">
						<span class="size-4 shrink-0" :class="item.selected ? 'lucide-check' : ''" aria-hidden="true" />
					</template>
					<template #item-label="{ item }">
						<span class="flex min-w-0 max-w-[20rem] items-center gap-2">
							<span class="truncate" :title="item.label">{{ item.label }}</span>
						</span>
					</template>
				</Dropdown>
			</div>
			<template v-if="actionsShown">
				<!-- On a phone the actions sit on their own line under the dropdown, and only a row that has something to do shows one. -->
				<span
					v-if="!isState(s)"
					class="flex shrink-0 items-center justify-end gap-1 max-md:col-span-2 max-md:col-start-2 max-md:row-start-2 max-md:justify-start"
					:class="!off(s as ModelSet) ? 'max-md:hidden' : ''"
				>
					<Button
						v-if="canMakeDefault(s as ModelSet)"
						:class="off(s as ModelSet) ? '' : 'invisible max-md:hidden'"
						variant="ghost"
						:loading="saving === s.id"
						:disabled="!!saving"
						:style="saving === s.id && held ? { width: `${held}px` } : undefined"
						:tabindex="off(s as ModelSet) ? undefined : -1"
						:aria-label="`Make ${labelOf(s as ModelSet)} the default for ${s.label}`"
						@click="makeIt(s as ModelSet, $event)"
					><span class="text-p-sm" :class="saving === s.id ? 'sr-only' : ''">Make default</span></Button>
					<Button
						v-if="canKeepOnly(s as ModelSet)"
						:class="off(s as ModelSet) || hovered === s.id ? '' : 'invisible max-md:hidden'"
						variant="ghost"
						:loading="saving === s.id"
						:disabled="!!saving"
						:tabindex="off(s as ModelSet) || hovered === s.id ? undefined : -1"
						:aria-label="`Keep only ${labelOf(s as ModelSet)} for ${s.label}`"
						@click="keepIt(s as ModelSet)"
					><span class="text-p-sm" :class="saving === s.id ? 'sr-only' : ''">Keep only this</span></Button>
				</span>
				<span v-else class="max-md:hidden" />
			</template>
		</div>
	</DefineRow>

	<div
		v-if="shown"
		ref="stack"
		data-sketch-ui="variants"
		class="pointer-events-none fixed inset-x-3 z-50 flex flex-col items-end gap-2"
		:style="{ bottom: `calc(0.75rem + ${lift}px)` }"
	>
		<div
			v-if="open"
			id="sketch-demo-card"
			class="pointer-events-auto max-h-[60vh] w-max max-w-full overflow-y-auto rounded-[16px] bg-surface-elevation-2 p-2 shadow-lg ring-1 ring-outline-gray-2"
		>
			<div
				class="grid grid-cols-[auto_minmax(0,max-content)] items-center gap-x-2"
				:class="actionsShown ? 'md:grid-cols-[auto_minmax(0,max-content)_auto]' : ''"
			>
				<RowOf v-for="s in appRows" :key="s.id" :s="s" role />
				<RowOf v-for="s in pageStateRows" :key="s.id" :s="s" />
				<RowOf v-for="s in setRows" :key="s.id" :s="s" />
			</div>
			<Button v-if="demo.canOpen" class="mt-0.5 w-full !justify-start" variant="ghost" icon-left="lucide-layout-grid" label="Open canvas" @click="openHere" />
		</div>
		<div ref="pill" data-pill="demo" :class="pillUnder ? 'invisible' : ''" class="pointer-events-auto relative rounded-5 bg-surface-elevation-2 p-1 shadow-lg ring-1 ring-outline-gray-2">
			<Button variant="ghost" aria-controls="sketch-demo-card" :aria-expanded="open" :class="open ? '!bg-surface-gray-3' : ''" :inert="covered" @pointerdown="pressed" @click="toggle">
				<span class="flex items-center gap-1.5">
					<span class="text-p-sm text-ink-gray-8">Demo</span>
					<span v-if="dot && !open" class="size-1.5 shrink-0 rounded-full bg-surface-blue-6" role="img" aria-label="New on this page" />
					<span class="size-3.5 text-ink-gray-5" :class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'" aria-hidden="true" />
				</span>
			</Button>
			<!-- The backdrop's tint over the pill and its ring (the ring is a 1px shadow, so is this). -->
			<div
				v-if="covered"
				class="absolute inset-0 rounded-[inherit]"
				:style="{ backgroundColor: page.backdrop, boxShadow: `0 0 0 1px ${page.backdrop}` }"
				aria-hidden="true"
				@pointerdown="onBackdrop"
			/>
		</div>
	</div>

	<!-- The outline over the hovered set's rect. -->
	<div
		v-if="box && hovered && shown"
		data-sketch-ui="variants"
		class="pointer-events-none fixed z-50 rounded-4 border-2 border-outline-blue-6"
		:style="{ left: `${box.x - 4}px`, top: `${box.y - 4}px`, width: `${box.w + 8}px`, height: `${box.h + 8}px` }"
		aria-hidden="true"
	/>
</template>
