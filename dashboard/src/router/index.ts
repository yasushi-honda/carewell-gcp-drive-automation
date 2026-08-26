import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'

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
    {
      path: '/class/:className/task/:taskId/groups',
      name: 'GroupList',
      component: () => import('../views/GroupListView.vue'),
    },
    {
      path: '/class/:className/task/:taskId/group/:groupName/students',
      name: 'GroupStudents',
      component: () => import('../views/GroupStudentsView.vue'),
    },
    {
      path: '/admin/duplicates',
      name: 'duplicates',
      component: () => import('../views/DuplicatesView.vue'),
      meta: { requiresAdmin: true },
    },
  ],
})

// 管理者専用ルートのガード（多層防御。本質的な保護はバックエンド/Firestoreルール側）
router.beforeEach(async (to) => {
  if (!to.meta.requiresAdmin) return true
  const { isAdmin, waitUntilReady } = useAuth()
  await waitUntilReady()
  return isAdmin.value ? true : { path: '/' }
})

export default router
