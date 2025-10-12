import { createRouter, createWebHistory } from 'vue-router'
import ClassListView from '../views/ClassListView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: ClassListView,
    },
    {
      path: '/class/:className',
      name: 'tasks',
      component: () => import('../views/TaskListView.vue'),
      props: true,
    },
    {
      path: '/class/:className/task/:taskId',
      name: 'files',
      component: () => import('../views/FileListView.vue'),
      props: true,
    },
  ],
})

export default router
