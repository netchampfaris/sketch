export function deprecate(fn) { return fn }
export function inspect(x) { return String(x) }
export function promisify(fn) { return fn }
export default { deprecate, inspect, promisify }
