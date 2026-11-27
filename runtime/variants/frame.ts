// What every render of the app away from the live page shares: a canvas frame (Frame.vue) and the look behind a page's
// closed dialogs (Discover.vue).
import { provide, shallowRef } from 'vue'
import { routeLocationKey, routerKey, routerViewLocationKey, useRouter } from 'vue-router'
import { frameDialogs, type OpenDialogs } from './dialogs'
import { sandboxKey, type Sandbox } from './state'

// Call in the render's setup. The app below renders the page at `path`, with the picks and states of `sandbox`, and
// reports there. `root` is the element it renders in; `open` the Dialogs it shows open (dialogs.ts).
export function useFrame(o: { path: string; sandbox: Sandbox; root: () => HTMLElement | null; open: OpenDialogs }) {
  const router = useRouter()
  const resolved = router.resolve(o.path)
  // App's RouterView and RouterLink follow this page, not the live one.
  provide(routerViewLocationKey, shallowRef(resolved))
  provide(routeLocationKey, resolved as any)
  // It never moves the live page: a page that redirects as it mounts would drop `?canvas=` and close the canvas.
  // Navigating from it does nothing.
  const stay = () => Promise.resolve()
  provide(routerKey, Object.assign(Object.create(router), { push: stay, replace: stay, go: () => {}, back: () => {}, forward: () => {} }))
  provide(sandboxKey, o.sandbox)
  // A page dialog draws in this render, never over the live page.
  frameDialogs(o.root, o.open)
}

// Drawn, but never seen and never in the way: far off the screen, at a window's size.
export const offscreen = (w: number, h: number) => ({ position: 'fixed', left: '-100000px', top: '0', width: w + 'px', height: h + 'px', overflow: 'hidden', contain: 'strict' })
