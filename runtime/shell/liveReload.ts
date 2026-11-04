// The owner's live reload. The shell is on Sketch's origin with the session, so it asks the session
// method the Sketch UI uses (`sketch.api.prototype_revision`) and, when the revision moves, reloads the
// iframe alone. The shell, its route and its state stay put.
//
// A write from the shell's own chrome (Make default and the rest, actions.ts) reloads the frame itself. It holds
// the poll while it is in flight, and its release moves the baseline to the revision the write left, so the
// change is one reload and a poll that was already out when the write began can't add a second.
const POLL_MS = 2000 // a stat walk on the server, cheap to answer
const POLL_MAX_MS = 30000 // the ceiling the backoff climbs to after failures

export type LiveReload = { stop: () => void; hold: () => Promise<() => Promise<void>> }

export function startLiveReload(slug: string, baseline: string, reload: () => void): LiveReload {
	let rev = baseline
	let wait = POLL_MS
	let timer: ReturnType<typeof setTimeout> | null = null
	let stopped = false
	let held = 0
	// Moves on every hold and release: a poll that set out before either drops what it heard.
	let epoch = 0

	const clear = () => {
		if (timer) clearTimeout(timer)
		timer = null
	}
	const schedule = () => {
		clear()
		// A background tab must not poll. visibilitychange restarts it. A write in flight holds it.
		if (!stopped && !held && !document.hidden) timer = setTimeout(poll, wait)
	}

	async function revision() {
		const url = `/api/method/sketch.api.prototype_revision?slug=${encodeURIComponent(slug)}`
		const response = await fetch(url, { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } })
		if (!response.ok) throw new Error(String(response.status))
		const next = (await response.json())?.message?.rev
		if (typeof next !== 'string' || !next) throw new Error('no revision')
		return next
	}

	async function poll() {
		timer = null
		const at = epoch
		let next = ''
		try {
			next = await revision()
			wait = POLL_MS
		} catch {
			// Silent: a dead endpoint leaves the page as it is. Back off and keep going.
			wait = Math.min(wait * 2, POLL_MAX_MS)
		}
		// A write began or ended meanwhile: it has the frame in hand, and it starts the poll again.
		if (at !== epoch) return
		if (next && next !== rev) {
			rev = next
			reload()
		}
		schedule()
	}

	async function hold() {
		held++
		epoch++
		clear()
		return async () => {
			try {
				rev = await revision()
			} catch {
				// The next poll compares against the old baseline, and reloads once more at worst.
			}
			held--
			epoch++
			schedule()
		}
	}

	const onVisibility = () => (document.hidden ? clear() : !timer && schedule())
	document.addEventListener('visibilitychange', onVisibility)
	schedule()
	return {
		stop: () => {
			stopped = true
			clear()
			document.removeEventListener('visibilitychange', onVisibility)
		},
		hold,
	}
}
