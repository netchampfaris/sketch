import { createRouter, createWebHistory } from 'vue-router'

// The SPA lives at "/" (spec 3). `get_home_page()` still answers "sketch", so
// core's login redirect lands on /sketch. The rewrite runs before
// createWebHistory reads the location, and the user never sees the old path.
const path = window.location.pathname
if (path === '/sketch' || path.startsWith('/sketch/')) {
  const rest = path.slice('/sketch'.length) || '/'
  window.history.replaceState({}, '', rest + window.location.search)
}

// The Viewer route /u/<username>/<slug> belongs to the Python renderer and is
// deliberately not claimed here.
export const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    {
      path: '/',
      name: 'Prototypes',
      component: () => import('./pages/PrototypesScreen.vue'),
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('./pages/SettingsScreen.vue'),
    },
  ],
})
