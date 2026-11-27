// frappe-ui Dialogs in a canvas frame. A Dialog renders nothing in place: it portals its panel to <body>, outside the frame,
// and it is modal, so it traps focus, locks the page's scroll and blocks the page's pointer. In a frame (Frame.vue) every
// Dialog portals into the frame and is never modal, so a tile can draw it and the canvas around stays usable. A set whose
// options are dialogs (each slot renders a Dialog at its root) shows them open in its own tiles, whatever the page's state.
// Other overlays (Popover, Dropdown, Tooltip) are left as they were.
import { Fragment, getCurrentInstance, inject, onBeforeMount, onBeforeUpdate, provide } from 'vue'
import type { ComponentInternalInstance, InjectionKey, VNode } from 'vue'
import { Dialog } from 'frappe-ui'

// frappe-ui's own key for where its overlays portal (`usePortalTarget`). `Symbol.for`, so it matches without an import; a
// frappe-ui without it leaves dialogs as they were.
const PORTAL = Symbol.for('frappe-ui:portal-target')

// A <Variants> tag in a frame, for the Dialogs under it: its set's key and its own instance.
export type FrameSet = { key: string; inst: ComponentInternalInstance }
export const frameSetKey: InjectionKey<FrameSet> = Symbol('sketch-frame-set')

// The Dialogs a rendered tree is made of at its top: through fragments and component roots, never into an element. A
// slot of `<NewDialog />` whose root is a `<Dialog>` gives that Dialog; a slot that renders a card gives none.
export function rootDialogs(tree: VNode | null | undefined, out: ComponentInternalInstance[] = []) {
  if (!tree) return out
  if (tree.type === Fragment && Array.isArray(tree.children)) for (const c of tree.children) rootDialogs(c as VNode, out)
  else if (tree.component?.type === Dialog) out.push(tree.component)
  else if (tree.component) rootDialogs(tree.component.subTree, out)
  return out
}

// An open Dialog's panel: the element reka marks `role="dialog"`, wherever it was portalled. Null while it is closed.
function panelOf(v: VNode | null | undefined): Element | null {
  if (!v) return null
  if (v.el instanceof Element && v.el.getAttribute('role') === 'dialog') return v.el
  if (v.component) return panelOf(v.component.subTree)
  if (Array.isArray(v.children)) for (const c of v.children) {
    const found = panelOf(c as VNode)
    if (found) return found
  }
  return null
}

// The panels of the open Dialogs at the top of `tree`.
export const rootPanels = (tree: VNode | null | undefined): Element[] => rootDialogs(tree).flatMap((d) => panelOf(d.subTree) ?? [])

// Finish each panel's opening animation (a slight scale), so it measures at its full size. Gives the panels back.
export function finishOpening(panels: Element[]): Element[] {
  for (const p of panels) for (const a of p.getAnimations()) if (a.effect?.getTiming().iterations !== Infinity) a.finish()
  return panels
}

// Which Dialogs a frame shows open: those of the set its tile shows (the set's key, none for a page tile), or 'all', to
// find the sets inside them (Discover.vue).
export type OpenDialogs = 'all' | (() => string | null | undefined)

// Call in a frame's setup. `root` is the frame's element.
export function frameDialogs(root: () => HTMLElement | null, open: OpenDialogs) {
  provide(PORTAL, undefined)
  // frappe-ui reads the key once, in each overlay's setup, so a getter in its place sees which component is asking.
  const own = (getCurrentInstance() as any).provides
  const outer = Object.getPrototypeOf(own)
  Object.defineProperty(own, PORTAL, {
    configurable: true,
    enumerable: true,
    get: () => tame(root, open) ?? outer?.[PORTAL],
  })
}

// A Dialog's portal target, after setting it up for the frame. Undefined for any other overlay: it gets what it would
// have got without the frame.
function tame(root: () => HTMLElement | null, which: OpenDialogs) {
  const dialog = getCurrentInstance()
  if (!dialog || dialog.type !== Dialog) return undefined
  // The target set's own dialog, at the top of its slot, shows open. Anything else stays as the page has it.
  const set = inject(frameSetKey, null)
  const open = which === 'all' || (!!set && set.key === which() && rootDialogs(set.inst.subTree).includes(dialog))
  // Before every render, after the page's own props land: `modal` falls through to reka's DialogRoot.
  const apply = () => {
    dialog.attrs.modal = false
    if (open) (dialog.props as Record<string, unknown>).open = true
  }
  onBeforeMount(apply, dialog)
  onBeforeUpdate(apply, dialog)
  return () => root() ?? undefined
}

// Whether each frappe-ui Dialog in `tree` is open. A closed one has not mounted its content, so the sets inside it have
// not either. Walks components, fragments and arrays; never into a closed Dialog, which has nothing below it.
export function dialogsIn(tree: VNode | null | undefined, out: boolean[] = []): boolean[] {
  if (!tree) return out
  const c = tree.component
  if (c) {
    if (c.type === Dialog) {
      const p = c.props as Record<string, unknown>
      out.push(!!(p.open ?? p.modelValue))
    }
    return dialogsIn(c.subTree, out)
  }
  if (tree.suspense) return dialogsIn(tree.suspense.activeBranch, out)
  if (Array.isArray(tree.children)) for (const x of tree.children) dialogsIn(x as VNode, out)
  return out
}
