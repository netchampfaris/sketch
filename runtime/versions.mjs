// Runtime version order. Folder names are frappe-ui versions, and a plain
// string sort puts 1.0.0-rc.2 after 1.0.0. A release sorts after its
// prereleases, the same as semver and PEP 440.
//
//   node versions.mjs newest <dir>   prints the newest version folder in <dir>
import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

function parts(version) {
	const [release, pre] = version.split('-', 2)
	return { release: release.split('.').map(Number), pre: pre ? pre.split('.') : null }
}

export function compare(a, b) {
	const x = parts(a)
	const y = parts(b)
	for (let i = 0; i < Math.max(x.release.length, y.release.length); i++) {
		const d = (x.release[i] ?? 0) - (y.release[i] ?? 0)
		if (d) return d
	}
	if (!x.pre || !y.pre) return (x.pre ? -1 : 0) - (y.pre ? -1 : 0)
	for (let i = 0; i < Math.max(x.pre.length, y.pre.length); i++) {
		const [p, q] = [x.pre[i], y.pre[i]]
		if (p === undefined) return -1
		if (q === undefined) return 1
		const [m, n] = [Number(p), Number(q)]
		const d = Number.isNaN(m) || Number.isNaN(n) ? p.localeCompare(q) : m - n
		if (d) return d
	}
	return 0
}

/** The newest version folder in `dir`, or null when it has none. */
export function newest(dir) {
	const versions = readdirSync(dir).filter(
		(name) => /^\d/.test(name) && statSync(join(dir, name)).isDirectory(),
	)
	return versions.sort(compare).pop() ?? null
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv[2] === 'newest') {
	const version = newest(process.argv[3])
	if (!version) process.exit(1)
	console.log(version)
}
