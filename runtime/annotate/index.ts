// The annotate toolbar's entry. boot.js imports this after the Prototype has mounted, and only for
// the owner's own live tab, a signed-in reader of a public Prototype (Comment only), and a Guest on a
// public Prototype (a "Sign in to comment" button). The toolbar is a second Vue app in a body-level host, so it never
// becomes part of the Prototype's vnode tree; it reads the Prototype's app from `#app` and shares
// its router, which is what keeps `useRoute()` in the toolbar in step with the page.
import { createApp } from 'vue'
import Annotate from './Annotate.vue'
import { initHost, isOwner, type Payload } from './host'
import { restore, startSaving } from './store'

export function mountAnnotate(data: Payload) {
  const root = document.getElementById('app') as (HTMLElement & { __vue_app__?: any }) | null
  const router = root?.__vue_app__?.config.globalProperties.$router
  if (!router || !(data.annotate_sig || data.commenter || data.sign_in) || document.querySelector('[data-sketch-ui="annotate"]')) return

  initHost(data, router)
  restore()

  const el = document.createElement('div')
  el.setAttribute('data-sketch-ui', 'annotate')
  document.body.append(el)

  const app = createApp(Annotate)
  app.use(router)
  // The toolbar is never worth breaking the Prototype for, and its errors are not the Prototype's.
  app.config.errorHandler = (err) => console.error('[sketch annotate]', err)
  app.mount(el)
  // Only the owner has notes or tweaks to save.
  if (isOwner()) startSaving()
}
