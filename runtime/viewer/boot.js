// The Viewer's boot script. Runs inside the iframe. Reads a Prototype's source
// tree out of the page, compiles it in the browser, links it, mounts it, and
// reports what happened.
import { createApp, h } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import { FrappeUI, FrappeUIProvider } from 'frappe-ui'
import { compileSFC, compileTS, toCJS } from 'sketch:compiler'
import { start as startTailwind, stats as twStats } from 'sketch:tailwind'

const t = { boot: performance.now() }
const errors = []
const consoleErrors = []
const warnings = []
// Tags the template compiler could not bind to an import. Some of them are
// registered globally by a plugin, so the check happens after mount.
const candidates = []
let router = null
// The payload readData() returned. `report` needs it to paint the status, and
// `report` also runs from the catch below, where readData() itself is what
// threw, so it stays null until the read succeeds.
let payload = null

// ---------------------------------------------------------------- error trap
window.addEventListener('error', (e) =>
  errors.push({ kind: 'runtime', message: e.message, file: e.filename, line: e.lineno }),
)
window.addEventListener('unhandledrejection', (e) =>
  errors.push({ kind: 'rejection', message: String(e.reason?.message || e.reason) }),
)
const realConsoleError = console.error.bind(console)
console.error = (...args) => {
  consoleErrors.push(args.map(String).join(' '))
  realConsoleError(...args)
}

// -------------------------------------------------------- upload_file stub
// The only endpoint a frappe-ui component calls on its own (ticket 07).
// It goes over XMLHttpRequest, not fetch, so the stub has to sit on XHR.
const UPLOAD = '/api/method/upload_file'
const RealXHR = window.XMLHttpRequest
window.XMLHttpRequest = class extends RealXHR {
  open(method, url, ...rest) {
    this.__stub = String(url).includes(UPLOAD)
    if (this.__stub) return
    return super.open(method, url, ...rest)
  }
  setRequestHeader(...a) {
    if (!this.__stub) return super.setRequestHeader(...a)
  }
  send(body) {
    if (!this.__stub) return super.send(body)
    const file = body instanceof FormData ? body.get('file') : null
    const finish = (url) => {
      const doc = {
        name: 'stub-' + Math.random().toString(36).slice(2, 10),
        file_name: file?.name || 'file',
        file_url: url,
        is_private: 0,
        file_size: file?.size || 0,
      }
      Object.defineProperties(this, {
        readyState: { value: 4, configurable: true },
        status: { value: 200, configurable: true },
        response: { value: JSON.stringify({ message: doc }), configurable: true },
        responseText: { value: JSON.stringify({ message: doc }), configurable: true },
      })
      this.upload?.onprogress?.({ lengthComputable: true, loaded: doc.file_size, total: doc.file_size })
      this.onreadystatechange?.()
      this.dispatchEvent(new ProgressEvent('load'))
    }
    if (file instanceof Blob) {
      const fr = new FileReader()
      fr.onload = () => finish(fr.result)
      fr.readAsDataURL(file)
    } else {
      finish('data:,')
    }
  }
}

// ------------------------------------------------------------------ the data
// The renderer carries the tree inside the page. There is no files endpoint.
const SLOT = 'sketch-data'
const UNFILLED = 'SKETCH_DATA'

function readData() {
  const el = document.getElementById(SLOT)
  if (!el) throw new Error(`No <script id="${SLOT}"> in the page. The Runtime was not stamped.`)
  const raw = (el.textContent || '').trim()
  if (!raw || raw === UNFILLED)
    throw new Error(`The <script id="${SLOT}"> slot is empty. Open a Prototype, not the Runtime.`)
  return JSON.parse(raw)
}

// Sketch owns the theme. The order is fixed: the theme URL parameter, then
// localStorage["theme"], then the browser preference. The renderer resolves
// the URL parameter and sends null when there is none, because it can read
// neither of the other two. "system" is not an answer, and the Viewer never
// writes localStorage: the Sketch UI shares this origin and owns that key.
const THEMES = ['light', 'dark']
const pick = (value) => (THEMES.includes(value) ? value : null)

