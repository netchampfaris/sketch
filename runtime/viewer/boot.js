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
  applyTheme(data.theme)
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
  parent.postMessage({ type: 'sketch:check', result }, '*')
  return result
}

run().catch((e) => {
  errors.push({ kind: 'boot', message: String(e?.message || e), stack: e?.stack })
  report('boot-failed')
})
