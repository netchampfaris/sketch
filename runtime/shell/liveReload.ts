// The owner's live reload. The shell is on Sketch's origin with the session, so it asks the session
// method the Sketch UI uses (`sketch.api.prototype_revision`) and, when the revision moves, reloads the
// iframe alone. The shell, its route and its state stay put.
const POLL_MS = 2000 // a stat walk on the server, cheap to answer
const POLL_MAX_MS = 30000 // the ceiling the backoff climbs to after failures

export function startLiveReload(slug: string, baseline: string, reload: () => void): () => void {
	let rev = baseline
	let wait = POLL_MS
	let timer: ReturnType<typeof setTimeout> | null = null
	let stopped = false

	const clear = () => {
		if (timer) clearTimeout(timer)
		timer = null
	}
	const schedule = () => {
		clear()
		// A background tab must not poll. visibilitychange restarts it.
		if (!stopped && !document.hidden) timer = setTimeout(poll, wait)
	}

	async function poll() {
		try {
			const url = `/api/method/sketch.api.prototype_revision?slug=${encodeURIComponent(slug)}`
			const response = await fetch(url, { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } })
			if (!response.ok) throw new Error(String(response.status))
			const next = (await response.json())?.message?.rev
			if (typeof next !== 'string' || !next) throw new Error('no revision')
			wait = POLL_MS
			if (next !== rev) {
				rev = next
				reload()
			}
		} catch {
			// Silent: a dead endpoint leaves the page as it is. Back off and keep going.
			wait = Math.min(wait * 2, POLL_MAX_MS)
		}
		schedule()
	}

	const onVisibility = () => (document.hidden ? clear() : !timer && schedule())
	document.addEventListener('visibilitychange', onVisibility)
	schedule()
	return () => {
		stopped = true
		clear()
		document.removeEventListener('visibilitychange', onVisibility)
	}
}
