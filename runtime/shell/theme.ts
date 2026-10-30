// The prototype theme (decision 84): light, dark or system, apart from Sketch's own UI theme, which the shell never
// reads or writes. The order is the Viewer's: the theme URL parameter, then the reader's prototype theme (saved on
// their account, `boot.prototype_theme`; a Guest's lives for the visit in this tab's sessionStorage), then system.
// The shell hands the parameter and the preference to the frame in its URL; the frame paints the Prototype and reports
// the theme it shows, and the shell's chrome follows it, as it did inside the page.
import { THEMES, type Theme } from '../shared/protocol'
import { call } from './api'

export const CHOICES = [...THEMES, 'system'] as const
export type Choice = (typeof CHOICES)[number]

const pick = (v: unknown): Theme | null => ((THEMES as readonly unknown[]).includes(v) ? (v as Theme) : null)
const choice = (v: unknown): Choice | null => ((CHOICES as readonly unknown[]).includes(v) ? (v as Choice) : null)
const VISIT = 'sketch:prototype-theme'

function visit(): Choice | null {
	try {
		return choice(sessionStorage.getItem(VISIT))
	} catch {
		return null
	}
}

// The theme the URL fixes, else null.
export const urlTheme = () => pick(new URLSearchParams(location.search).get('theme'))

let signedIn = false
let preference: Choice = 'system'
// Saves go one after another, so quick switching cannot land an older choice after the newest.
let saving: Promise<unknown> = Promise.resolve()
export function initTheme(saved: string | null | undefined, reader: boolean) {
	signedIn = reader
	preference = (reader ? choice(saved) : visit()) ?? 'system'
}
export const preferenceNow = () => preference

// What the chrome paints before the frame says: the same answer the frame will reach.
export const resolveTheme = (): Theme =>
	urlTheme() || pick(preference) || (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')

export function applyTheme(theme: Theme) {
	document.documentElement.dataset.theme = theme
}

// The Prototype's own switch chose a theme (the frame's `theme:choose`), the one way the preference changes. It is one
// of three values on the reader's own account; the shell takes it only right after a click or key the person made (the
// frame's activation reaches the shell), so a page cannot change it on its own. Its choice outranks
// a theme in the link from now on, so the parameter leaves the URL and a reload keeps it.
export function chooseTheme(next: Choice) {
	if (next === preference || !navigator.userActivation?.isActive) return
	preference = next
	const url = new URL(location.href)
	if (url.searchParams.has('theme')) {
		url.searchParams.delete('theme')
		history.replaceState(history.state, '', url)
	}
	if (!signedIn) {
		try {
			sessionStorage.setItem(VISIT, next)
		} catch {
			// No storage: the choice lasts until the tab reloads.
		}
		return
	}
	// Quiet: the page already shows the choice.
	saving = saving.then(() => call('save_prototype_theme', { theme: next })).catch(() => {})
}
