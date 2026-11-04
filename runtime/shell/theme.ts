// The shell owns the theme, in the Viewer's order: the theme URL parameter, then localStorage["theme"] (the
// Sketch UI writes it, on this same origin), then the browser preference. The shell never writes the key.
// It hands the answer to the frame in the iframe URL for the first paint, since an opaque origin cannot
// read this origin's storage, and from then on follows what the frame reports.
import { THEMES, type Theme } from '../shared/protocol'

const pick = (v: unknown): Theme | null => ((THEMES as readonly unknown[]).includes(v) ? (v as Theme) : null)
const DARK = '(prefers-color-scheme: dark)'

function stored(): Theme | null {
	try {
		return pick(localStorage.getItem('theme'))
	} catch {
		return null
	}
}

// The URL or a saved choice fixes the theme; with neither it follows the system.
export const fixedTheme = (fromServer: Theme | null) =>
	pick(fromServer) || pick(new URLSearchParams(location.search).get('theme')) || stored()

export const resolveTheme = (fromServer: Theme | null): Theme =>
	fixedTheme(fromServer) || (window.matchMedia?.(DARK).matches ? 'dark' : 'light')

export function applyTheme(theme: Theme) {
	document.documentElement.dataset.theme = theme
}

// Calls back when the answer may have moved: the system preference, or the Sketch UI saving one in another tab.
export function watchTheme(changed: () => void): () => void {
	const media = window.matchMedia?.(DARK)
	const onStorage = (e: StorageEvent) => e.key === 'theme' && changed()
	media?.addEventListener('change', changed)
	window.addEventListener('storage', onStorage)
	return () => {
		media?.removeEventListener('change', changed)
		window.removeEventListener('storage', onStorage)
	}
}
