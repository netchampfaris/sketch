// The Viewer's boot script. Runs inside the Viewer shell's sandboxed iframe, or
// alone for a `check` run. Reads a Prototype's source tree out of the page,
// compiles it in the browser, links it, mounts it, and reports what happened.
// Nothing here acts as anyone: the page holds no credential, and the chrome that
// writes is the shell's (runtime/shell), on Sketch's own origin.
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

// Sketch owns the theme (decision 84). The preference is light, dark or system, and the order is fixed: the theme
// URL parameter, then the reader's prototype theme (`pref`, which the Viewer shell puts in this frame's URL: saved on
// their account, apart from Sketch's own UI theme, or for a Guest the choice made earlier this visit), then system.
// The renderer resolves the theme parameter and sends null when there is none.
//
// The page sits in an opaque origin, so `localStorage` and `sessionStorage` throw. frappe-ui's `useColorScheme`
// reads and writes `localStorage["theme"]`, and a Prototype may keep its own keys, so the Viewer puts stand-ins there:
// "theme" reads this preference and a write hands it to the shell, which saves it (to the account over the session,
// or to the visit); every other key lives in memory for the page. frappe-ui paints `data-theme` itself on a write, so
// a Prototype's switch applies with no reload.
const THEMES = ['light', 'dark']
const CHOICES = [...THEMES, 'system']
const pick = (value) => (THEMES.includes(value) ? value : null)
const choice = (value) => (CHOICES.includes(value) ? value : null)
const dark = window.matchMedia?.('(prefers-color-scheme: dark)')

let preference = 'system'

function paintTheme() {
  document.documentElement.dataset.theme = pick(preference) || (dark?.matches ? 'dark' : 'light')
}

function applyTheme(data) {
  const params = new URLSearchParams(location.search)
  preference = pick(data.theme) || pick(params.get('theme')) || choice(params.get('pref')) || 'system'
  paintTheme()
}

// The Prototype chose a theme. Its own choice outranks a theme in the link from now on, so the parameter leaves the
// URL and a reload keeps what was picked. The shell saves it (runtime/shell/theme.ts): this frame holds no credential.
function saveTheme(value) {
  const next = choice(value)
  // frappe-ui writes back what it read when it starts: that is no choice.
  if (!next || next === preference) return
  preference = next
  const url = new URL(location.href)
  if (url.searchParams.has('theme')) {
    url.searchParams.delete('theme')
    history.replaceState(history.state, '', url)
  }
  if (parent !== window) parent.postMessage({ channel: 'sketch-shell', type: 'theme:choose', data: { theme: next } }, '*')
}

// System follows the computer while the page is open.
dark?.addEventListener?.('change', () => {
  if (preference === 'system') paintTheme()
})

function memoryBacking() {
  const memory = new Map()
  return {
    get: (key) => (memory.has(key) ? memory.get(key) : null),
    set: (key, value) => memory.set(key, value),
    remove: (key) => memory.delete(key),
    keys: () => [...memory.keys()],
  }
}

// A Storage over `backing`. With `theme`, the "theme" key is the prototype theme above.
function makeStorage(backing, theme) {
  const own = (key) => theme && key === 'theme'
  const others = () => backing.keys().filter((key) => !own(key))
  return {
    getItem: (key) => (own(String(key)) ? preference : backing.get(String(key))),
    setItem: (key, value) => (own(String(key)) ? saveTheme(String(value)) : backing.set(String(key), String(value))),
    removeItem: (key) => (own(String(key)) ? undefined : backing.remove(String(key))),
    clear: () => others().forEach((key) => backing.remove(key)),
    key: (index) => [...(theme ? ['theme'] : []), ...others()][index] ?? null,
    get length() {
      return others().length + (theme ? 1 : 0)
    },
  }
}

// The real storage, when this page can reach it (a `check` run, which is not sandboxed), else null.
function realStorage(name) {
  try {
    const real = window[name]
    real.getItem('theme')
    return {
      get: (key) => real.getItem(key),
      set: (key, value) => real.setItem(key, value),
      remove: (key) => real.removeItem(key),
      keys: () => Array.from({ length: real.length }, (_, i) => real.key(i)),
    }
  } catch {
    return null
  }
}

// Before any Prototype code runs. The page's origin is opaque, so the real storage is normally out of reach; where it
// is reachable it is Sketch's own, whose "theme" key is Sketch's UI theme, so "theme" is always this page's.
function installStorage() {
  for (const name of ['localStorage', 'sessionStorage']) {
    const store = makeStorage(realStorage(name) ?? memoryBacking(), name === 'localStorage')
    try {
      Object.defineProperty(window, name, { value: store, configurable: true, enumerable: true })
    } catch {
      // A browser that will not let the property go keeps throwing, as it did before.
    }
  }
}
installStorage()

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

