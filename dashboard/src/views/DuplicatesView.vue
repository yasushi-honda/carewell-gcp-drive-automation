<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- ページタイトル -->
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900">重複日介番号一覧</h1>
      <p class="mt-2 text-sm text-gray-600">
        Google Sheets内で同じ日介番号が複数のクラスに登場している受講生の一覧です。
        詳細を比較して、どちらを残すか判断してください。
      </p>
    </div>

    <!-- 対応方法の説明 -->
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <div class="flex">
        <svg class="h-5 w-5 text-blue-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-blue-800">重複の対応方法</h3>
          <div class="mt-2 text-sm text-blue-700">
            <ol class="list-decimal list-inside space-y-1">
              <li><strong>詳細を比較</strong>: カードをクリックして両方のデータを比較</li>
              <li><strong>正しいクラスを確認</strong>: 氏名・ふりがな・勤務先などから正しいクラスを判断</li>
              <li><strong>元データを編集</strong>: 削除したいクラスのリンクをクリック → 別タブでスプレッドシートが開く</li>
              <li><strong>L列にチェック</strong>: 該当行のL列「無効」チェックボックスをONにする</li>
              <li><strong>同期実行</strong>: ヘッダーの「データ同期」ボタンで変更を反映</li>
            </ol>
          </div>
        </div>
      </div>
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
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <svg v-else class="-ml-1 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {{ loading ? '読み込み中...' : '最新データを取得' }}
      </button>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading && !duplicates.length" class="space-y-4">
      <div v-for="i in 3" :key="i" class="bg-white shadow-sm rounded-lg p-4 animate-pulse">
        <div class="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
        <div class="h-4 bg-gray-200 rounded w-1/2"></div>
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

    <!-- 重複一覧 -->
    <div v-else class="space-y-4">
      <!-- サマリー -->
      <div class="bg-white shadow-sm rounded-lg px-4 py-3 border-b border-gray-200">
        <p class="text-sm text-gray-700">
          <span class="font-semibold text-red-600">{{ duplicates.length }}</span> 件の重複が見つかりました
          （<span class="text-green-600 font-medium">{{ resolvedCount }} 件対応済み</span>、
          <span class="text-yellow-600 font-medium">{{ pendingCount }} 件未対応</span>）
        </p>
      </div>

      <!-- 各重複カード -->
      <div
        v-for="(dup, index) in duplicates"
        :key="dup.student_id"
        class="bg-white shadow-sm rounded-lg overflow-hidden"
      >
        <!-- カードヘッダー -->
        <div
          class="px-4 py-3 border-b border-gray-200 flex items-center justify-between cursor-pointer hover:bg-gray-50"
          @click="toggleExpand(index)"
        >
          <div class="flex items-center space-x-4">
            <span class="text-sm font-medium text-gray-500">#{{ index + 1 }}</span>
            <span class="font-mono text-sm font-bold text-gray-900">{{ dup.student_id }}</span>
            <span
              v-if="hasInactive(dup)"
              class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
            >
              <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              対応済み
            </span>
            <span
              v-else
              class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"
            >
              <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              未対応
            </span>
          </div>
          <div class="flex items-center space-x-4">
            <div class="text-sm text-gray-500">
              <span class="font-medium">{{ dup.kept.class_name }}</span>
              と
              <span class="font-medium">{{ dup.ignored.class_name }}</span>
            </div>
            <svg
              class="h-5 w-5 text-gray-400 transition-transform"
              :class="{ 'rotate-180': expandedItems.includes(index) }"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        <!-- 展開された詳細 -->
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="max-h-0 opacity-0"
          enter-to-class="max-h-[1000px] opacity-100"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="max-h-[1000px] opacity-100"
          leave-to-class="max-h-0 opacity-0"
        >
          <div v-if="expandedItems.includes(index)" class="overflow-hidden">
            <!-- 比較テーブル -->
            <div class="px-4 py-4 bg-gray-50">
              <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr>
                      <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100">
                        項目
                      </th>
                      <th class="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider bg-blue-600">
                        {{ dup.kept.class_name }}
                        <span
                          v-if="dup.kept.status === 'inactive'"
                          class="ml-1 px-1 py-0.5 text-[10px] bg-blue-800 rounded"
                        >無効</span>
                        <a
                          v-if="classUrls[dup.kept.class_name]"
                          :href="classUrls[dup.kept.class_name]"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="ml-2 inline-flex items-center text-blue-200 hover:text-white"
                          @click.stop
                          title="スプレッドシートを開く"
                        >
                          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      </th>
                      <th class="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider bg-purple-600">
                        {{ dup.ignored.class_name }}
                        <span
                          v-if="dup.ignored.status === 'inactive'"
                          class="ml-1 px-1 py-0.5 text-[10px] bg-purple-800 rounded"
                        >無効</span>
                        <a
                          v-if="classUrls[dup.ignored.class_name]"
                          :href="classUrls[dup.ignored.class_name]"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="ml-2 inline-flex items-center text-purple-200 hover:text-white"
                          @click.stop
                          title="スプレッドシートを開く"
                        >
                          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      </th>
                      <th class="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100 w-16">
                        一致
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="field in comparisonFields" :key="field.key">
                      <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-700 bg-gray-50">
                        {{ field.label }}
                      </td>
                      <td
                        class="px-3 py-2 whitespace-nowrap text-sm"
                        :class="getValueClass(dup.kept[field.key], dup.ignored[field.key])"
                      >
                        {{ dup.kept[field.key] || '-' }}
                      </td>
                      <td
                        class="px-3 py-2 whitespace-nowrap text-sm"
                        :class="getValueClass(dup.kept[field.key], dup.ignored[field.key])"
                      >
                        {{ dup.ignored[field.key] || '-' }}
                      </td>
                      <td class="px-3 py-2 whitespace-nowrap text-center">
                        <span v-if="dup.kept[field.key] === dup.ignored[field.key]" class="text-green-500">
                          <svg class="h-4 w-4 inline" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                          </svg>
                        </span>
                        <span v-else class="text-orange-500 font-bold">
                          <svg class="h-4 w-4 inline" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                          </svg>
                        </span>
                      </td>
                    </tr>
                    <!-- ステータス行 -->
                    <tr class="bg-yellow-50">
                      <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-700">
                        ステータス（L列）
                      </td>
                      <td class="px-3 py-2 whitespace-nowrap text-sm">
                        <span
                          class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          :class="dup.kept.status === 'active' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-600 line-through'"
                        >
                          {{ dup.kept.status === 'active' ? '有効' : '無効' }}
                        </span>
                      </td>
                      <td class="px-3 py-2 whitespace-nowrap text-sm">
                        <span
                          class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          :class="dup.ignored.status === 'active' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-600 line-through'"
                        >
                          {{ dup.ignored.status === 'active' ? '有効' : '無効' }}
                        </span>
                      </td>
                      <td class="px-3 py-2 whitespace-nowrap text-center">
                        <span v-if="hasInactive(dup)" class="text-green-500">
                          <svg class="h-4 w-4 inline" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                          </svg>
                        </span>
                        <span v-else class="text-yellow-500 font-bold" title="どちらかをL列で無効化してください">!</span>
                      </td>
                    </tr>
                    <!-- 行番号 -->
                    <tr class="bg-gray-50">
                      <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-500">
                        行番号（参考）
                      </td>
                      <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">
                        {{ dup.kept.row }}行目
                      </td>
                      <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">
                        {{ dup.ignored.row }}行目
                      </td>
                      <td class="px-3 py-2"></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- アクションボタン -->
              <div class="mt-4 flex items-center justify-end space-x-3">
                <a
                  v-if="classUrls[dup.kept.class_name]"
                  :href="classUrls[dup.kept.class_name]"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center px-3 py-2 border border-blue-300 shadow-sm text-sm leading-4 font-medium rounded-md text-blue-700 bg-white hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  {{ dup.kept.class_name }} を編集
                </a>
                <a
                  v-if="classUrls[dup.ignored.class_name]"
                  :href="classUrls[dup.ignored.class_name]"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center px-3 py-2 border border-purple-300 shadow-sm text-sm leading-4 font-medium rounded-md text-purple-700 bg-white hover:bg-purple-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500"
                >
                  <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  {{ dup.ignored.class_name }} を編集
                </a>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- 凡例 -->
    <div v-if="duplicates.length" class="mt-6 bg-gray-50 rounded-lg p-4">
      <h4 class="text-sm font-medium text-gray-700 mb-3">凡例・用語説明</h4>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-600">
        <div>
          <h5 class="font-medium text-gray-700 mb-1">対応ステータス</h5>
          <ul class="space-y-1">
            <li class="flex items-center">
              <span class="inline-block px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-800 mr-2">対応済み</span>
              どちらかがL列で無効化されている
            </li>
            <li class="flex items-center">
              <span class="inline-block px-1.5 py-0.5 rounded text-xs bg-yellow-100 text-yellow-800 mr-2">未対応</span>
              両方とも有効 → どちらかを無効化する必要あり
            </li>
          </ul>
        </div>
        <div>
          <h5 class="font-medium text-gray-700 mb-1">データ比較</h5>
          <ul class="space-y-1">
            <li class="flex items-center">
              <svg class="h-4 w-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              両クラスで値が一致
            </li>
            <li class="flex items-center">
              <svg class="h-4 w-4 text-orange-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              値が異なる（黄色背景）→ 要確認
            </li>
            <li class="flex items-center">
              <svg class="h-4 w-4 text-gray-400 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              クリックで元スプレッドシートを開く
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'

