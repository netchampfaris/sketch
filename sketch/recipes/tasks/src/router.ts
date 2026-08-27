// The Runtime creates the router in hash mode. A Prototype exports routes only.
import type { RouteRecordRaw } from 'vue-router'
import TaskList from './pages/TaskList.vue'
import TaskDetailPage from './pages/TaskDetailPage.vue'

// The list and the detail are two routes with the task id as a parameter.
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Tasks', component: TaskList },
  {
    path: '/task/:id',
    name: 'Task',
    component: TaskDetailPage,
    props: true,
  },
]

export default routes
