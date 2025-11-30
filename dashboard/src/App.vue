<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Skip to main content link (キーボードナビゲーション用) -->
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-md focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
    >
      メインコンテンツへスキップ
    </a>

    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between">
          <router-link to="/" class="cursor-pointer">
            <h1 class="text-3xl font-bold text-gray-900 hover:text-gray-700 transition-colors">
              Carewell Dashboard
            </h1>
          </router-link>
          <div class="flex items-center space-x-4">
            <!-- 管理者モード: 同期ボタン -->
            <button
              v-if="isAdmin"
              @click="handleSync"
              :disabled="syncing"
              class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md transition-all duration-200 shadow-sm"
              :class="syncing
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-green-600 text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2'"
            >
              <!-- 同期中のスピナー -->
              <svg
                v-if="syncing"
                class="animate-spin -ml-1 mr-2 h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                />
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <!-- 同期アイコン -->
              <svg
                v-else
                class="-ml-1 mr-2 h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              {{ syncing ? '同期中...' : 'データ同期' }}
            </button>
            <nav class="flex space-x-4">
              <router-link
                to="/"
                class="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100"
                active-class="bg-gray-100 text-gray-900"
              >
                クラス一覧
              </router-link>
              <router-link
                to="/students"
                class="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-100"
                active-class="bg-gray-100 text-gray-900"
              >
                受講生一覧
              </router-link>
            </nav>
          </div>
        </div>
      </div>
    </header>

    <!-- 同期結果のトースト通知 -->
    <Transition
      enter-active-class="transform ease-out duration-300 transition"
      enter-from-class="translate-y-2 opacity-0 sm:translate-y-0 sm:translate-x-2"
      enter-to-class="translate-y-0 opacity-100 sm:translate-x-0"
      leave-active-class="transition ease-in duration-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="showToast"
        class="fixed top-4 right-4 z-50 max-w-sm w-full shadow-lg rounded-lg pointer-events-auto"
        :class="toastType === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'"
      >
        <div class="p-4">
          <div class="flex items-start">
            <!-- 成功アイコン -->
            <div
              v-if="toastType === 'success'"
              class="flex-shrink-0"
            >
              <svg class="h-6 w-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <!-- エラーアイコン -->
            <div
              v-else
              class="flex-shrink-0"
            >
              <svg class="h-6 w-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div class="ml-3 w-0 flex-1">
              <p
                class="text-sm font-medium"
                :class="toastType === 'success' ? 'text-green-800' : 'text-red-800'"
              >
                {{ toastTitle }}
              </p>
              <p
                class="mt-1 text-sm"
                :class="toastType === 'success' ? 'text-green-700' : 'text-red-700'"
              >
                {{ toastMessage }}
              </p>
            </div>
            <div class="ml-4 flex-shrink-0 flex">
              <button
                @click="showToast = false"
                class="rounded-md inline-flex text-gray-400 hover:text-gray-500 focus:outline-none"
              >
                <span class="sr-only">閉じる</span>
                <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <main id="main-content" aria-label="メインコンテンツ">
      <div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { ref, watch, onMounted } from 'vue'
import { useStudentSync } from './composables/useStudentSync'

const route = useRoute()

// 管理者モード
const isAdmin = ref(false)

// 同期機能
const { syncStudents, syncing } = useStudentSync()

// トースト通知の状態
const showToast = ref(false)
const toastType = ref<'success' | 'error'>('success')
const toastTitle = ref('')
const toastMessage = ref('')

/**
 * トースト通知を表示
 */
const showNotification = (type: 'success' | 'error', title: string, message: string) => {
  toastType.value = type
  toastTitle.value = title
  toastMessage.value = message
  showToast.value = true

  // 5秒後に自動で閉じる
  setTimeout(() => {
    showToast.value = false
  }, 5000)
}

/**
 * 同期ボタンのクリックハンドラ
 */
const handleSync = async () => {
  try {
    const result = await syncStudents({ backfill: true })

    if (result.status === 'success') {
      showNotification(
        'success',
        '同期完了',
        `受講生: ${result.students_synced}件同期、ファイル: ${result.files_backfilled || 0}件更新`
      )
    } else {
      showNotification('error', '同期エラー', result.error || '不明なエラーが発生しました')
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '同期に失敗しました'
    showNotification('error', '同期エラー', errorMessage)
  }
}

// グローバル管理者モード検出
const checkAdminMode = () => {
  if (route.query.admin === 'true') {
    sessionStorage.setItem('adminMode', 'true')
    isAdmin.value = true
    console.log('[App.vue] Admin mode activated via URL parameter')
  } else if (route.path === '/' && !route.query.admin) {
    // サイト内遷移かどうかを判定
    const isInternalNavigation = document.referrer &&
      document.referrer.startsWith(window.location.origin)

    if (!isInternalNavigation) {
      // 外部からの直接アクセスの場合のみクリア
      sessionStorage.removeItem('adminMode')
      isAdmin.value = false
      console.log('[App.vue] Admin mode cleared (external access to homepage)')
    } else {
      // 内部遷移の場合は sessionStorage から読み取り
      isAdmin.value = sessionStorage.getItem('adminMode') === 'true'
      console.log('[App.vue] Admin mode preserved (internal navigation)')
    }
  } else {
    // その他のページでは sessionStorage から読み取り
    isAdmin.value = sessionStorage.getItem('adminMode') === 'true'
  }
}

// 初期チェック
onMounted(() => {
  checkAdminMode()
})

// ルート変更を監視
watch(() => route.query.admin, () => {
  checkAdminMode()
})
</script>
