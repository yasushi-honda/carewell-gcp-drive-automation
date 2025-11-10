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
    </header>

    <main id="main-content" aria-label="メインコンテンツ">
      <div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { watch, onMounted } from 'vue'

const route = useRoute()

// グローバル管理者モード検出
const checkAdminMode = () => {
  if (route.query.admin === 'true') {
    sessionStorage.setItem('adminMode', 'true')
    console.log('[App.vue] Admin mode activated via URL parameter')
  } else if (route.path === '/' && !route.query.admin) {
    // サイト内遷移かどうかを判定
    const isInternalNavigation = document.referrer &&
      document.referrer.startsWith(window.location.origin)

    if (!isInternalNavigation) {
      // 外部からの直接アクセスの場合のみクリア
      sessionStorage.removeItem('adminMode')
      console.log('[App.vue] Admin mode cleared (external access to homepage)')
    } else {
      console.log('[App.vue] Admin mode preserved (internal navigation)')
    }
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
