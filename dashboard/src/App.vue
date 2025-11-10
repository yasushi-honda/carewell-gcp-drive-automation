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
          <h1 class="text-3xl font-bold text-gray-900">
            Carewell Dashboard
          </h1>
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
import { RouterView } from 'vue-router'
</script>
