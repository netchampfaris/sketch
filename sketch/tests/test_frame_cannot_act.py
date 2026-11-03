# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Code in the Prototype's frame can't act as anyone, proven in a real browser.

The Viewer is Sketch's shell with the Prototype in a sandboxed frame (`sketch/viewer.py`). The shell holds the
person's session and makes every write; the frame holds nothing that can act as anyone. This file puts that to the
test the way an attacker would: an invited editor's agent writes an option, `src/variants/@<editor>/evil.vue`, and
the owner opens the canvas, so the option's code runs in the owner's page. On mount it:

1. POSTs, with `credentials: 'include'`, to every write the Viewer has ever had: the session methods the shell uses
   now and every signed door this branch deleted. It GETs and POSTs `comments_list` too, and submits one form.
2. Looks through its document (`script#sketch-data` included) and its globals for a signature, an expiry, a CSRF
   token, a ticket or a pass.
3. Reaches for `parent.document`, sets `top.location`, and opens the shell's URL in a popup.
4. Posts forged messages to the shell: a tile menu and Enter, the Note and Comment keys with a pick and Enter,
   tile picks, Tweak's answer, Escape, types the shell has never heard of, and oversized payloads.

It writes what happened into its own tile, as a list the owner can read, and as JSON in `#evil-report`.
`frame_cannot_act.mjs` signs in as the owner, opens the canvas, reads the report and records every request the
browser made. This module makes the assertions from the database and that record.

The positive control is a second run: the owner uses the shell's own tile menu, Make default on the editor's other
option, then Undo. Both land, so the shell path works while the frame path does not. The attack is disarmed in that
run (an init script sets a flag the option reads), so its forged keys can't race the clicks.

Skips when node, Playwright, the web server or the built shell is absent. A skip is not a pass.
`SKETCH_EVIDENCE_DIR`, when set, is where the runs leave their screenshots.
"""

import base64
import hashlib
import json
import os
import unittest

import frappe
from frappe.sessions import delete_session
from frappe.tests import IntegrationTestCase, set_user

from sketch import annotations, api, badges, comments, prototype_files
from sketch.mcp import tools
from sketch.tests import utils
from sketch.tests.test_viewer_api import open_session
from sketch.viewer import SHELL_HTML

SCRIPT = "frame_cannot_act.mjs"
HOME_FILE = "src/pages/Home.vue"
SET = "Card"

TREE = {
	"src/App.vue": (
		"<script setup lang='ts'>\nimport { RouterView } from 'vue-router'\n</script>\n\n"
		"<template>\n  <div class='min-h-screen w-full bg-surface-base p-8 text-ink-gray-8'>\n"
		"    <RouterView />\n  </div>\n</template>\n"
	),
	HOME_FILE: (
		"<script setup>\nimport { Variants } from 'sketch:variants'\n</script>\n\n"
		"<template>\n  <div class='max-w-xl space-y-4'>\n"
		"    <h1 class='text-2xl font-semibold'>Frame test</h1>\n"
		"    <Variants name='Card'>\n"
		"      <template #plain><div class='rounded-lg border p-4'><p class='text-base'>Plain card</p></div></template>\n"
		"      <template #filled><div class='rounded-lg bg-surface-gray-2 p-4'><p class='text-base'>Filled card</p></div></template>\n"
		"    </Variants>\n  </div>\n</template>\n"
	),
	"src/router.ts": (
		"import type { RouteRecordRaw } from 'vue-router'\n"
		"import Home from './pages/Home.vue'\n\n"
		"const routes: RouteRecordRaw[] = [{ path: '/', name: 'Home', component: Home, meta: { title: 'Home' } }]\n\n"
		"export default routes\n"
	),
}

#: The editor's harmless option: the one the owner makes default from the shell in the control run.
CALM = (
	'<variant set="Card" name="Calm" />\n\n'
	"<template>\n  <div class='rounded-lg border-2 border-outline-gray-3 p-4'><p class='text-base'>Calm card</p></div>\n</template>\n"
)

#: The attack. `__CALLS__` and `__SHELL__` are filled in per run. The calls go in as base64, and the words the scan
#: looks for are built from pieces, so the option's own source (which `sketch-data` carries) never matches its scan.
EVIL = r"""<variant set="Card" name="Evil" />

