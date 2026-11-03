<script setup lang="ts">
// The Viewer shell: Sketch's own page at /u/<username>/<slug> (sketch/viewer.py SHELL_FLAG). The Prototype
// runs in a full-viewport sandboxed iframe of the same URL with ?frame=1, in an opaque origin, holding no
// credential. Everything that acts as the reader, or shows a person's data, is drawn here, on Sketch's
// origin, over the frame (plan steps 3 to 6 move it in). The shell never scrolls; the frame's rects are
// the shell's coordinates.
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { FrappeUIProvider } from 'frappe-ui'
import { fromFrame, read, type FromFrame, type Theme } from '../shared/protocol'
import { host, type Role } from '../annotate/host'
import { transport } from '../annotate/comments'
import type { ShellBoot } from './boot'
import { applyTheme, resolveTheme, watchTheme } from './theme'
import { startLiveReload } from './liveReload'
import { call, initApi } from './api'
import { initBadges } from './badges'
import { frameGone, page, post, receive, setFrameWindow } from './frame'
import { restoreNotes, startSaving } from './notes'
import Toolbar from './Toolbar.vue'

const props = defineProps<{ boot: ShellBoot }>()

// The statuses that paint boot.js's status screen instead of the Prototype.
const STATUS_SCREENS = ['empty', 'compile-failed', 'link-failed', 'boot-failed']

const frame = shallowRef<HTMLIFrameElement | null>(null)
const theme = ref<Theme>(resolveTheme(props.boot.theme))
applyTheme(theme.value)

// What the frame last said about itself lives in frame.ts `page`: the chrome lays itself out from it.
watch(frame, (el) => setFrameWindow(el?.contentWindow ?? null), { flush: 'sync' })

// ---- Who is reading, for the toolbar -------------------------------------------------------
// Note is the owner's, and an invited editor's own; Comment is anyone signed in who can open the page
// (`me`); a signed-out visitor to a public Prototype gets "Sign in to comment". Nobody else gets a toolbar.
const boot = props.boot
const noter = boot.role === 'owner' || (boot.role === 'editor' && !!boot.me)
const role: Role = noter ? (boot.role as Role) : boot.me ? 'reader' : 'guest'
const toolbar = noter || !!boot.me || boot.sign_in
if (toolbar) {
	initApi(boot.name, boot.csrf_token)
	Object.assign(host, { name: boot.name, title: (boot.title ?? '').trim(), role, me: boot.me?.username ?? '', openCount: Number(boot.comments_open) || 0 })
	// Every comment call goes over the session (sketch.viewer_api), never with anything the frame holds.
	transport.call = (method, fields) => call(method, fields)
	initBadges(boot.badges, !!boot.me)
	if (noter) {
		restoreNotes(boot.annotations, boot.annotations_epoch)
		startSaving()
	}
}
// The toolbar comes once the Prototype has drawn, as it did in the frame, and stays through a live reload.
const shown = ref(false)
watch(
	() => page.ready && !STATUS_SCREENS.includes(page.status),
	(ok) => {
		if (!ok) return
		shown.value = toolbar
		// The page names, for the comments list's groups (annotate/host.ts pageNameOf). Nothing renders from it.
		host.router = createRouter({
			history: createMemoryHistory(),
			routes: page.pages.map((p) => ({ path: p.path, component: { render: () => null }, meta: { title: p.title } })),
		})
	},
)

// The iframe is recreated (a new key) to reload it, so a reload is a fresh load even when the URL is the same.
const generation = ref(0)
const src = ref(frameUrl())

// The iframe boots on the shell's own hash, so a deep link and ?canvas= land where they point.
function frameUrl() {
	const url = new URL(props.boot.frame_src, location.origin)
	url.searchParams.set('theme', theme.value)
	return url.pathname + url.search + location.hash
}

function reloadFrame() {
	frameGone()
	src.value = frameUrl()
	generation.value++
}

// ---- Frame -> shell -------------------------------------------------------------------------
const handlers: { [K in keyof FromFrame]?: (d: FromFrame[K]) => void } = {
	ready: ({ status }) => {
		if (STATUS_SCREENS.includes(status)) {
			const owner = props.boot.role === 'owner'
			post('copy', { owner, reloads: owner && !!props.boot.rev })
		}
	},
	route: ({ fullPath }) => {
		if (!fullPath.startsWith('/')) return
		const hash = `#${fullPath}`
		// replaceState fires no hashchange, so this never echoes back to the frame as a nav.
		if (location.hash !== hash) history.replaceState(history.state, '', location.pathname + location.search + hash)
	},
	theme: ({ theme: next }) => {
		theme.value = next
		applyTheme(next)
	},
	// layout, demo, canvas, hover, pick, drag, rects, track and key go to frame.ts (`receive`), for the toolbar.
	// model, tile:menu, tile:pick and tweak:info are read by the validators already and handled from plan steps 4 to 6.
}

function onMessage(e: MessageEvent) {
	// Only our own iframe, and only while it is in its opaque origin. Anything else is not the Prototype.
	if (!frame.value || e.source !== frame.value.contentWindow || e.origin !== 'null') return
	const msg = read<FromFrame>(e.data, fromFrame)
	if (!msg) return
	receive(msg.type, msg.data as never)
	;(handlers[msg.type] as ((d: unknown) => void) | undefined)?.(msg.data)
}

// ---- Shell -> frame -------------------------------------------------------------------------
// A hash typed into the address bar moves the page in the frame.
function onHashChange() {
	const path = location.hash.replace(/^#/, '') || '/'
	post('nav', { path })
}

// The system preference or a saved choice moved, and nothing fixes the theme in the URL.
function onThemeSource() {
	if (new URLSearchParams(location.search).get('theme')) return
	const next = resolveTheme(null)
	if (next === theme.value) return
	theme.value = next
	applyTheme(next)
	post('theme', { theme: next })
}

let stopTheme = () => {}
let stopReload = () => {}
onMounted(() => {
	window.addEventListener('message', onMessage)
	window.addEventListener('hashchange', onHashChange)
	stopTheme = watchTheme(onThemeSource)
	// Only the owner has an agent writing to the tree, and only the owner's page carries a baseline.
	if (props.boot.role === 'owner' && props.boot.rev) stopReload = startLiveReload(props.boot.slug, props.boot.rev, reloadFrame)
})
onBeforeUnmount(() => {
	window.removeEventListener('message', onMessage)
	window.removeEventListener('hashchange', onHashChange)
	stopTheme()
	stopReload()
})
</script>

<template>
	<FrappeUIProvider>
		<!-- allow-same-origin must never join these: it hands the frame Sketch's origin and the session. -->
		<iframe
			:key="generation"
			ref="frame"
			:src="src"
			:title="boot.title"
			sandbox="allow-scripts allow-forms allow-popups"
			allow="clipboard-write"
			class="fixed inset-0 block w-full border-0"
			style="height: 100dvh"
		/>
		<!-- Sketch's chrome over the frame. It takes no pointer events itself; each widget opts back in. -->
		<div data-sketch-ui="shell" class="pointer-events-none fixed inset-0">
			<Toolbar v-if="shown" :noter="noter" />
		</div>
	</FrappeUIProvider>
</template>