function storedTheme() {
  // A sandboxed or partitioned context can throw on the first read.
  try {
    return localStorage.getItem('theme')
  } catch {
    return null
  }
}

function applyTheme(resolved) {
  const url = new URLSearchParams(location.search).get('theme')
  const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  const theme =
    pick(resolved) || pick(url) || pick(storedTheme()) || (dark ? 'dark' : 'light')
  document.documentElement.dataset.theme = theme
}

// ------------------------------------------------------------------- chrome
// Sketch's one piece of DOM inside a Viewer: the status screen. It is plain
// nodes styled by the <style> block in viewer.html, because no frappe-ui
// component renders without Vue and the screen mounts none.
//
// Every string a Prototype owns arrives through textContent. A title is user
// input, and this document already carries the whole source tree.
function el(tag, className, text) {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text !== undefined) node.textContent = text
  return node
}

function icon(name, size) {
  const node = el('span', `${name} ${size} shrink-0`)
  node.setAttribute('aria-hidden', 'true')
  return node
}

// viewer.html still ships the constant "Prototype" in <title>, because the
// renderer substitutes one slot and no more. Two open Prototypes were therefore
// the same entry in the tab strip and in browser history, and every shared link
// had the same name. The payload already carries the title, so stamp it here.
function setTitle(data) {
  const title = typeof data.title === 'string' ? data.title.trim() : ''
  if (title) document.title = title
}

// The gallery embeds one Viewer per card in a same-origin iframe
// (frontend/src/components/PrototypePreview.vue). A framed Viewer is a picture
// of the Prototype: no poller.
const framed = window.top !== window.self

// The one answer to "does this tab reload itself". startLiveReload and the
// status copy both read it, so the promise can never outlive the poller. The
// copy used to read `data.live` alone, so a card preview of the owner's own
// empty Prototype promised a reload that startLiveReload never started.
//
// `data.sig` is the credential the poll needs. The document is sandboxed into
// an opaque origin, so a cookie cannot authenticate the request and the
// renderer mints a signature into the page instead. A document served before
// that change carries none, and it must promise nothing.
function reloadsItself(data) {
  return Boolean(data.live) && Boolean(data.name) && Boolean(data.sig) && !framed
}

// The statuses that leave the page empty. `ok` and `errors` both mounted the
// Prototype, so their paint is the Prototype's own and this must not replace it.
const STATUS_SHAPE = {
  empty: 'empty',
  'compile-failed': 'failed',
  'link-failed': 'failed',
  'boot-failed': 'failed',
}

const FAILED_HEADING = {
  'compile-failed': 'This prototype did not compile',
  'link-failed': 'This prototype did not link',
  'boot-failed': 'This prototype did not start',
}

// Enough to name the mistake. The rest is in window.__sketch, which is what
// `check` reads, and a wall of them stops being legible.
const SHOWN_ERRORS = 5

// "src/pages/About.vue:12:4". compileSFC and compileTS both report line and
// column; a resolve or boot error has neither, and some have no file, so the
// kind labels the row instead of an empty line.
function errorWhere(error) {
  if (!error.file) return error.kind || 'error'
  let where = error.file
  if (Number.isFinite(error.line)) {
    where += `:${error.line}`
    if (Number.isFinite(error.column)) where += `:${error.column}`
  }
  return where
}

function emptyScreen(box, data, name) {
  const owner = Boolean(data.is_owner)
  box.append(el('p', 'text-base-medium text-ink-gray-8', owner ? 'Waiting for your agent' : 'Nothing to show yet'))

  const lines = [`${name} has no files yet.`]
  lines.push(owner ? 'Ask your agent to build a page.' : 'The owner has not built a page yet.')
  // Only a page with a poller behind it may promise a reload.
  if (reloadsItself(data)) lines.push('This tab reloads itself when the files arrive.')
  box.append(el('p', 'sk-status-body text-p-sm text-ink-gray-5', lines.join(' ')))
}

