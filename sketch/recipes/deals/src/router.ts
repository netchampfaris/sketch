// The Runtime creates the router in hash mode. A Prototype exports routes only.
import Board from './pages/Board.vue'
import DealDetail from './pages/DealDetail.vue'
import DealList from './pages/DealList.vue'

export default [
  { path: '/', name: 'Board', component: Board },
  { path: '/list', name: 'List', component: DealList },
  {
    path: '/deals/:org',
    name: 'Deal',
    component: DealDetail,
    props: true,
  },
]
