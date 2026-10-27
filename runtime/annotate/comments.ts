// Comments: conversations between people, pinned to elements of the live page. The state, the calls
// and the sorting live here; the .vue files draw. Comments are not notes: they never enter `notes`,
// the prompt or the owner's saved annotations, and each change is its own call to the server
// (sketch/comments.py), so nothing here ever replaces the whole set.
//
// The page holds a ticket, not a pass. The pass (15 minutes) is minted when Comment mode opens and
// renewed while the person is active; leaving Comment mode drops it. The Viewer is sandboxed and sends
// no cookie, so every call carries the pass and nothing else.
import { computed, ref } from 'vue'
import { readThread, setUnread } from 'sketch:variants'
import type { TileSpot } from 'sketch:variants'
import { host } from './host'
import type { Note } from './annotate'

// `author` is the username; `name` the full name the server sends with it (the username when there is none).
export type Reply = { id: string; author: string; name: string; text: string; ts: number; edited: boolean }
// Where a thread sits: a note's anchor without the words.
export type Anchor = Omit<Note, 'id' | 'note' | 'createdAt' | 'sent'>
// `unread` is how many comments by others this person has not seen; `mentioned` says one of them names this person.
export type Thread = Reply & { resolved: boolean; anchor: Anchor; replies: Reply[]; unread: number; mentioned: boolean }
export type Person = { name?: string; image?: string }
// Someone a comment can mention: the owner, the editors and, on a public prototype, everyone who has commented.
export type Mentionable = { username: string; name: string; image: string }

const BASE = '/api/method/sketch.api.'
const POLL_MS = 20000
const PASS_MARGIN_S = 60
export const MAX_BYTES = 4096

export const threads = ref<Thread[]>([])
export const people = ref<Record<string, Person>>({})
export const mentionable = ref<Mentionable[]>([])
// idle until Comment mode opens; loading on the first read; error when it failed with nothing to show.
export const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
export const showResolved = ref(false)
export const query = ref('')
// The thread whose popover is open, so its pin can wear a ring.
export const openThread = ref<string | null>(null)

// How many threads still need an answer: the server's count until the first read, then ours.
export const openCount = computed(() => (status.value === 'ready' ? threads.value.filter((t) => !t.resolved).length : host.openCount))

const byNewest = (a: Thread, b: Thread) => b.ts - a.ts || (a.id < b.id ? 1 : -1)
export const resolvedCount = computed(() => threads.value.filter((t) => t.resolved).length)
// Newest unresolved first; resolved ones follow only when asked for.
export const sorted = computed(() => {
  const open = threads.value.filter((t) => !t.resolved).sort(byNewest)
  return showResolved.value ? [...open, ...threads.value.filter((t) => t.resolved).sort(byNewest)] : open
})
// Search matches the words of any comment in a thread, or the name or username of anyone who took part.
export const matching = computed(() => {
  const q = query.value.trim().toLowerCase().replace(/^@/, '')
  if (!q) return sorted.value
  return sorted.value.filter((t) => [t, ...t.replies].some((c) => [c.text, c.author, c.name].some((w) => w.toLowerCase().includes(q))))
})
export const byteLength = (s: string) => new TextEncoder().encode(s).length

// ---- The pass ------------------------------------------------------------------------------
let pass: { exp: number; sig: string } | null = null
let minting: Promise<{ exp: number; sig: string }> | null = null

const now = () => Date.now() / 1000

async function mint() {
  const form = new URLSearchParams({ name: host.name, username: host.me, exp: host.ticketExp, sig: host.ticketSig })
  const res = await fetch(`${BASE}comment_pass`, { method: 'POST', body: form, credentials: 'omit', cache: 'no-store' })
  if (!res.ok) throw new HttpError(res.status)
  const { message } = await res.json()
  pass = { exp: Number(message.exp), sig: String(message.sig) }
  return pass
}

async function ensurePass(force = false) {
  if (!force && pass && pass.exp - now() > PASS_MARGIN_S) return pass
  minting ??= mint().finally(() => (minting = null))
  return minting
}

export class HttpError extends Error {
  constructor(public status: number) {
    super(String(status))
  }
}

// One call as the signed-in person. A 404 may only mean the pass went stale, so it is asked for
// again once before it counts.
async function call<T = any>(method: string, fields: Record<string, string> = {}): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    const p = await ensurePass(attempt > 0)
    const form = new URLSearchParams({ name: host.name, username: host.me, exp: String(p.exp), sig: p.sig, ...fields })
    const res = await fetch(BASE + method, { method: 'POST', body: form, credentials: 'omit', cache: 'no-store' })
    if (res.status === 404 && attempt === 0) continue
    if (!res.ok) throw new HttpError(res.status)
    return (await res.json()).message as T
  }
}

// ---- Reading ---------------------------------------------------------------------------------
const RECENT_MS = 5000
const readAt: Record<string, number> = {}
let timer = 0
let listening = false

