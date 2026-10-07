<script setup lang="ts">
// A token dropdown that previews on hover: the element changes as the pointer or arrow keys move
// over a row, Enter or a click keeps it, Esc or a click elsewhere puts it back.
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { UI_ATTR } from './annotate'

type Swatch = { type: 'ink' | 'bg' | 'border'; cls: string }
type Opt = { value: string | null; label: string; right?: string; swatch?: Swatch }

const props = defineProps<{
	modelValue: string | null
	options: Opt[]
	label: string
	noneRight?: string
	icon?: string
	changed?: boolean
	mixed?: boolean
	// How an empty value reads: the computed px as a token ('space', '16px' -> 4; 'radius').
	emptyAs?: 'space' | 'radius'
}>()
const emit = defineEmits<{
	preview: [value: string | null]
	commit: [value: string | null]
	cancel: []
	reset: []
}>()

const open = ref(false)
const query = ref('')
const active = ref(0)
const trigger = ref<HTMLElement | null>(null)
const pop = ref<HTMLElement | null>(null)
const inp = ref<HTMLInputElement | null>(null)
const popStyle = ref<Record<string, string>>({})
let previewed = false

const current = computed(() => props.options.find((o) => o.value === props.modelValue))
// The trigger shows the token only; the px value lives in the list. A value outside the list
// (an arbitrary class like pl-[2.625rem]) is shown as it is.
const text = computed(() => {
	if (props.mixed) return 'Mixed'
	if (current.value && current.value.value !== null) return current.value.label
	if (props.modelValue == null) return emptyText.value
	return props.modelValue.replace(/^\[|\]$/g, '')
})
// No class set: show what the element has anyway, so the field is never a bare dash.
const RADIUS: Record<string, string> = { '0': '0', '4': '1', '8': '4', '10': '5', '12': '6' }
const emptyText = computed(() => {
	const raw = props.noneRight
	if (!raw) return 'None'
	const n = parseFloat(raw)
	if (!props.emptyAs || !/^-?[\d.]+px$/.test(raw) || Number.isNaN(n)) return raw
	if (props.emptyAs === 'radius') return RADIUS[String(n)] ?? raw
	// Spacing tokens are quarters of a pixel step: only a clean multiple of 2px has one.
	return Number.isInteger(n) && n % 2 === 0 ? String(n / 4) : raw
})
const muted = computed(() => props.mixed || props.modelValue == null)

const filtered = computed(() => {
	const q = query.value.trim().toLowerCase()
	return q ? props.options.filter((o) => o.label.toLowerCase().includes(q)) : props.options
})

function scrollTo(i: number, center = false) {
	const p = pop.value
	const row = p?.querySelector<HTMLElement>(`[data-i="${i}"]`)
	if (!p || !row) return
	if (center) p.scrollTop = row.offsetTop - p.clientHeight / 2 + row.offsetHeight / 2
	else if (row.offsetTop < p.scrollTop + 4) p.scrollTop = row.offsetTop - 4
	else if (row.offsetTop + row.offsetHeight > p.scrollTop + p.clientHeight - 4) p.scrollTop = row.offsetTop + row.offsetHeight - p.clientHeight + 4
}

function previewAt(i: number) {
	const o = filtered.value[i]
	if (!o) return
	active.value = i
	previewed = true
	emit('preview', o.value)
}

// ---- Open and close -------------------------------------------------------------------
function openList() {
	const t = trigger.value
	if (open.value || !t) return
	const r = t.getBoundingClientRect()
	const est = Math.min(256, props.options.length * 28 + 8)
	const below = window.innerHeight - r.bottom - 8
	const up = below < est && r.top > below
	const w = Math.max(r.width, 148)
	const style: Record<string, string> = {
		left: `${Math.min(Math.max(8, r.left), window.innerWidth - w - 8)}px`,
		width: `${w}px`,
		transformOrigin: up ? 'bottom' : 'top',
	}
	if (up) {
		style.bottom = `${window.innerHeight - r.top + 4}px`
		style.maxHeight = `${Math.min(256, r.top - 12)}px`
	} else {
		style.top = `${r.bottom + 4}px`
		style.maxHeight = `${Math.min(256, below)}px`
	}
	popStyle.value = style
	query.value = ''
	active.value = Math.max(0, props.options.findIndex((o) => o.value === props.modelValue))
	previewed = false
	open.value = true
	addListeners()
	nextTick(() => {
		inp.value?.focus({ preventScroll: true })
		scrollTo(active.value, true)
	})
}

