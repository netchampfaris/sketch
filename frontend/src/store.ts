/**
 * The reads every screen shares.
 *
 * Writes are not here. A card owns its own rename, delete and public toggle,
 * so one card's spinner never disables the others.
 */
import { call, toast, useCall } from 'frappe-ui'
import type { AgentToken, Prototype, Recipe, SketchSession } from './types'

/** A whitelisted method in `sketch/api.py`. */
export function method(name: string): string {
  return `/api/v2/method/sketch.api.${name}`
}

export const session = useCall<SketchSession>({
  url: method('get_session'),
  immediate: false,
})

export const prototypes = useCall<Prototype[]>({
  url: method('list_prototypes'),
  immediate: false,
  initialData: [],
})

export const recipes = useCall<Recipe[]>({
  url: method('list_recipes'),
  immediate: false,
  initialData: [],
})

// `initialData` keeps the connection card at full height while the token
// loads. Without it the card collapses and the page jumps (problem C7).
export const agentToken = useCall<AgentToken>({
  url: method('get_agent_token'),
  immediate: false,
  initialData: { token: '', endpoint: '' },
})

/** Send a signed-out visitor to the login page and back again. */
export function goToLogin(): void {
  const back = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.href = `/login?redirect-to=${back}`
}

/**
 * End the session, then send the browser to the login page.
 *
 * `logout` is POST only, so `call` is the right door: it posts, and it adds
 * the CSRF token that `sketch/www/sketch.py` puts on `window`. The path comes
 * from the session, never from a literal here.
 *
 * A silent failure would leave the user signed in on a login page, so the
 * browser only moves after the server answers. On an error the user stays put
 * and reads a toast.
 */
export async function logout(): Promise<void> {
  const url = session.data?.logout_url
  if (url) {
    try {
      await call(url)
    } catch {
      toast.error('Could not sign out. Try again.')
      return
    }
  }
  window.location.href = '/login'
}

/**
 * The textarea fallback for a browser with no async clipboard.
 *
 * `execCommand('copy')` returns false instead of throwing when the write is
 * refused, so the boolean is the only failure signal there is. The field is
 * removed in `finally`: an exception used to leave an invisible textarea in
 * the DOM, and every later copy added another one.
 */
function copyWithTextarea(text: string): boolean {
  const field = document.createElement('textarea')
  field.value = text
  field.style.position = 'fixed'
  field.style.opacity = '0'
  document.body.appendChild(field)
  try {
    field.select()
    return document.execCommand('copy')
  } finally {
    document.body.removeChild(field)
  }
}

/**
 * Put text on the clipboard. Falls back to a hidden textarea on http.
 *
 * Rejects when the text did not reach the clipboard, after showing the text
 * so the user can select it by hand. A silent failure was worse than no copy
 * at all: the user believed the token was on the clipboard, pasted whatever
 * was there before into an agent config, and blamed the token.
 *
 * `navigator.clipboard.writeText` rejects on a denied permission, on a
 * document that is not focused, and on any page the browser does not treat as
 * a secure context. None of that is visible to the caller otherwise.
 *
 * The rejection is the contract, not a leak: every caller awaits this and
 * then reports success, so swallowing the error would put a green "Copied"
 * toast next to the red one. `toast` de-duplicates on `id`, so a burst of
 * failed copies replaces one message instead of stacking (DESIGN.md >
 * Toasts).
 */
export async function copyText(text: string): Promise<void> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return
    }
    if (!copyWithTextarea(text)) throw new Error('execCommand("copy") was refused')
  } catch (error) {
    toast.error(`Could not copy. Select this and copy it by hand: ${text}`, {
      id: 'copy-text',
    })
    throw error
  }
}
