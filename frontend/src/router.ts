import { createRouter, createWebHistory } from 'vue-router'

/**
 * The SPA route for a request path.
 *
 * The SPA lives at "/" (spec 3), but `get_home_page()` still answers
 * "sketch", so core's login redirect lands on /sketch, and
 * `website_route_rules` serves /sketch/<path> as well. Both forms reach the
 * same routes, so drop the prefix before the router reads the path.
 *
 * `App.vue` calls this too, on the path it takes out of the after-login
 * cookie. That path is a request path and can carry the same prefix.
 */
export function toSpaPath(path: string): string {
  if (path === '/sketch' || path.startsWith('/sketch/')) {
    return path.slice('/sketch'.length) || '/'
  }
  return path
}

// The rewrite runs before createWebHistory reads the location, and the user
// never sees the old path.
const path = window.location.pathname
const spaPath = toSpaPath(path)
if (spaPath !== path) {
  window.history.replaceState({}, '', spaPath + window.location.search)
}

// The Viewer route /u/<username>/<slug> belongs to the Python renderer and is
// deliberately not claimed here.
//
// `meta.public` marks a route that renders with no session. `App.vue` reads it
// instead of bouncing every failed `get_session` to /login, and
// `sketch/www/sketch.py` PUBLIC_PATHS has to name the same paths, or the
// server sends the Guest away before the bundle loads. `hooks.py`
// `website_route_rules` has to name every route here, public or not, or a
// direct load of it is a 404.
export const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    {
      path: '/',
      name: 'Prototypes',
      component: () => import('./pages/PrototypesScreen.vue'),
    },
    {
      path: '/feed',
      name: 'Feed',
      component: () => import('./pages/FeedScreen.vue'),
      meta: { public: true },
    },
    {
      path: '/about',
      name: 'About',
      component: () => import('./pages/AboutScreen.vue'),
      meta: { public: true },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('./pages/SettingsScreen.vue'),
    },
  ],
})
