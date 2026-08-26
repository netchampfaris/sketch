import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory('/sketch'),
  routes: [
    { path: '/', name: 'Home', component: () => import('./pages/HomeScreen.vue') },
  ],
})
