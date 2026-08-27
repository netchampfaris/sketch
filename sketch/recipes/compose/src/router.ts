// The Runtime creates the router in hash mode. A Prototype exports routes only.
import type { RouteRecordRaw } from 'vue-router'
import Compose from './pages/Compose.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Compose', component: Compose },
]

export default routes
