export function pathToFileURL(p) { return new URL('file://' + p) }
export function fileURLToPath(u) { return String(u).replace('file://', '') }
export function parse(u) { try { const x = new URL(u, 'file:///'); return { pathname: x.pathname, search: x.search, query: x.search.slice(1), href: x.href } } catch { return { pathname: u } } }
export default { pathToFileURL, fileURLToPath, parse }