function failedScreen(box, data, status) {
  box.append(el('p', 'text-base-medium text-ink-gray-8', FAILED_HEADING[status]))

  const lead = data.is_owner
    ? reloadsItself(data)
      ? 'Send these errors to your agent. This tab reloads itself after the fix.'
      : 'Send these errors to your agent.'
    : 'The owner has to fix these errors.'
  box.append(el('p', 'sk-status-body text-p-sm text-ink-gray-5', lead))

  const list = el('ul', 'sk-status-list')
  for (const error of errors.slice(0, SHOWN_ERRORS)) {
    const row = el('li', 'sk-error')
    row.append(el('p', 'font-mono text-xs text-ink-gray-5', errorWhere(error)))
    row.append(el('p', 'text-p-sm text-ink-gray-8', String(error.message || 'No message.')))
    list.append(row)
  }
  box.append(list)

  const rest = errors.length - SHOWN_ERRORS
  if (rest > 0) box.append(el('p', 'text-p-xs text-ink-gray-5', `And ${rest} more.`))
}

// `report` used to write window.__sketch and post a message and nothing else,
// so an empty tree and a failed build both left a white page. A new user's
// first URL is a freshly created Prototype, so white was the first thing Sketch
// showed them.
function paintStatus(status, data) {
  const shape = STATUS_SHAPE[status]
  if (!shape) return

  const root = document.getElementById('app')
  // startTailwind runs after the mount and can still throw, and that reports
  // boot-failed. The Prototype is on the screen by then, and a working page is
  // worth more than the message.
  if (!root || root.firstElementChild) return

  const name = typeof data.title === 'string' && data.title.trim() ? data.title.trim() : 'This prototype'
  const box = el('div', 'sk-status-box')
  const glyph = el('span', shape === 'empty' ? 'sk-status-glyph' : 'sk-status-glyph sk-status-glyph-alert')
  glyph.append(icon(shape === 'empty' ? 'lucide-file-plus' : 'lucide-triangle-alert', 'size-6'))
  box.append(glyph)

  if (shape === 'empty') emptyScreen(box, data, name)
  else failedScreen(box, data, status)

  const screen = el('div', 'sk-status')
  screen.append(box)
  root.append(screen)
}

// -------------------------------------------------------------- live reload
// The owner's own tab polls one revision string and reloads when it moves.
// Socket.io is not an option here: Frappe's realtime auth compares the request
// Host against the browser Origin, and the tunnel rewrites Host.
//
// The renderer sends `live: false` for everything except the owner reading
// this Prototype in a session. `check` and a Guest on a public link therefore
// make no request at all. A framed Viewer drops out too, in reloadsItself
// above: twenty cards in iframes would make ten requests a second, and the
// gallery already polls once for the whole grid
// (frontend/src/pages/PrototypesScreen.vue, POLL_MS 4000).
//
// The poll cannot use the session. This document is sandboxed into an opaque
// origin (sketch/viewer.py SANDBOX), so it sends no cookie and it holds no
// csrf_token. It sends the signature the renderer minted into the payload
// instead. That signature reads one revision number for one Prototype and
// opens nothing else (sketch/api.py signed_revision).
const POLL_MS = 2000 // one poll every two seconds: a stat walk, cheap to answer
const POLL_MAX_MS = 30000 // the ceiling the backoff climbs to after failures

