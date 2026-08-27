// In-browser SFC compiler. Ticket 05 chose this pair: @vue/compiler-sfc
// (esm-browser) for the SFC, sucrase for type stripping.
import {
  parse,
  compileScript,
  compileStyleAsync,
  compileTemplate,
} from '@vue/compiler-sfc/dist/compiler-sfc.esm-browser.js'
import { transform } from 'sucrase'

const TS = { transforms: ['typescript'], disableESTransforms: true }
// The module registry runs each file as CommonJS, so an import cycle resolves
// the way it does in Node and in a bundler: the partly filled exports object.
const CJS = { transforms: ['imports'], disableESTransforms: true }

// Stable short id per filename, used as the scoped-style hash.
function scopeId(filename) {
  let h = 5381
  for (let i = 0; i < filename.length; i++) h = ((h << 5) + h + filename.charCodeAt(i)) | 0
  return (h >>> 0).toString(16).padStart(8, '0')
}

export function compileTS(filename, source) {
  try {
    return { code: transform(source, { ...TS, filePath: filename }).code, errors: [] }
  } catch (e) {
    return { code: '', errors: [fmt(filename, e)] }
  }
}

// ESM to CommonJS, for the module registry in boot.js.
export function toCJS(filename, source) {
  try {
    return { code: transform(source, { ...CJS, filePath: filename }).code, errors: [] }
  } catch (e) {
    return { code: '', errors: [fmt(filename, e)] }
  }
}

export async function compileSFC(filename, source) {
  const id = scopeId(filename)
  const { descriptor, errors } = parse(source, { filename })
  // Ticket 05: check parse errors before compileScript, or a broken template
  // compiles into a component that renders wrong instead of failing.
  if (errors.length) return { code: '', css: '', errors: errors.map((e) => fmt(filename, e)) }

  const hasTS =
    descriptor.script?.lang === 'ts' || descriptor.scriptSetup?.lang === 'ts'
  const scopedStyle = descriptor.styles.some((s) => s.scoped)

  // A template-only SFC has no script, and compileScript throws on it.
  // Compile the template on its own and wrap it as the component.
  let code
  if (!descriptor.script && !descriptor.scriptSetup) {
    const t = compileTemplate({
      source: descriptor.template?.content ?? '',
      filename,
      id,
      scoped: scopedStyle,
    })
    if (t.errors.length) return { code: '', css: '', errors: t.errors.map((e) => fmt(filename, e)) }
    code = t.code + '\nconst __sfc__ = { render }\n'
  } else {
    let script
    try {
      script = compileScript(descriptor, { id, inlineTemplate: true, genDefaultAs: '__sfc__' })
    } catch (e) {
      return { code: '', css: '', errors: [fmt(filename, e)] }
    }
    code = script.content
  }
  if (hasTS) {
    const out = compileTS(filename, code)
    if (out.errors.length) return { code: '', css: '', errors: out.errors }
    code = out.code
  }

  let css = ''
  const cssErrors = []
  for (const style of descriptor.styles) {
    const res = await compileStyleAsync({
      source: style.content,
      filename,
      id: `data-v-${id}`,
      scoped: style.scoped,
    })
    if (res.errors.length) cssErrors.push(...res.errors.map((e) => fmt(filename, e)))
    css += res.code
  }
  if (cssErrors.length) return { code: '', css: '', errors: cssErrors }

  code += `\n__sfc__.__file = ${JSON.stringify(filename)}\n`
  if (scopedStyle) code += `__sfc__.__scopeId = ${JSON.stringify('data-v-' + id)}\n`
  code += 'export default __sfc__\n'
  return { code, css, errors: [] }
}

function fmt(filename, e) {
  const loc = e.loc?.start || e.loc || {}
  return {
    file: filename,
    line: loc.line ?? null,
    column: loc.column ?? null,
    message: e.message || String(e),
  }
}