// viewer.html ships the constant "Prototype" in <title>. The renderer replaces
// it (sketch/viewer.py head_html), and this keeps the tab right for a document
// served without that step.
function setTitle(data) {
  const title = typeof data.title === 'string' ? data.title.trim() : ''
  if (title) document.title = title
}

// The Viewer shell's frame: the renderer marks its payload `chrome: 'shell'`, and `check`'s `chrome: 'off'`
// (sketch/viewer.py frame_payload).
const inShell = (data) => data.chrome === 'shell'

// A `check` run (the Guest request that carries `sig` in its URL) shows the design alone: Variants reads this and
// draws no canvas, and no agent starts.
const chromeOff = (data) => data.chrome === 'off' || new URLSearchParams(location.search).has('sig')

// The payload says nothing about who is reading, so the status copy takes its two facts from the shell (the
// agent's `copy` message): is this the owner, and does the shell reload the frame as the agent writes. Until it
// says, and for `check`, the copy is a reader's.
let copyHints = null
const ownerCopy = () => Boolean(copyHints?.owner)
const reloadCopy = () => Boolean(copyHints?.reloads)

// The statuses that can leave the page empty. `errors` mounted the Prototype,
// but an error thrown while it first rendered leaves #app with nothing in it,
// and the guard in paintStatus keeps any page that did render.
const STATUS_SHAPE = {
  empty: 'empty',
  errors: 'failed',
  'compile-failed': 'failed',
  'link-failed': 'failed',
  'boot-failed': 'failed',
}

