// A write from the Viewer reloads the page, and a sandboxed page has no storage, so what the next page shows rides in
// `window.name`, which survives a reload. `mark` is a result to announce. `pending` is an Undo toast still on screen: a
// live reload (the agent wrote) must not drop it silently. Make default (default.ts) and Delete variant (edit.ts) share it.

// How long an Undo toast stays. The page takes a moment to reload, and the person then looks for the change before
// reaching for Undo.
export const UNDO_MS = 10000

export function carrier<T>(mark: string, pending: string) {
  return {
    // Leave `note` for the next page to announce, and reload.
    reload(note: T) {
      window.name = mark + JSON.stringify(note)
      location.reload()
    },
    // What the last page left, and whether it was an Undo toast still up. Read once: it is cleared either way. A page
    // that set its own window.name gets nothing, and keeps its name.
    take(): { note: T; pending: boolean } | null {
      const raw = window.name
      const held = raw.startsWith(pending)
      if (!held && !raw.startsWith(mark)) return null
      window.name = ''
      try {
        return { note: JSON.parse(raw.slice((held ? pending : mark).length)) as T, pending: held }
      } catch {
        return null
      }
    },
    // An Undo toast is up: a reload before it goes brings it back.
    hold(note: T) {
      window.name = pending + JSON.stringify(note)
    },
    // The toast is gone: dismissed, timed out, or pressed.
    release() {
      if (window.name.startsWith(pending)) window.name = ''
    },
  }
}