interface StudentData {
  name: string
  furigana: string
  student_id: string
  company: string
  office: string
  service_type: string
  group: string
  serial_number: string
  student_number: string
  class_name: string
  status: string
  row: number
}

interface Duplicate {
  student_id: string
  kept: StudentData
  ignored: StudentData
  resolution: 'active_inactive' | 'first_occurrence'
}

const duplicates = ref<Duplicate[]>([])
const classUrls = ref<Record<string, string>>({})
const loading = ref(false)
const error = ref<string | null>(null)
const expandedItems = ref<number[]>([])

const CLOUD_RUN_URL = 'https://carewell-file-collector-imczapxkba-an.a.run.app'

const { getIdToken } = useAuth()

// 比較用フィールド定義
const comparisonFields = [
  { key: 'name', label: '氏名' },
  { key: 'furigana', label: 'ふりがな' },
  { key: 'company', label: '勤務先法人' },
  { key: 'office', label: '事業所' },
  { key: 'service_type', label: 'サービス種別' },
  { key: 'group', label: 'グループ' },
  { key: 'serial_number', label: '通し番号' },
  { key: 'student_number', label: '受講生番号' },
]

// どちらかが無効化されているか
const hasInactive = (dup: Duplicate) => {
  return dup.kept.status === 'inactive' || dup.ignored.status === 'inactive'
}

