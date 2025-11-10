import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/ClassListView.vue'),
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
    {
      path: '/students',
      name: 'students',
      component: () => import('../views/StudentsView.vue'),
    },
    {
      path: '/students/:id',
      name: 'student-detail',
      component: () => import('../views/StudentDetailView.vue'),
      props: true,
    },
  ],
})

export default router
