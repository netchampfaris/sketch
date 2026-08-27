// The Runtime creates the router in hash mode. A Prototype exports routes only.
import type { RouteRecordRaw } from 'vue-router'
import Issues from './pages/Issues.vue'
import About from './pages/About.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Issues', component: Issues },
  { path: '/about', name: 'About', component: About },
]

export default routes
