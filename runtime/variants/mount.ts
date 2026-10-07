// The pill host mounts lazily, the first time a set or a state does, so a Prototype without either
// gets no extra DOM.
import { createApp } from 'vue'
import Pill from './Pill.vue'
import { mirrorStates } from './state'

let mounted = false
export function mountPill(router: any) {
  if (mounted || document.documentElement.dataset.sketchChrome === 'off') return
  mounted = true
  const el = document.createElement('div')
  el.setAttribute('data-sketch-ui', 'variants')
  document.body.append(el)
  const app = createApp(Pill)
  app.use(router)
  // A navigation without the `s` query puts it back.
  router.afterEach((to: any) => { mirrorStates(router, to) })
  app.config.errorHandler = (err) => console.error('[sketch variants]', err)
  app.mount(el)
}
