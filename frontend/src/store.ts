/**
 * The reads every screen shares.
 *
 * Writes are not here. A card owns its own rename, delete and public toggle,
 * so one card's spinner never disables the others.
 */
import { useCall } from 'frappe-ui'
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

export const agentToken = useCall<AgentToken>({
  url: method('get_agent_token'),
  immediate: false,
})

/** Send a signed-out visitor to the login page and back again. */
export function goToLogin(): void {
  const back = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.href = `/login?redirect-to=${back}`
}

/** Put text on the clipboard. Falls back to a hidden textarea on http. */
export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const field = document.createElement('textarea')
  field.value = text
  field.style.position = 'fixed'
  field.style.opacity = '0'
  document.body.appendChild(field)
  field.select()
  document.execCommand('copy')
  document.body.removeChild(field)
}
