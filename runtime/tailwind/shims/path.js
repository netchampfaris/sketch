const sep = '/'
function normalize(p) { const out = []; for (const s of p.split('/')) { if (!s || s === '.') continue; if (s === '..') out.pop(); else out.push(s) } return (p.startsWith('/') ? '/' : '') + out.join('/') }
function join(...a) { return normalize(a.filter(Boolean).join('/')) }
function resolve(...a) { let r = ''; for (const s of a) { if (!s) continue; r = s.startsWith('/') ? s : r + '/' + s } return normalize(r || '/') }
function dirname(p) { const i = p.lastIndexOf('/'); return i <= 0 ? (i === 0 ? '/' : '.') : p.slice(0, i) }
function basename(p, ext) { let b = p.slice(p.lastIndexOf('/') + 1); if (ext && b.endsWith(ext)) b = b.slice(0, -ext.length); return b }
function extname(p) { const b = basename(p); const i = b.lastIndexOf('.'); return i > 0 ? b.slice(i) : '' }
function isAbsolute(p) { return p.startsWith('/') }
function relative(a, b) { return b }
const posix = { sep, normalize, join, resolve, dirname, basename, extname, isAbsolute, relative }
posix.posix = posix
export { sep, normalize, join, resolve, dirname, basename, extname, isAbsolute, relative, posix }
export default posix