const FAILED_HEADING = {
  'compile-failed': 'This prototype did not compile',
  'link-failed': 'This prototype did not link',
  'boot-failed': 'This prototype did not start',
  errors: 'This prototype did not start',
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

function emptyScreen(box, name) {
  const owner = ownerCopy()
  box.append(el('p', 'text-base-medium text-ink-gray-8', owner ? 'Waiting for your agent' : 'Nothing to show yet'))

  const lines = [`${name} has no files yet.`]
  lines.push(owner ? 'Ask your agent to build a page.' : 'The owner has not built a page yet.')
  // Only a page with a poller behind it may promise a reload.
  if (reloadCopy()) lines.push('This tab reloads itself when the files arrive.')
  box.append(el('p', 'sk-status-body text-p-sm text-ink-gray-5', lines.join(' ')))
}

function failedScreen(box, status) {
  box.append(el('p', 'text-base-medium text-ink-gray-8', FAILED_HEADING[status]))

  const lead = ownerCopy()
    ? reloadCopy()
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

  if (shape === 'empty') emptyScreen(box, name)
  else failedScreen(box, status)

  const screen = el('div', 'sk-status')
  screen.append(box)
  root.append(screen)
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
function makeRegistry(files, factories, bare, wrap) {
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
    return wrap ? wrap(hit, load(hit)) : load(hit)
  }

  return load
}

// ------------------------------------------------------- teammates' variants
// src/variants/@name/ is a teammate's folder, written only by that person's agent. src/variants/adopted/ holds the
// ones the owner made the default; src/variants/adopted.json says who made each and which one leads its set.
const GUEST = /^src\/variants\/@[a-z0-9-]+\//
const ADOPTED = /^src\/variants\/adopted\/.+\.vue$/
const REGISTRY = 'src/variants/adopted.json'
const authorOf = (path) => path.split('/')[2].slice(1)

function adoptedRows(files) {
  try {
    const rows = JSON.parse(files[REGISTRY] || '{}')
    return rows && typeof rows === 'object' ? rows : {}
  } catch {
    return {}
  }
}

// `<variant set="KPI strip" name="Compact" />` or `<variant component="src/components/KpiStrip.vue" name="Compact" />`.
// The author is the folder the file is in, never a word in the file.
function variantsOf(data, compiled, blocks, skip, loader) {
  const adopted = adoptedRows(data.files || {})
  const out = []
  for (const path of Object.keys(compiled)) {
    if (!path.endsWith('.vue')) continue
    let author = ''
    let lead = false
    if (GUEST.test(path)) author = authorOf(path)
    else if (ADOPTED.test(path)) {
      author = String(adopted[path]?.author || '')
      lead = Boolean(adopted[path]?.default)
      if (!data.authors?.[author]) continue
    } else continue

    const tag = (blocks[path] || []).find((b) => b.type === 'variant')
    if (!tag) continue
    const text = (k) => (typeof tag.attrs[k] === 'string' ? tag.attrs[k].trim() : '')
    const [name, set, component] = [text('name'), text('set'), text('component')]
    if (!name || Boolean(set) === Boolean(component)) {
      skip(path, '<variant> needs name="…" and exactly one of set="…" or component="…".')
      continue
    }
    if (component && (!component.endsWith('.vue') || compiled[component] === undefined || GUEST.test(component))) {
      skip(path, `${component} is not a component of this prototype.`)
      continue
    }
    out.push({ value: path.slice('src/variants/'.length, -'.vue'.length), label: name, author, set, component, lead, load: () => loader(path) })
  }
  return out
}

// ------------------------------------------------------------------- run it
async function run() {
  const data = readData()
  payload = data
  // Chrome.vue reads this: in the shell's frame the Demo pill is the shell's to draw (runtime/shell/DemoPill.vue).
  document.documentElement.dataset.sketchChrome = chromeOff(data) ? 'off' : 'shell'
  applyTheme(data)
  setTitle(data)
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

  // 1. compile every file. A teammate's file (src/variants/@name/) is compiled apart: a mistake in it is a warning
  //    and the file is skipped, so it can never fail the owner's page. Its styles are dropped.
  t.compileStart = performance.now()
  const compiled = {}
  const blocks = {}
  const view = { ...files }
  let css = ''
  const guests = new Set(Object.keys(files).filter((p) => GUEST.test(p)))
  const skip = (path, message) => {
    delete compiled[path]
    delete view[path]
    warnings.push({ kind: 'variant-skipped', file: path, message: `Skipped, so it is not an option. ${message}` })
  }
  const said = (list) => list.map((e) => (Number.isFinite(e.line) ? `Line ${e.line}: ` : '') + e.message).join(' ')
  for (const [path, source] of Object.entries(files)) {
    const guest = guests.has(path)
    if (guest && !data.authors?.[authorOf(path)]) {
      skip(path, `${authorOf(path)} is not a Sketch user.`)
      continue
    }
    if (path.endsWith('.vue')) {
      const r = await compileSFC(path, source)
      if (guest && r.errors.length) {
        skip(path, said(r.errors))
        continue
      }
      errors.push(...r.errors.map((e) => ({ kind: 'compile', ...e })))
      for (const m of (r.code || '').matchAll(/_resolveComponent\(\s*"([^"]+)"/g))
        candidates.push({ file: path, tag: m[1] })
      compiled[path] = r.code
      blocks[path] = r.blocks || []
      if (!guest) css += r.css
    } else if (path.endsWith('.ts') || path.endsWith('.js')) {
      const r = compileTS(path, source)
      if (guest && r.errors.length) {
        skip(path, said(r.errors))
        continue
      }
      errors.push(...r.errors.map((e) => ({ kind: 'compile', ...e })))
      compiled[path] = r.code
    } else if (guest) {
      delete view[path]
    }
  }
  t.compileEnd = performance.now()
  if (errors.length) return report('compile-failed')

  // 2. link. Relative specifiers resolve inside the tree; bare ones load
  //    through the import map, once, before any module body runs.
  const bare = new Map()
  const load1 = async (spec) => {
    // A namespace object carries no __esModule, so sucrase's default-import
    // interop would wrap it again. Copy it and mark it.
    bare.set(spec, Object.freeze({ ...(await import(spec)), __esModule: true }))
  }
  const owned = Object.fromEntries(Object.entries(compiled).filter(([p]) => !guests.has(p)))
  for (const spec of bareSpecifiers(owned)) {
    try {
      await load1(spec)
    } catch (e) {
      errors.push({ kind: 'resolve', message: `Cannot resolve "${spec}". ${String(e?.message || e)}` })
    }
  }
  for (const [path, code] of Object.entries(owned)) {
    for (const m of code.matchAll(SPEC))
      if (m[3].startsWith('.') && !resolve(view, path, m[3]))
        errors.push({ kind: 'resolve', file: path, message: `Cannot resolve "${m[3]}"` })
    for (const { specifier, name } of namedImports(code)) {
      const ns = bare.get(specifier)
      if (ns && !(name in ns))
        errors.push({ kind: 'resolve', file: path, message: `"${specifier}" has no export named "${name}"` })
    }
  }
  if (errors.length) return report('link-failed')

  // A teammate's files link the same way, and the ones that do not are skipped, one at a time and then whatever
  // imported them.
  const badBare = new Set()
  const guestCode = () => Object.fromEntries(Object.entries(compiled).filter(([p]) => guests.has(p)))
  for (const spec of bareSpecifiers(guestCode()))
    if (!bare.has(spec))
      try {
        await load1(spec)
      } catch {
        badBare.add(spec)
      }
  for (let changed = true; changed; ) {
    changed = false
    for (const [path, code] of Object.entries(guestCode())) {
      let why = ''
      for (const m of code.matchAll(SPEC)) {
        const bad = m[3].startsWith('.') ? !resolve(view, path, m[3]) : badBare.has(m[3])
        if (bad) why = `Cannot resolve "${m[3]}".`
      }
      for (const { specifier, name } of namedImports(code)) {
        const ns = bare.get(specifier)
        if (ns && !(name in ns)) why = `"${specifier}" has no export named "${name}".`
      }
      if (why) {
        skip(path, why)
        changed = true
      }
    }
  }

  const factories = {}
  for (const [path, code] of Object.entries(compiled)) {
    const cjs = toCJS(path, code)
    if (guests.has(path) && cjs.errors.length) {
      skip(path, said(cjs.errors))
      continue
    }
    errors.push(...cjs.errors.map((e) => ({ kind: 'compile', ...e })))
    if (cjs.errors.length) continue
    factories[path] = new Function('exports', 'require', 'module', `${cjs.code}\n//# sourceURL=${path}`)
  }
  if (errors.length) return report('link-failed')

  // The variants teammates made, and the ones the owner adopted: options of the set each one names. They
  // load on first use, inside a boundary (runtime/variants/Variants.vue).
  const extras = variantsOf(data, compiled, blocks, skip, (path) => load(path).default)
  if (extras.length && !bare.has('sketch:variants')) {
    try {
      await load1('sketch:variants')
    } catch (e) {
      extras.length = 0
      warnings.push({ kind: 'variant-skipped', message: `The variants could not load. ${String(e?.message || e)}` })
    }
  }
  const targets = new Set(extras.map((e) => e.component).filter(Boolean))
  const wrapped = new Map()
  // A component a teammate made a variant for becomes a set whose first option is the component itself.
  const wrap = (path, mod) => {
    if (!targets.has(path) || !mod.default) return mod
    if (!wrapped.has(path))
      wrapped.set(
        path,
        Object.freeze({ ...mod, __esModule: true, default: bare.get('sketch:variants').wrapComponent(mod.default, path) }),
      )
    return wrapped.get(path)
  }
  const load = makeRegistry(view, factories, bare, wrap)
  // When each option first appeared, so every set shows its options oldest first (sketch/variant_order.py).
  bare.get('sketch:variants')?.registerSeen?.(data.variant_seen)
  if (extras.length)
    bare.get('sketch:variants').registerExtras(extras, data.authors || {}, (extra, err) =>
      warnings.push({
        kind: 'variant-failed',
        file: `src/variants/${extra.value}.vue`,
        message: `This option did not load. ${String(err?.message || err)}`,
      }),
    )

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
  // A Prototype that imports `sketch:variants` gets the Demo pill and the canvas beside its App. The canvas draws
  // that App in frames, so it is handed the component. It is inside the provider, so its toasts and dialogs work.
  const Chrome = bare.get('sketch:variants')?.Chrome
  const app = createApp(() => h(FrappeUIProvider, null, { default: () => [h(App), Chrome && h(Chrome, { shell: App })] }))
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

// The shell's frame talks to the shell through the agent, whatever the status: an empty or broken tree
// still needs its route, theme and status copy. It is a separate module, loaded after the first paint, so
// it cannot slow or break it, and a failure to load it is a warning and nothing more. A Prototype never
// imports it, and the import map names it for this file alone.
async function startShellAgent(status) {
  try {
    const { startAgent } = await import('sketch:agent')
    startAgent({
      status,
      routes: router ? [...new Set(router.getRoutes().map((r) => r.path))] : [],
      router,
      files: (payload && payload.files) || {},
      repaint: (hints) => {
        copyHints = hints
        document.querySelector('.sk-status')?.remove()
        paintStatus(status, payload || {})
      },
    })
  } catch (e) {
    console.warn('[sketch] the shell agent did not load:', e)
  }
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
  if (payload && inShell(payload) && !chromeOff(payload)) startShellAgent(status)
  return result
}

run().catch((e) => {
  errors.push({ kind: 'boot', message: String(e?.message || e), stack: e?.stack })
  report('boot-failed')
})