export async function load(silent = false) {
  if (!silent && status.value !== 'ready') status.value = 'loading'
  try {
    const r = await call<{ threads: Thread[]; people: Record<string, Person>; mentionable: Mentionable[] }>('comments_list')
    // A thread opened a moment ago is read, even if the server has not heard yet.
    for (const t of r.threads) if (t.unread && Date.now() - (readAt[t.id] ?? 0) < RECENT_MS) t.unread = 0
    threads.value = r.threads
    people.value = r.people
    mentionable.value = r.mentionable
    status.value = 'ready'
    setUnread(r.threads.map((t) => ({ id: t.id, route: t.anchor.route, unread: t.unread, mention: t.mentioned })))
    // A thread that is open shows what came in: it stays read.
    const open = threadById(openThread.value)
    if (open?.unread) read(open.id)
  } catch (e) {
    // A quiet refresh that fails keeps what is on screen.
    if (!silent || status.value !== 'ready') status.value = 'error'
  }
}

// Comment mode opens: read the threads and keep them fresh while the page is in view.
export function startListening() {
  if (listening) return
  listening = true
  void load()
  timer = window.setInterval(() => !document.hidden && void load(true), POLL_MS)
}

// Comment mode closes: no pass is kept, and nothing polls.
export function stopListening() {
  listening = false
  clearInterval(timer)
  pass = null
  openThread.value = null
  query.value = ''
}

// ---- Writing: one change, one call. Each answers with the thread as it now stands. ---------------
function take(t: Thread | null, id?: string) {
  if (t) threads.value = threads.value.some((x) => x.id === t.id) ? threads.value.map((x) => (x.id === t.id ? t : x)) : [...threads.value, t]
  else if (id) threads.value = threads.value.filter((x) => x.id !== id)
  return t
}

export async function createThread(anchor: Anchor, text: string) {
  return take(await call<Thread>('comment_add', { anchor: JSON.stringify(anchor), text }))!
}
export async function reply(thread: string, text: string) {
  take(await call<Thread | null>('comment_reply', { thread, text }), thread)
}
export async function edit(thread: string, comment: string, text: string) {
  take(await call<Thread | null>('comment_edit', { comment, text }), thread)
}
// Deleting the first comment deletes the thread; the server answers with null then.
export async function remove(thread: string, comment: string) {
  take(await call<Thread | null>('comment_delete', { comment }), thread)
}
export async function setResolved(thread: string, resolved: boolean) {
  take(await call<Thread | null>('comment_resolve', { thread, resolved: resolved ? '1' : '0' }), thread)
}
// The person opened a thread: it is read, here at once and on the server when it can be told.
export function read(id: string) {
  readAt[id] = Date.now()
  const t = threadById(id)
  if (t?.unread) threads.value = threads.value.map((x) => (x.id === id ? { ...x, unread: 0 } : x))
  readThread(id)
}
// The owner copies a comment into a note of their own; the comment stays. The row is the new note.
export const toNote = (comment: string) => call<Note>('comment_to_note', { comment })

// Where a canvas thread sits, or null for a thread on the live page.
export const spotOfThread = (t: Thread): TileSpot | null => (t.anchor.tile ? { route: t.anchor.route, tile: t.anchor.tile } : null)
export const threadById = (id: string | null | undefined) => (id ? threads.value.find((t) => t.id === id) : undefined)
export const personOf = (username: string) => people.value[username] ?? {}

// ---- Time --------------------------------------------------------------------------------------
export function ago(ts: number): string {
  const s = Math.max(0, now() - ts)
  if (s < 60) return 'now'
  if (s < 3600) return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}h`
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d`
  return new Date(ts * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
export const whenOf = (ts: number) => new Date(ts * 1000).toLocaleString()

// ---- Mentions ----------------------------------------------------------------------------------
// A mention is stored in the text as `@[username]` (sketch/comments.py), and drawn as the person's full name.
const TOKEN = /@\[([a-z][a-z0-9-]{2,29})\]/g
export const nameOf = (username: string) => people.value[username]?.name || mentionable.value.find((m) => m.username === username)?.name || username

// The words with each mention as "@Full Name", for a list row or a title.
export const plain = (text: string) => text.replace(TOKEN, (_, u: string) => `@${nameOf(u)}`)

// The words in pieces, so a mention can be drawn in its own colour. Text is never HTML.
export type Piece = { text: string; mention?: string }
export function pieces(text: string): Piece[] {
  const out: Piece[] = []
  let at = 0
  for (const m of text.matchAll(TOKEN)) {
    if (m.index! > at) out.push({ text: text.slice(at, m.index) })
    out.push({ text: `@${nameOf(m[1])}`, mention: m[1] })
    at = m.index! + m[0].length
  }
  if (at < text.length) out.push({ text: text.slice(at) })
  return out
}

// The first line of a comment, for the list.
export const firstLine = (text: string) => plain(text).split('\n').find((l) => l.trim())?.trim() ?? ''


// A page's name for the list: the router's name for it, else its last path segment ("/" is Home).
export function pageName(route: string): string {
  let name = ''
  try {
    const n = host.router?.resolve(route).name
    if (typeof n === 'string') name = n
  } catch {}
  if (!name) name = route.split('?')[0].split('/').filter(Boolean).pop() ?? 'Home'
  const words = name.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/[-_]+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}