// Pass a row to keep it; pass nothing to put the element back.
function close(keep?: number) {
	if (!open.value) return
	const o = keep != null ? filtered.value[keep] : undefined
	open.value = false
	removeListeners()
	if (o) emit('commit', o.value)
	else if (previewed) emit('cancel')
	previewed = false
}

function toggle() {
	if (open.value) close()
	else openList()
}

function onTriggerKey(e: KeyboardEvent) {
	// Enter and Space arrive as a click on the button; only the arrow needs its own handling.
	if (e.key === 'ArrowDown' && !open.value) {
		e.preventDefault()
		openList()
	}
}

function onKey(e: KeyboardEvent) {
	const k = e.key
	const n = filtered.value.length
	if (k === 'ArrowDown' || k === 'ArrowUp') {
		e.preventDefault()
		e.stopPropagation()
		if (!n) return
		const i = (active.value + (k === 'ArrowDown' ? 1 : -1) + n) % n
		previewAt(i)
		scrollTo(i)
	} else if (k === 'Enter') {
		e.preventDefault()
		e.stopPropagation()
		close(n ? active.value : undefined)
		trigger.value?.focus({ preventScroll: true })
	} else if (k === 'Escape') {
		e.preventDefault()
		e.stopPropagation()
		close()
		trigger.value?.focus({ preventScroll: true })
	} else if (k === 'Tab') close()
}

function onInput(e: Event) {
	query.value = (e.target as HTMLInputElement).value
	active.value = 0
	if (filtered.value.length) previewAt(0)
	nextTick(() => scrollTo(0))
}

function onRowMove(i: number, e: PointerEvent) {
	// A list scrolling under a still pointer must not count as hovering.
	if (i === active.value || (e.movementX === 0 && e.movementY === 0)) return
	previewAt(i)
}

function onLeave() {
	active.value = Math.max(0, filtered.value.findIndex((o) => o.value === props.modelValue))
	if (previewed) {
		previewed = false
		emit('cancel')
	}
}

// ---- Listeners live only while the list is open ---------------------------------------
function onOutside(e: Event) {
	const t = e.target as Node
	if (pop.value?.contains(t) || trigger.value?.contains(t)) return
	close()
}
function onScroll(e: Event) {
	if (!pop.value?.contains(e.target as Node)) close()
}
const onResize = () => close()

function addListeners() {
	// On window, so this runs before the picker's own capture listeners on document.
	window.addEventListener('pointerdown', onOutside, true)
	window.addEventListener('scroll', onScroll, true)
	window.addEventListener('resize', onResize)
}
function removeListeners() {
	window.removeEventListener('pointerdown', onOutside, true)
	window.removeEventListener('scroll', onScroll, true)
	window.removeEventListener('resize', onResize)
}
onBeforeUnmount(() => {
	removeListeners()
	if (open.value && previewed) emit('cancel')
})
</script>

