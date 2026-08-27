// Browser Tailwind engine for the Viewer. Watches the iframe document and
// compiles the classes a Prototype uses. Layer 2 of the two-layer scheme from
// ticket 06: layer 1 is the precompiled frappe-ui internals CSS, loaded first.
import postcss from 'postcss'
import tailwindcss from 'tailwindcss'
import preset from './preset-browser.js'

const seen = new Set()
let styleEl = null
let pending = null
export const stats = []

// Layer 1 already carries `@tailwind base`, so emit components + utilities only.
const INPUT = '@tailwind components;@tailwind utilities;'
const config = {
  presets: [preset],
  content: { files: ['/template.html'], extract: { html: (s) => s.split(' ') } },
}

function collect() {
  let added = 0
  for (const el of document.querySelectorAll('[class]')) {
    for (const c of el.classList) {
      if (!seen.has(c)) {
        seen.add(c)
        added++
      }
    }
  }
  return added
}

export async function compile(reason, force = false) {
  const added = collect()
  if (!added && !force) return 0
  const t0 = performance.now()
  globalThis.__twfiles['/template.html'] = [...seen].join(' ')
  const res = await postcss([tailwindcss(config)]).process(INPUT, { from: '/input.css' })
  if (!styleEl || !styleEl.isConnected) {
    styleEl = document.createElement('style')
    styleEl.id = 'tw-runtime'
    document.head.append(styleEl)
  }
  styleEl.textContent = res.css
  const ms = performance.now() - t0
  stats.push({ reason, ms, added, classes: seen.size, cssBytes: res.css.length })
  return ms
}

export function start() {
  // Ignore the runtime's own <style> writes, or the observer loops.
  const own = (r) =>
    r.target === styleEl ||
    (r.target === document.head && [...r.addedNodes].every((n) => n === styleEl))
  const obs = new MutationObserver((records) => {
    if (records.every(own)) return
    if (pending) return
    pending = compile('mutation').finally(() => {
      pending = null
    })
  })
  obs.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class'],
    childList: true,
    subtree: true,
  })
  return compile('initial', true)
}
