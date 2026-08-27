import preflight from 'TWLIB/css/preflight.css'
const files = (globalThis.__twfiles = globalThis.__twfiles || {})
export function readFileSync(p) { if (String(p).endsWith('preflight.css')) return preflight; return files[p] || '' }
export function existsSync(p) { return p in files }
export function statSync() { return { mtimeMs: 0, isFile: () => true, isDirectory: () => false } }
export function readdirSync() { return [] }
export function realpathSync(p) { return p }
export function writeFileSync() {}
export const promises = { readFile: async (p) => readFileSync(p) }
export default { readFileSync, existsSync, statSync, readdirSync, realpathSync, writeFileSync, promises, accessSync() {} }
export function accessSync() {}