<template>
	<div class="group relative min-w-0" data-tweak-select>
		<button
			ref="trigger"
			type="button"
			:aria-label="label"
			:title="label"
			aria-haspopup="listbox"
			:aria-expanded="open"
			class="flex h-7 w-full items-center gap-1.5 rounded-4 bg-surface-gray-2 px-2 text-base text-ink-gray-8 hover:bg-surface-gray-3"
			@click="toggle"
			@keydown="onTriggerKey"
		>
			<span v-if="icon" class="size-3.5 shrink-0 text-ink-gray-5" :class="icon" aria-hidden="true" />
			<template v-if="current?.swatch">
				<span v-if="current.swatch.type === 'ink'" class="w-3.5 shrink-0 text-center text-xs font-semibold leading-none" :class="current.swatch.cls" aria-hidden="true">Aa</span>
				<span v-else-if="current.swatch.type === 'bg'" class="size-3.5 shrink-0 rounded-sm border border-outline-gray-2" :class="current.swatch.cls" aria-hidden="true" />
				<span v-else class="size-3.5 shrink-0 rounded-sm border-2 border-solid" :class="current.swatch.cls" aria-hidden="true" />
			</template>
			<span class="min-w-0 flex-1 truncate text-left" :class="mixed ? 'text-ink-gray-5' : muted && 'text-ink-gray-4'">{{ text }}</span>
		</button>
		<!-- Changed: a violet dot, which turns into a reset button on hover. -->
		<span v-if="changed" class="pointer-events-none absolute right-1 top-1 size-1.5 rounded-full bg-surface-violet-7 group-hover:hidden" aria-hidden="true" />
		<button
			v-if="changed"
			type="button"
			aria-label="Reset"
			title="Reset"
			class="absolute right-0.5 top-1/2 hidden size-6 -translate-y-1/2 items-center justify-center rounded-4 bg-surface-gray-3 text-ink-gray-6 hover:text-ink-gray-9 group-hover:flex"
			@click.stop="emit('reset')"
		>
			<span class="lucide-rotate-ccw size-3" aria-hidden="true" />
		</button>

		<Teleport to="body">
			<Transition
				enter-from-class="opacity-0 scale-[0.97] motion-reduce:scale-100"
				enter-active-class="transition duration-[120ms] ease-out motion-reduce:transition-opacity"
				leave-active-class="transition-opacity duration-75"
				leave-to-class="opacity-0"
			>
				<div
					v-if="open"
					ref="pop"
					:[UI_ATTR]="''"
					data-tweak-select
					class="fixed z-[2147483001] max-h-64 overflow-y-auto rounded-5 border border-outline-gray-2 bg-surface-elevation-2 p-1 shadow-xl"
					:style="popStyle"
					@pointerdown.stop
					@focusin.stop
					@mouseleave="onLeave"
				>
					<!-- Takes the typing (so page shortcuts stay quiet) and the arrow keys. -->
					<input ref="inp" class="absolute size-px opacity-0" aria-label="Filter tokens" autocomplete="off" :value="query" @input="onInput" @keydown="onKey" />
					<p v-if="query" class="px-2 pb-1 text-xs text-ink-gray-5">Filter: {{ query }}</p>
					<div role="listbox" :aria-label="label">
						<div
							v-for="(o, i) in filtered"
							:key="String(o.value)"
							:data-i="i"
							role="option"
							:aria-selected="o.value === modelValue"
							class="flex h-7 cursor-default items-center gap-1.5 rounded-4 px-2 text-base text-ink-gray-8"
							:class="i === active && 'bg-surface-gray-3'"
							@pointermove="onRowMove(i, $event)"
							@click="close(i)"
						>
							<template v-if="o.swatch">
								<span v-if="o.swatch.type === 'ink'" class="w-3.5 shrink-0 text-center text-xs font-semibold leading-none" :class="o.swatch.cls" aria-hidden="true">Aa</span>
								<span v-else-if="o.swatch.type === 'bg'" class="size-3.5 shrink-0 rounded-sm border border-outline-gray-2" :class="o.swatch.cls" aria-hidden="true" />
								<span v-else class="size-3.5 shrink-0 rounded-sm border-2 border-solid" :class="o.swatch.cls" aria-hidden="true" />
							</template>
							<span class="min-w-0 flex-1 truncate" :class="o.value === null && 'text-ink-gray-5'">{{ o.label }}</span>
							<span v-if="o.value === null ? noneRight : o.right" class="shrink-0 text-sm tabular-nums text-ink-gray-5">{{ o.value === null ? noneRight : o.right }}</span>
							<span v-if="o.value === modelValue" class="lucide-check size-3.5 shrink-0 text-ink-gray-6" aria-hidden="true" />
						</div>
						<p v-if="!filtered.length" class="flex h-7 items-center px-2 text-base text-ink-gray-5">No match</p>
					</div>
				</div>
			</Transition>
		</Teleport>
	</div>
</template>
