// The Runtime creates the router in hash mode. A Prototype exports routes only.
import type { RouteRecordRaw } from 'vue-router'
import Browser from './pages/Browser.vue'

// Every route is parameterless: the view key rides in as a static prop. Folder
// drill-down stays inside the Home route, so the Breadcrumbs trail keeps
// working without a route parameter.
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: Browser, props: { view: 'home' } },
  {
    path: '/recents',
    name: 'Recents',
    component: Browser,
    props: { view: 'recents' },
  },
  {
    path: '/favourites',
    name: 'Favourites',
    component: Browser,
    props: { view: 'favourites' },
  },
  {
    path: '/shared',
    name: 'Shared',
    component: Browser,
    props: { view: 'shared' },
  },
  {
    path: '/trash',
    name: 'Trash',
    component: Browser,
    props: { view: 'trash' },
  },
]

export default routes
