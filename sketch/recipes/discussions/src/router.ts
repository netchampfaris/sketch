// The Runtime creates the router in hash mode. A Prototype exports routes only.
import type { RouteRecordRaw } from 'vue-router'
import Home from './pages/Home.vue'
import Search from './pages/Search.vue'
import Space from './pages/Space.vue'
import Thread from './pages/Thread.vue'
import { spaces } from './data'

// Every sidebar space owns a path. The space name rides on `meta`, so no route
// takes a parameter.
const spaceRoutes: RouteRecordRaw[] = spaces.map((space) => ({
  path: `/spaces/${space.slug}`,
  name: space.name,
  component: Space,
  meta: { space: space.name },
}))

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: Home },
  { path: '/search', name: 'Search', component: Search },
  ...spaceRoutes,
  // The reader picks its discussion from `?d=`, so the path stays parameterless.
  { path: '/thread', name: 'Thread', component: Thread },
]

export default routes
