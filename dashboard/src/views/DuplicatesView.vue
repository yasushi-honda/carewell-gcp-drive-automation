<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- ページタイトル -->
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900">重複日介番号一覧</h1>
      <p class="mt-2 text-sm text-gray-600">
        Google Sheets内で同じ日介番号が複数回登場している受講生の一覧です。
        「無効化すべきクラス」列に表示されているクラスのL列「無効」チェックボックスをONにすると、
        正しいクラスのデータのみが同期されます。
      </p>
    </div>

    <!-- 更新ボタン -->
    <div class="mb-4">
      <button
        @click="fetchDuplicates"
        :disabled="loading"
        class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md transition-all duration-200 shadow-sm"
        :class="loading
          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : 'bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'"
      >
        <svg
          v-if="loading"
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
        {{ loading ? '読み込み中...' : '最新データを取得' }}
      </button>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading && !duplicates.length" class="space-y-4">
      <div v-for="i in 5" :key="i" class="bg-white shadow-sm rounded-lg p-4 animate-pulse">
        <div class="h-4 bg-gray-200 rounded w-3/4"></div>
      </div>
    </div>

    <!-- エラー状態 -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4">
      <div class="flex">
        <svg class="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">エラーが発生しました</h3>
          <p class="mt-1 text-sm text-red-700">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- 重複なし -->
    <div v-else-if="!duplicates.length" class="bg-green-50 border border-green-200 rounded-lg p-4">
      <div class="flex">
        <svg class="h-5 w-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-green-800">重複なし</h3>
          <p class="mt-1 text-sm text-green-700">重複している日介番号はありません。</p>
        </div>
      </div>
    </div>

    <!-- 重複一覧テーブル -->
    <div v-else class="bg-white shadow-sm rounded-lg overflow-hidden">
      <!-- テーブルヘッダー -->
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <p class="text-sm text-gray-700">
          <span class="font-semibold text-red-600">{{ duplicates.length }}</span> 件の重複が見つかりました
        </p>
      </div>

      <!-- テーブル本体 -->
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                #
              </th>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                日介番号
              </th>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                氏名
              </th>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                有効なクラス
              </th>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                無効化すべきクラス
              </th>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                解決方法
              </th>
              <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                対応状況
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="(dup, index) in duplicates" :key="dup.student_id" class="hover:bg-gray-50">
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                {{ index + 1 }}
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span class="font-mono text-sm font-medium text-gray-900">{{ dup.student_id }}</span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                {{ dup.name }}
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  {{ dup.kept_class }}
                </span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                  {{ dup.ignored_class }}
                </span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                <span v-if="dup.resolution === 'active_inactive'" class="text-green-600">
                  L列で解決済み
                </span>
                <span v-else class="text-yellow-600">
                  先着順（要確認）
                </span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span
                  v-if="dup.ignored_status === 'inactive'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
                >
                  <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                  </svg>
                  無効化済み
                </span>
                <span
                  v-else
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"
                >
                  <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                  </svg>
                  要対応
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 凡例 -->
      <div class="px-4 py-3 border-t border-gray-200 bg-gray-50">
        <h4 class="text-sm font-medium text-gray-700 mb-2">凡例</h4>
        <div class="flex flex-wrap gap-4 text-xs text-gray-600">
          <div class="flex items-center">
            <span class="inline-block w-3 h-3 bg-green-100 rounded-full mr-1"></span>
            有効なクラス: 同期されるデータ
          </div>
          <div class="flex items-center">
            <span class="inline-block w-3 h-3 bg-red-100 rounded-full mr-1"></span>
            無効化すべきクラス: Google Sheets L列で無効化推奨
          </div>
          <div class="flex items-center">
            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-800 mr-1">無効化済み</span>
            L列で無効化対応済み
          </div>
          <div class="flex items-center">
            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-yellow-100 text-yellow-800 mr-1">要対応</span>
            L列での無効化が必要
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Duplicate {
  student_id: string
  name: string
  kept_class: string
  kept_status: string
  ignored_class: string
  ignored_status: string
  resolution: 'active_inactive' | 'first_occurrence'
}

const duplicates = ref<Duplicate[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const CLOUD_RUN_URL = 'https://carewell-file-collector-imczapxkba-an.a.run.app'

const fetchDuplicates = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await fetch(`${CLOUD_RUN_URL}/admin/duplicate-students`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()

    if (data.status === 'success') {
      duplicates.value = data.duplicates || []
    } else {
      throw new Error(data.error || 'Unknown error')
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '重複情報の取得に失敗しました'
    console.error('Error fetching duplicates:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDuplicates()
})
</script>