// 対応済み/未対応のカウント
const resolvedCount = computed(() =>
  duplicates.value.filter(d => hasInactive(d)).length
)
const pendingCount = computed(() =>
  duplicates.value.filter(d => !hasInactive(d)).length
)

// 値の比較に基づくクラス（異なる場合は黄色背景）
const getValueClass = (value1: string, value2: string) => {
  if (value1 !== value2) {
    return 'bg-yellow-50 text-gray-900 font-medium'
  }
  return 'text-gray-900'
}

// カードの展開/折りたたみ
const toggleExpand = (index: number) => {
  const idx = expandedItems.value.indexOf(index)
  if (idx === -1) {
    expandedItems.value.push(index)
  } else {
    expandedItems.value.splice(idx, 1)
  }
}

// データ取得
const fetchDuplicates = async () => {
  loading.value = true
  error.value = null

  try {
    const token = await getIdToken()
    if (!token) {
      throw new Error('管理者ログインが必要です')
    }

    const response = await fetch(`${CLOUD_RUN_URL}/admin/duplicate-students`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    })

    if (response.status === 401) {
      throw new Error('セッションが切れました。再ログインしてください')
    }
    if (response.status === 403) {
      throw new Error('管理者権限がありません')
    }
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()

    if (data.status === 'success') {
      duplicates.value = data.duplicates || []
      classUrls.value = data.class_urls || {}
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
