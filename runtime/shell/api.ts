// The shell's calls to the server: same-origin POSTs to sketch.viewer_api with the session cookie and Frappe's
// CSRF token from the shell's boot JSON. Who is asking is the session's person (sketch/viewer_api.py `_actor`),
// never anything this page names. Only the shell's own UI calls these; no frame message leads here.
export class HttpError extends Error {
	constructor(public status: number) {
		super(String(status))
	}
}

const BASE = '/api/method/sketch.viewer_api.'
const cred = { name: '', csrf: '' }
export function initApi(name: string, csrf: string) {
	cred.name = name
	cred.csrf = csrf
}

export async function call<T = any>(method: string, fields: Record<string, string> = {}, keepalive = false): Promise<T> {
	const res = await fetch(BASE + method, {
		method: 'POST',
		body: new URLSearchParams({ name: cred.name, ...fields }),
		credentials: 'same-origin',
		cache: 'no-store',
		keepalive,
		headers: { Accept: 'application/json', 'X-Frappe-CSRF-Token': cred.csrf },
	})
	if (!res.ok) throw new HttpError(res.status)
	return (await res.json()).message as T
}