function startLiveReload(data) {
  if (!reloadsItself(data)) return

  const url =
    '/api/method/sketch.api.signed_revision?name=' +
    encodeURIComponent(data.name) +
    '&exp=' +
    encodeURIComponent(data.exp) +
    '&sig=' +
    encodeURIComponent(data.sig)
  // The renderer read the revision while it built this page, so the baseline
  // covers the two seconds before the first poll. A write inside that window
  // used to become the baseline, and the page never reloaded. An older served
  // document carries no `rev`, so that one still adopts the first poll.
  let first = typeof data.rev === 'string' && data.rev ? data.rev : null
  let wait = POLL_MS
  let timer = null

  const stop = () => {
    clearTimeout(timer)
    timer = null
  }

  const schedule = () => {
    stop()
    // A background tab must not poll. visibilitychange restarts it.
    if (document.hidden) return
    timer = setTimeout(poll, wait)
  }

  async function poll() {
    try {
      // `omit`, not `same-origin`. An opaque origin has no same origin, and
      // `include` would need Access-Control-Allow-Credentials, which the
      // endpoint deliberately does not send.
      const response = await fetch(url, { cache: 'no-store', credentials: 'omit' })
      if (!response.ok) throw new Error(String(response.status))
      const rev = (await response.json())?.message?.rev
      if (typeof rev !== 'string' || !rev) throw new Error('no revision')
      wait = POLL_MS // a good answer clears the backoff
      if (first === null) first = rev
      else if (rev !== first) {
        stop()
        // The router is hash mode (createWebHashHistory below), so the current
        // page is in location.hash and a reload lands back on it.
        location.reload()
        return
      }
    } catch {
      // Every failure is silent. A dead endpoint must leave the Viewer exactly
      // as it is today, so back off and keep the page working.
      wait = Math.min(wait * 2, POLL_MAX_MS)
    }
    schedule()
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop()
    else if (!timer) schedule()
  })
  schedule()
}