<script setup>
import { onMounted } from 'vue'

const CALLS = JSON.parse(atob('__CALLS__'))
const SHELL = '__SHELL__'
const w = window
// One run however many times the option mounts. The list is drawn by hand into every copy: a canvas tile is not
// re-rendered once drawn, so a reactive list would stay at its first row.
const state = w.__evil || (w.__evil = { started: false, done: false, rows: [], report: null })
function draw() {
	for (const box of document.querySelectorAll('[data-evil]')) {
		const list = box.querySelector('ul')
		list.replaceChildren(...state.rows.map((r) => {
			const li = document.createElement('li')
			li.className = 'truncate'
			const label = document.createElement('span')
			label.className = 'text-ink-gray-6'
			label.textContent = r.label + ': '
			li.append(label, r.result)
			return li
		}))
		const pre = box.querySelector('pre')
		pre.textContent = state.done ? JSON.stringify(state.report) : ''
		if (state.done) pre.setAttribute('data-done', '1')
	}
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const row = (label, result) => (state.rows.push({ label, result }), draw())
// The browser hides a cross-origin answer from the frame, so a refused call reads as "blocked" here; the server's own
// status (403 for the session methods, 417 for the deleted doors) is in its log, not in the frame.
const said = (r) => (r.error ? 'blocked, no answer' : (r.status >= 200 && r.status < 300 ? 'WENT THROUGH ' : 'refused ') + r.status)
const plain = (t) => t.replace(/^threw (\w+)/, 'refused ($1)').replace(/^no error: /, '')

// The words a credential goes by, assembled so this file's own text holds none of them.
const WORDS = ['s' + 'ig', 'e' + 'xp', 'cs' + 'rf', 'to' + 'ken', 'tic' + 'ket', 'pa' + 'ss']
// A key is a credential's when it is one of the words, ends in _<word>, or holds the third or fifth word anywhere.
const KEY = new RegExp('^(' + WORDS.join('|') + ')$|_(' + WORDS.join('|') + ')$|' + WORDS[2] + '|' + WORDS[4], 'i')
const TEXT = new RegExp('[?&](' + WORDS.slice(0, 2).join('|') + ')=|"(' + WORDS.join('|') + '|' + WORDS[2] + '_' + WORDS[3] + ')"\\s*:|' + WORDS[2], 'i')

async function call(c) {
	const url = new URL('/api/method/' + c.method, location.href)
	const body = new URLSearchParams(c.args)
	try {
		const r = c.get
			? await fetch(url + '?' + body, { credentials: 'include' })
			: await fetch(url, { method: 'POST', credentials: 'include', body })
		return { status: r.status, body: (await r.text()).slice(0, 160) }
	} catch (e) {
		return { error: String(e && e.name ? e.name : e) }
	}
}

function walk(value, path, hits, seen, depth) {
	if (!value || typeof value !== 'object' || depth > 4 || seen.has(value) || seen.size > 20000) return
	seen.add(value)
	let keys = []
	try { keys = Object.keys(value) } catch { return }
	for (const k of keys) {
		if (KEY.test(k)) hits.push(path + k)
		let v
		try { v = value[k] } catch { continue }
		if (typeof v === 'string' && TEXT.test(v)) hits.push(path + k + ' (text)')
		walk(v, path + k + '.', hits, seen, depth + 1)
	}
}

function scan() {
	const hits = []
	const data = document.getElementById('sketch-data')
	if (data) {
		// Every key, and every text but the files': those are the Prototype's own source, this option's included.
		try {
			const slot = JSON.parse(data.textContent)
			walk(slot, 'sketch-data.', hits, new Set([slot.files]), 0)
			for (const path of Object.keys(slot.files || {})) if (KEY.test(path)) hits.push('sketch-data.files.' + path)
		} catch { hits.push('sketch-data (unreadable)') }
	}
	// The document as text, with the data slot left to the walk above: its files are the Prototype's own source.
	const clone = document.documentElement.cloneNode(true)
	clone.querySelector('#sketch-data')?.remove()
	clone.querySelectorAll('[data-evil]').forEach((n) => n.remove())
	if (TEXT.test(clone.outerHTML)) hits.push('document: ' + clone.outerHTML.match(TEXT)[0])
	for (const [name, text] of [['location', location.href], ['referrer', document.referrer], ['window.name', w.name]])
		if (TEXT.test(text)) hits.push(name)
	// The globals the page added, against a blank document's.
	const blank = document.createElement('iframe')
	document.body.appendChild(blank)
	const base = new Set(Object.getOwnPropertyNames(blank.contentWindow))
	blank.remove()
	// The browser's own constructors and functions are native code, not the page's.
	const native = (k) => { try { return typeof w[k] === 'function' && /\[native code\]/.test(Function.prototype.toString.call(w[k])) } catch { return false } }
	const globals = Object.getOwnPropertyNames(w).filter((k) => !base.has(k) && k !== '__evil' && !native(k))
	for (const k of globals) {
		if (KEY.test(k)) hits.push('window.' + k)
		let v
		try { v = w[k] } catch { continue }
		if (typeof v === 'string' && TEXT.test(v)) hits.push('window.' + k + ' (text)')
		walk(v, 'window.' + k + '.', hits, new Set(), 0)
	}
	let cookie
	try { cookie = 'read: ' + JSON.stringify(document.cookie) } catch (e) { cookie = 'threw ' + e.name }
	return { hits, globals: globals.length, cookie }
}

function attempt(run) {
	try { return 'no error: ' + String(run()).slice(0, 80) } catch (e) { return 'threw ' + e.name }
}

function formPost(c) {
	const sink = document.createElement('iframe')
	sink.name = 'evil-sink'
	sink.style.display = 'none'
	document.body.appendChild(sink)
	const form = document.createElement('form')
	form.method = 'POST'
	form.action = new URL('/api/method/' + c.method, location.href).href
	form.target = 'evil-sink'
	for (const [k, v] of Object.entries(c.args)) {
		const input = document.createElement('input')
		input.name = k
		input.value = v
		form.appendChild(input)
	}
	document.body.appendChild(form)
	form.submit()
	return 'submitted'
}

const post = (type, data) => parent.postMessage({ channel: 'sketch-shell', type, data }, '*')
const key = (k) => post('key', { key: k, mods: [], layer: '' })
const PICK = {
	kind: 'click', ref: 'evil', label: 'Card', x: 40, y: 40, shift: false, keyboard: true, picks: [],
	el: { selector: 'h1', component: 'Home', element: 'Heading', text: 'Frame test', state: '' },
	component: { component: 'Home', chain: ['App', 'Home'], file: 'src/pages/Home.vue' },
	rect: { x: 30, y: 30, w: 200, h: 30 },
}

async function forge() {
	const sent = []
	const send = async (type, data, gap = 150) => {
		try { post(type, data); sent.push(type) } catch (e) { sent.push(type + ' (threw ' + e.name + ')') }
		await sleep(gap)
	}
	const tiles = [...document.querySelectorAll('[data-tile-id]')].map((t) => t.getAttribute('data-tile-id'))
	for (const tileId of tiles) {
		await send('tile:menu', { tileId, rect: { x: 600, y: 300, w: 20, h: 20 } }, 400)
		await send('key', { key: 'Enter', mods: [], layer: '' })
		await send('key', { key: 'Escape', mods: [], layer: '' })
	}
	for (const tool of ['n', 'c']) {
		await send('key', { key: tool, mods: [], layer: '' }, 300)
		await send('pick', PICK, 400)
		await send('key', { key: 'Enter', mods: [], layer: '' }, 300)
		await send('key', { key: 'Escape', mods: [], layer: '' })
		await send('key', { key: 'Escape', mods: [], layer: '' })
	}
	for (const option of ['@__EDITOR__/calm', '@__EDITOR__/evil', 'filled'])
		await send('tile:pick', { spot: { route: '/', tile: { kind: 'set', view: 'set:home/card', page: 'Home', group: 'Card', groupKey: 'card', option, optionLabel: option } }, fx: 0.5, fy: 0.5, x: 100, y: 100 })
	await send('tweak:info', { req: '', sels: [{ ref: 'evil', label: 'Evil', classes: ['x'] }], total: 1, joinable: 1, say: 'evil', found: true, outside: false })
	await send('ready', { status: 'ok', routes: ['/'], pages: [{ path: '/', title: 'Home' }] })
	for (const type of ['evil', 'set_variant_default', 'save_annotations', 'comment:add', 'make-default'])
		await send(type, { slug: '__SLUG__', option: '@__EDITOR__/evil', text: 'forged' })
	const big = 'x'.repeat(5 * 1024 * 1024)
	await send('tile:menu', { tileId: big, rect: { x: 1, y: 1, w: 1, h: 1 } })
	await send('pick', { ...PICK, label: big, el: { ...PICK.el, text: big } })
	await send('model', { sets: [{ id: big, name: big, options: [] }], states: [], canOpen: true })
	await send('tweak:info', { req: big, sels: Array.from({ length: 5000 }, () => ({ ref: 'x', classes: ['y'] })) })
	// Not even the envelope.
	try { parent.postMessage('set_variant_default', '*'); parent.postMessage({ type: 'tile:menu', data: {} }, '*'); sent.push('raw') } catch (e) { sent.push('raw (threw)') }
	await send('key', { key: 'Escape', mods: [], layer: '' })
	return sent
}

async function attack() {
	const report = { fetches: [], form: '', creds: null, parentDocument: '', topNavigation: '', popup: '', forged: [] }
	report.creds = scan()
	row('Credentials in the page', report.creds.hits.length ? 'FOUND ' + report.creds.hits.join(', ') : 'none found')
	for (const c of CALLS) {
		const r = await call(c)
		report.fetches.push({ label: c.label, method: c.method, get: !!c.get, ...r })
		row(c.label, said(r))
	}
	report.form = attempt(() => formPost(CALLS[0]))
	row('Make default (form post)', 'sent, answer unreadable')
	report.parentDocument = attempt(() => parent.document.title)
	row("Read the shell's page", plain(report.parentDocument))
	report.topNavigation = attempt(() => { top.location.href = SHELL + '#evil'; return top.location.href })
	row('Navigate the shell', plain(report.topNavigation))
	report.popup = attempt(() => {
		const p = window.open(SHELL + '?evil=1', '_blank')
		if (!p) return 'null'
		let doc
		try { doc = 'read ' + p.document.title } catch (e) { doc = 'threw ' + e.name }
		return 'opened, its document ' + doc
	})
	row('Read a popup of the shell', report.popup.includes('its document threw') ? 'refused (SecurityError)' : plain(report.popup))
	report.forged = await forge()
	row('Forged messages to the shell', report.forged.length + ' sent')
	state.report = report
	state.done = true
	draw()
}

onMounted(() => {
	if (state.started) return draw()
	state.started = true
	if (w.__evilDisarmed) {
		row('Control run', 'disarmed')
		state.report = { disarmed: true }
		state.done = true
		draw()
		return
	}
	attack()
})
</script>

<template>
	<div data-evil class="rounded-lg border border-outline-red-2 bg-surface-red-1 p-3 text-ink-gray-8">
		<p class="text-sm font-semibold text-ink-red-4">An editor's option, trying to act as you</p>
		<!-- Tall from the start: the canvas sizes a tile by its first paint, before any row is in. -->
		<ul class="mt-1.5 grid min-h-[330px] grid-cols-2 content-start gap-x-3 text-[10px] leading-[14px]">
			<li class="truncate">Starting…</li>
		</ul>
		<pre id="evil-report" hidden></pre>
	</div>
</template>
"""

#: Every write a page could reach, old and new, as (label, method, args). The method names alone are what the
#: assertions check; the args are real (this Prototype, its options, a real thread) so a door that opened would
#: show in the database.
def calls(doc, owner_username: str, editor_username: str, thread: str) -> list[dict]:
	name, slug = doc.name, doc.slug
	evil, calm = f"@{editor_username}/evil", f"@{editor_username}/calm"
	variant = {"slug": slug, "file": HOME_FILE, "name": SET, "option": evil}
	undo = {**variant, "sequence": "1"}
	note = json.dumps({"notes": [{"id": "evil", "route": "/", "note": "forged", "offset": {"x": 0, "y": 0}, "rect": {}}], "tweaks": []})
	anchor = json.dumps({"route": "/", "selector": "h1", "element": "Heading", "text": "Frame test", "offset": {"x": 0.5, "y": 0.5}})
	signed = {"name": name, "username": owner_username, "exp": "0", "sig": "x"}
	rows = [
		# The session methods the shell calls now.
		("Make default", "sketch.api.set_variant_default", variant),
		("Undo Make default", "sketch.api.undo_variant_default", undo),
		("Keep only this", "sketch.api.keep_variant", variant),
		("Undo Keep only this", "sketch.api.undo_keep_variant", undo),
		("Delete variant", "sketch.viewer_api.delete_variant", {"name": name, "option": calm}),
		("Undo Delete variant", "sketch.viewer_api.undo_delete_variant", {"name": name, "option": calm, "sequence": "1"}),
		("Save notes", "sketch.viewer_api.save_annotations", {"name": name, "data": note, "epoch": "0"}),
		("Read comments (POST)", "sketch.viewer_api.comments_list", {"name": name}),
		("Comment", "sketch.viewer_api.comment_add", {"name": name, "anchor": anchor, "text": "forged"}),
		("Reply", "sketch.viewer_api.comment_reply", {"name": name, "thread": thread, "text": "forged"}),
		("Edit comment", "sketch.viewer_api.comment_edit", {"name": name, "comment": thread, "text": "forged"}),
		("Delete comment", "sketch.viewer_api.comment_delete", {"name": name, "comment": thread}),
		("Resolve", "sketch.viewer_api.comment_resolve", {"name": name, "thread": thread, "resolved": "1"}),
		("Delete resolved", "sketch.viewer_api.comments_delete_resolved", {"name": name, "also": json.dumps([thread])}),
		("Note from comment", "sketch.viewer_api.comment_note_draft", {"name": name, "comment": thread}),
		("Mark seen", "sketch.viewer_api.seen_mark", {"name": name, "variants": json.dumps([evil]), "threads": json.dumps([thread])}),
		# The owner's other session writes, reached the same way.
		("Restore version", "sketch.api.restore_version", {"slug": slug, "sequence": "1"}),
		("Delete versions", "sketch.api.delete_versions", {"slug": slug, "sequence": "1"}),
		("Make public", "sketch.api.set_public", {"slug": slug, "is_public": "1"}),
		("Invite", "sketch.api.invite_editor", {"slug": slug, "username": editor_username}),
		("Rename", "sketch.api.rename_prototype", {"slug": slug, "title": "forged"}),
		# Every signed door this branch deleted, as the old page called them.
		("Make default (signed)", "sketch.api.set_variant_default_signed", {**signed, **variant}),
		("Undo Make default (signed)", "sketch.api.undo_variant_default_signed", {**signed, **undo}),
		("Keep only this (signed)", "sketch.api.keep_variant_signed", {**signed, **variant}),
		("Undo Keep only this (signed)", "sketch.api.undo_keep_variant_signed", {**signed, **undo}),
		("Delete variant (signed)", "sketch.api.delete_variant_signed", {**signed, "option": calm}),
		("Undo Delete variant (signed)", "sketch.api.undo_delete_variant_signed", {**signed, "option": calm, "sequence": "1"}),
		("Revision (signed)", "sketch.api.signed_revision", signed),
		("Save notes (signed)", "sketch.api.save_annotations", {**signed, "data": note, "epoch": "0"}),
		("Comment pass", "sketch.api.comment_pass", signed),
		("Read comments (signed)", "sketch.api.comments_list", signed),
		("Comment (signed)", "sketch.api.comment_add", {**signed, "anchor": anchor, "text": "forged"}),
		("Reply (signed)", "sketch.api.comment_reply", {**signed, "thread": thread, "text": "forged"}),
		("Resolve (signed)", "sketch.api.comment_resolve", {**signed, "thread": thread, "resolved": "1"}),
		("Mark seen (signed)", "sketch.api.seen_mark", {**signed, "variants": json.dumps([evil])}),
		("Note from comment (signed)", "sketch.api.comment_note_draft", {**signed, "comment": thread}),
	]
	out = [{"label": label, "method": method, "args": args} for label, method, args in rows]
	out.insert(8, {"label": "Read comments (GET)", "method": "sketch.viewer_api.comments_list", "args": {"name": name}, "get": True})
	return out


#: What the shell itself may never send while the attack runs: every write above, by method name.
def write_methods(rows: list[dict]) -> set[str]:
	return {r["method"] for r in rows if "comments_list" not in r["method"]}


class TestAnOptionInTheFrameCannotActAsAnyone(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		reason = utils.node_reason() or utils.webserver_reason()
		if not reason and not os.path.isfile(frappe.get_app_path("sketch", *SHELL_HTML)):
			reason = "the frontend is not built, so there is no shell page"
		if reason:
			raise unittest.SkipTest(reason)

		cls.owner = utils.make_user("fcaown", "d2tfcaown")
		cls.addClassCleanup(utils.drop_user, cls.owner)
		cls.editor = utils.make_user("fcaed", "d2tfcaed")
		cls.addClassCleanup(utils.drop_user, cls.editor)
		cls.owner_username, cls.editor_username = utils.username_of(cls.owner), utils.username_of(cls.editor)

		cls.doc = utils.make_prototype(cls.owner, "d2t-frame-cannot-act", files=TREE)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		with set_user(cls.owner):
			api.invite_editor(cls.doc.slug, cls.editor_username)

		# Something of everyone's to leave alone: both people's notes and the editor's thread.
		cls.seed_notes(cls.owner, None)
		cls.seed_notes(cls.editor, cls.editor)
		cls.thread = comments.add_thread(
			cls.doc.name,
			comments.Actor(cls.editor_username, cls.editor, False),
			{"route": "/", "selector": "h1", "element": "Heading", "text": "Frame test", "offset": {"x": 0.5, "y": 0.5}},
			"Is the heading right?",
		)
		frappe.db.commit()

		viewer = f"/u/{cls.owner_username}/{cls.doc.slug}"
		cls.calls = calls(cls.doc, cls.owner_username, cls.editor_username, cls.thread)
		evil = (
			EVIL.replace("__CALLS__", base64.b64encode(json.dumps(cls.calls).encode()).decode())
			.replace("__SHELL__", f"http://{utils.site_host()}:{utils.webserver_port()}{viewer}")
			.replace("__EDITOR__", cls.editor_username)
			.replace("__SLUG__", cls.doc.slug)
		)
		# The editor's agent writes the two options and commits, as any invited editor can.
		ref = f"{cls.owner_username}/{cls.doc.slug}"
		with set_user(cls.editor):
			for tool, args in (
				("write_files", {"files": [
					{"path": f"src/variants/@{cls.editor_username}/evil.vue", "content": evil},
					{"path": f"src/variants/@{cls.editor_username}/calm.vue", "content": CALM},
				]}),
				("commit", {"prompt": "Add two Card options"}),
			):
				reply = tools.call_tool(tool, {"prototype": ref, **args})
				if reply["isError"]:
					raise AssertionError(reply["content"][0]["text"])

		# The owner has seen both options and the thread, so the shell has no badge of its own to clear.
		badges.mark(cls.doc.name, cls.owner, [f"@{cls.editor_username}/evil", f"@{cls.editor_username}/calm"], [cls.thread])
		frappe.db.commit()

		sid, _ = open_session(cls.owner)
		cls.addClassCleanup(delete_session, sid)
		cls.before = cls.snapshot()
		cls.attack = cls.drive(viewer, sid, "attack")
		cls.after_attack = cls.snapshot()
		cls.control = cls.drive(viewer, sid, "control")
		cls.after_control = cls.snapshot()

	@classmethod
	def seed_notes(cls, user, editor):
		note = {"id": f"seed-{user}", "route": "/", "note": f"A note of {user}", "offset": {"x": 0, "y": 0}, "rect": {}}
		annotations.save(cls.doc.name, json.dumps({"notes": [note], "tweaks": []}), annotations.epoch(cls.doc.name, editor), editor=editor)

	@classmethod
	def drive(cls, viewer: str, sid: str, mode: str) -> dict:
		entry = f"{utils.playwright_root()}/playwright/index.mjs"
		run = utils.run_node(
			SCRIPT,
			entry,
			utils.site_host(),
			str(utils.webserver_port()),
			viewer,
			sid,
			mode,
			os.environ.get("SKETCH_EVIDENCE_DIR", ""),
		)
		if run.returncode != 0:
			raise AssertionError(f"{SCRIPT} {mode} failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
		frappe.db.rollback()
		return json.loads(run.stdout)

	@classmethod
	def snapshot(cls) -> dict:
		name = cls.doc.name
		tree = prototype_files.read_tree(name)
		return {
			"tree": hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest(),
			"versions": frappe.get_all(
				"Sketch Prototype Version", filters={"prototype": name}, fields=["sequence", "kind", "action"], order_by="sequence asc"
			),
			"owner_notes": annotations.read(name),
			"editor_notes": annotations.read(name, editor=cls.editor),
			"comments": frappe.get_all(
				"Sketch Comment",
				filters={"prototype": name},
				fields=["name", "thread", "author", "text", "resolved", "edited"],
				order_by="name asc",
			),
			"seen": sorted(
				(r.user, r.kind, r.item)
				for r in frappe.get_all("Sketch Seen", filters={"prototype": name}, fields=["user", "kind", "item"])
			),
			"prototype": frappe.db.get_value("Sketch Prototype", name, ["title", "is_public"], as_dict=True),
			"editors": sorted(frappe.get_all("Sketch Prototype Editor", filters={"prototype": name}, pluck="user")),
		}

	def say(self, answer: dict | None = None) -> str:
		return json.dumps(answer if answer is not None else self.attack, indent=1)[:6000]

	# --------------------------------------------------------------- it ran

	def test_the_option_ran_in_the_owners_frame_and_tried_every_door(self):
		"""Without this the rest proves nothing: the attack must have run, as the owner looked, and called them all."""
		report = self.attack["report"]
		self.assertEqual(self.attack["frameOrigin"], "null", self.say())
		self.assertEqual([f["method"] for f in report["fetches"]], [c["method"] for c in self.calls], self.say())
		self.assertTrue(report["forged"], self.say())

	# --------------------------------------------------------- every door shut

	def test_every_call_from_the_frame_was_refused(self):
		"""From the browser's own record: each reached the server and got no 2xx, or never got an answer."""
		sent = self.attack["frameRequests"]
		self.assertGreaterEqual(len(sent), len(self.calls), self.say())
		through = [r for r in sent if 200 <= (r.get("status") or 0) < 300]
		self.assertEqual(through, [], self.say())

	def test_the_option_read_no_answer(self):
		through = [f for f in self.attack["report"]["fetches"] if 200 <= (f.get("status") or 0) < 300]
		self.assertEqual(through, [], self.say())

	# ---------------------------------------------------------- nothing changed

	def test_no_version_and_the_same_tree(self):
		self.assertEqual(self.after_attack["versions"], self.before["versions"])
		self.assertEqual(self.after_attack["tree"], self.before["tree"])

	def test_both_peoples_notes_are_untouched(self):
		self.assertEqual(self.after_attack["owner_notes"], self.before["owner_notes"])
		self.assertEqual(self.after_attack["editor_notes"], self.before["editor_notes"])

	def test_no_comment_was_added_changed_or_removed(self):
		self.assertEqual(self.after_attack["comments"], self.before["comments"])

	def test_nothing_new_was_marked_seen(self):
		self.assertEqual(self.after_attack["seen"], self.before["seen"])

	def test_the_prototype_and_its_editors_are_as_they_were(self):
		self.assertEqual(self.after_attack["prototype"], self.before["prototype"])
		self.assertEqual(self.after_attack["editors"], self.before["editors"])

	# ------------------------------------------------------ nothing to steal

	def test_the_frame_holds_no_credential(self):
		creds = self.attack["report"]["creds"]
		self.assertEqual(creds["hits"], [], self.say())
		self.assertTrue(creds["cookie"].startswith("threw"), self.say())

	# ------------------------------------------------------ the shell holds

	def test_the_shells_page_is_out_of_reach(self):
		self.assertTrue(self.attack["report"]["parentDocument"].startswith("threw"), self.say())

	def test_the_shell_was_not_navigated(self):
		self.assertEqual(self.attack["shellUrlAfter"], self.attack["shellUrlBefore"], self.say())

	def test_a_popup_is_no_way_in(self):
		"""A popup either never opens, or opens sandboxed: the option can't read it, and it writes nothing."""
		self.assertNotIn("read ", self.attack["report"]["popup"], self.say())
		for page in self.attack["popups"]:
			self.assertEqual(page["origin"], "null", self.say())

	def test_forged_messages_made_the_shell_send_no_write(self):
		"""The shell (and any popup) sent none of the writes, though the frame told it about menus, picks and keys.

		The frame is where the person's picks, keys and tile ⋯ presses come from, so its messages may open a menu or
		the comment box: that is the design. What they can't do is act. A menu item needs a press that began on it
		(runtime/shell/TileMenu.vue), and a comment needs typing in the shell.
		"""
		writes = write_methods(self.calls)
		sent = [r for r in self.attack["otherRequests"] if r["method"] in writes]
		self.assertEqual(sent, [], self.say())
		self.assertEqual(self.attack["toasts"], [], self.say())

	# ------------------------------------------------------- the shell path

	def test_the_shells_own_menu_still_makes_default_and_undoes_it(self):
		"""The positive control: the owner's click in the shell lands, so the frame's failures are the frame's."""
		control = self.control
		self.assertEqual(control["menuItems"][:1], ["Make default"], self.say(control))
		self.assertEqual(control["writes"], [["sketch.api.set_variant_default", 200], ["sketch.api.undo_variant_default", 200]], self.say(control))
		new = self.after_control["versions"][len(self.after_attack["versions"]) :]
		self.assertEqual([v.action for v in new][:1], ["Made Default"], self.say(control))
		self.assertEqual(len(new), 2, new)
		# Make default adopts the file into the owner's tree: the option is the owner's now.
		self.assertEqual(control["defaultAfterMake"], "adopted/calm", self.say(control))
		self.assertEqual(self.after_control["tree"], self.before["tree"])
