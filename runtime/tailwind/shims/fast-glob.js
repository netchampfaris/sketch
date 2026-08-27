export function sync(patterns) { return [].concat(patterns).filter((p) => !String(p).startsWith('!')) }
export function escapePath(p) { return p }
export function generateTasks(patterns) { const list = [].concat(patterns); return [{ base: '/', dynamic: false, positive: list.filter((p) => !p.startsWith('!')), negative: list.filter((p) => p.startsWith('!')).map((p) => p.slice(1)), patterns: list }] }
export default { sync, escapePath, generateTasks }