// -------------------------------------------------------------- module link
const EXT = ['', '.ts', '.js', '.vue', '/index.ts', '/index.js']
// Matches `from '…'`, `import '…'`, `import('…')`, `export … from '…'`.
const SPEC = /(\bfrom\s+|\bimport\s*\(\s*|\bimport\s+)(['"])([^'"\n]+)\2/g
// `import <clause> from '<specifier>'`, for the named-export check.
const NAMED_IMPORT = /\bimport\s+([^'";]+?)\s+from\s*(['"])([^'"\n]+)\2/g

function normalize(base, spec) {
  const parts = base.split('/').slice(0, -1)
  for (const seg of spec.split('/')) {
    if (seg === '.' || seg === '') continue
    if (seg === '..') parts.pop()
    else parts.push(seg)
  }
  return parts.join('/')
}

function resolve(files, base, spec) {
  if (!spec.startsWith('.')) return null // bare specifier: the import map owns it
  const target = normalize(base, spec)
  for (const ext of EXT) if (files[target + ext] !== undefined) return target + ext
  return null
}

// Every bare specifier the tree imports, so they load before the registry runs.
function bareSpecifiers(compiled) {
  const out = new Set()
  for (const code of Object.values(compiled))
    for (const m of code.matchAll(SPEC)) if (!m[3].startsWith('.')) out.add(m[3])
  return [...out]
}

// The names a file imports from each bare specifier. ESM checks these at link
// time; the registry runs CommonJS, so the check is here instead.
function namedImports(code) {
  const out = []
  for (const m of code.matchAll(NAMED_IMPORT)) {
    if (m[3].startsWith('.')) continue
    const inner = m[1].match(/\{([^}]*)\}/)
    if (!inner) continue
    for (const part of inner[1].split(',')) {
      const name = part.trim().split(/\s+as\s+/)[0].trim()
      if (name && !name.startsWith('type ')) out.push({ specifier: m[3], name })
    }
  }
  return out
}

// -------------------------------------------------------------- the registry
// Each module runs once, into its own exports object, and that object is
// registered before the body runs. An import cycle therefore sees the partly
// filled exports, the way Node and a bundler resolve one.
function makeRegistry(files, factories, bare) {
  const modules = new Map()
  const styles = new Map()

  function inject(path) {
    if (!styles.has(path)) {
      const el = document.createElement('style')
      el.dataset.sketchCss = path
      el.textContent = files[path]
      document.head.append(el)
      styles.set(path, Object.freeze({ __esModule: true, default: path }))
    }
    return styles.get(path)
  }

  function load(path) {
    const found = modules.get(path)
    if (found) return found.exports
    const module = { exports: {} }
    modules.set(path, module)
    factories[path](module.exports, (spec) => request(path, spec), module)
    return module.exports
  }

  function request(from, spec) {
    if (!spec.startsWith('.')) {
      if (bare.has(spec)) return bare.get(spec)
      throw new Error(`Cannot resolve "${spec}" from ${from}`)
    }
    const hit = resolve(files, from, spec)
    if (!hit) throw new Error(`Cannot resolve "${spec}" from ${from}`)
    if (hit.endsWith('.css')) return inject(hit)
    if (!factories[hit]) throw new Error(`Cannot import "${spec}" from ${from}: not a module`)
    return load(hit)
  }

  return load
}

// ------------------------------------------------------------------- run it
async function run() {
  const data = readData()
  payload = data
  applyTheme(data.theme)
  setTitle(data)
  // Before the early returns below: an empty or broken tree must reload too.
  try {
    startLiveReload(data)
  } catch {
    // The poller is never worth failing the boot for.
  }
  const files = data.files || {}

  // A brand-new Prototype has no files until a recipe or the agent writes one.
  if (!Object.keys(files).length) return report('empty')

  // The Runtime owns the mount, so it needs these two files by name. Say which
  // one is missing, rather than failing later on an undefined import.
  const missing = []
  if (files['src/App.vue'] === undefined) missing.push('src/App.vue')
  if (files['src/router.ts'] === undefined && files['src/router.js'] === undefined)
    missing.push('src/router.ts')
  for (const file of missing)
    errors.push({
      kind: 'precondition',
      file,
      message: `${file} is missing. The Runtime imports it to mount the Prototype.`,
    })
  if (errors.length) return report('link-failed')

  // 1. compile every file
  t.compileStart = performance.now()
  const compiled = {}
  let css = ''
  for (const [path, source] of Object.entries(files)) {
    if (path.endsWith('.vue')) {
      const r = await compileSFC(path, source)
      errors.push(...r.errors.map((e) => ({ kind: 'compile', ...e })))
      for (const m of (r.code || '').matchAll(/_resolveComponent\(\s*"([^"]+)"/g))
        candidates.push({ file: path, tag: m[1] })
      compiled[path] = r.code
      css += r.css
    } else if (path.endsWith('.ts') || path.endsWith('.js')) {
      const r = compileTS(path, source)
      errors.push(...r.errors.map((e) => ({ kind: 'compile', ...e })))
      compiled[path] = r.code
    }
  }
  t.compileEnd = performance.now()
  if (errors.length) return report('compile-failed')

  // 2. link. Relative specifiers resolve inside the tree; bare ones load
  //    through the import map, once, before any module body runs.
  const bare = new Map()
  for (const spec of bareSpecifiers(compiled)) {
    try {
      // A namespace object carries no __esModule, so sucrase's default-import
      // interop would wrap it again. Copy it and mark it.
      bare.set(spec, Object.freeze({ ...(await import(spec)), __esModule: true }))
    } catch (e) {
      errors.push({ kind: 'resolve', message: `Cannot resolve "${spec}". ${String(e?.message || e)}` })
    }
  }
  for (const [path, code] of Object.entries(compiled)) {
    for (const m of code.matchAll(SPEC))
      if (m[3].startsWith('.') && !resolve(files, path, m[3]))
        errors.push({ kind: 'resolve', file: path, message: `Cannot resolve "${m[3]}"` })
    for (const { specifier, name } of namedImports(code)) {
      const ns = bare.get(specifier)
      if (ns && !(name in ns))
        errors.push({ kind: 'resolve', file: path, message: `"${specifier}" has no export named "${name}"` })
    }
  }
  if (errors.length) return report('link-failed')

  const factories = {}
  for (const [path, code] of Object.entries(compiled)) {
    const cjs = toCJS(path, code)
    errors.push(...cjs.errors.map((e) => ({ kind: 'compile', ...e })))
    if (cjs.errors.length) continue
    factories[path] = new Function('exports', 'require', 'module', `${cjs.code}\n//# sourceURL=${path}`)
  }
  if (errors.length) return report('link-failed')
  const load = makeRegistry(files, factories, bare)

  // 3. styles before mount, so first paint is styled
  if (css) {
    const el = document.createElement('style')
    el.id = 'sfc-styles'
    el.textContent = css
    document.head.append(el)
  }

  // 4. mount. The Runtime owns the mount and the router; a Prototype ships
  //    src/App.vue and src/router.ts and no entry file.
  t.mountStart = performance.now()
  const App = load('src/App.vue').default
  const routes = load(files['src/router.ts'] !== undefined ? 'src/router.ts' : 'src/router.js').default
  router = createRouter({ history: createWebHashHistory(), routes })
  // FrappeUIProvider mounts the imperative dialog and toast surfaces. Without
  // it `dialog.confirm()` and `toast.success()` do nothing and report no
  // error, so the Runtime mounts it rather than trusting every Prototype to.
  // It renders no wrapper element of its own.
  const app = createApp(() => h(FrappeUIProvider, null, { default: () => h(App) }))
  app.config.errorHandler = (err, _i, info) =>
    errors.push({ kind: 'vue', message: String(err?.message || err), info })
  app.use(router).use(FrappeUI)

  // Production Vue drops "Failed to resolve component". Rebuild it: every
  // globally registered name is on the app context once the plugins are in.
  const camel = (n) => n.replace(/-(\w)/g, (_, c) => c.toUpperCase())
  const pascal = (n) => camel(n)[0].toUpperCase() + camel(n).slice(1)
  const known = new Set(['RouterView', 'RouterLink'])
  for (const n of Object.keys(app._context.components)) known.add(pascal(n))
  for (const { file, tag } of candidates) {
    if (known.has(pascal(tag))) continue
    warnings.push({
      kind: 'unresolved-component',
      file,
      message: `<${tag}> is not imported or registered. A production build renders nothing for it.`,
    })
  }
  await router.isReady()
  // check walks the routes through this, not through the DOM.
  window.__sketchGoto = async (path) => {
    await router.push(path)
    await nextPaint()
  }
  app.mount('#app')
  await nextPaint()
  t.mounted = performance.now()

  // 5. Tailwind layer 2 for the Prototype's own utilities
  t.twStart = performance.now()
  await startTailwind()
  await nextPaint()
  t.twDone = performance.now()

  report('ok')
}

const round = (n) => (Number.isFinite(n) ? Math.round(n * 10) / 10 : null)

function nextPaint() {
  return new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
}

function report(status) {
  // A Vue error after a clean mount still means the Prototype is broken.
  if (status === 'ok' && errors.length) status = 'errors'
  const result = {
    status,
    errors,
    warnings,
    routes: router ? [...new Set(router.getRoutes().map((r) => r.path))] : [],
    consoleErrors,
    timings: {
      compileMs: round(t.compileEnd - t.compileStart),
      mountMs: round(t.mounted - t.mountStart),
      tailwindMs: round(t.twDone - t.twStart),
      totalMs: round((t.twDone || performance.now()) - t.boot),
    },
    tailwind: twStats,
  }
  window.__sketch = result
  // Every caller passes through here, including the run().catch below, so one
  // call covers every status that leaves the page empty. It runs before the
  // message, because `check` screenshots as soon as the message arrives.
  try {
    paintStatus(status, payload || {})
  } catch {
    // The result is the contract `check` reads, and console.error is captured
    // into it above. A DOM failure must take down neither.
  }
  parent.postMessage({ type: 'sketch:check', result }, '*')
  return result
}

run().catch((e) => {
  errors.push({ kind: 'boot', message: String(e?.message || e), stack: e?.stack })
  report('boot-failed')
})
