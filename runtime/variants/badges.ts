// What is new for this reader, as the Viewer shell says (runtime/shell/badges.ts holds the server's snapshot and
// reports what the person looks at, over the session). The shell sends only the option values new to this person
// (`display.newOptions`); this keeps them for the visit, for the tile's "New" badge and the Show list's dots. Nothing
// here talks to the server.
//
// A badge stays on screen for the visit it was loaded in, so it never vanishes under the pointer. A dot clears as the
// person looks (`looked`).
import { reactive } from 'vue'

export const badges = reactive({
  // Options new to this person when the page loaded. Nothing removes one before the next visit.
  fresh: {} as Record<string, true>,
  // The ones whose set the person has opened since.
  looked: {} as Record<string, true>,
})

// New since the person last looked, as of this visit's start. The tile's "New" badge.
export const isNew = (option: string) => !!badges.fresh[option]
// New and not yet looked at. The dots.
export const isFresh = (option: string) => !!badges.fresh[option] && !badges.looked[option]
export const freshIn = (options: readonly string[]) => options.filter(isFresh).length

// The person has opened a set on the canvas: every option of it counts as looked at here.
export function lookAt(options: readonly string[]) {
  for (const o of options) if (isFresh(o)) badges.looked[o] = true
}
