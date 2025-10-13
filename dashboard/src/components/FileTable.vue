<template>
  <div>
    <!-- デスクトップ: テーブル表示 (md以上) -->
    <div class="hidden md:block overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th
              scope="col"
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
              @click="$emit('sort', 'student_name')"
            >
              <div class="flex items-center">
                学生名
                <svg
                  v-if="sortColumn === 'student_name'"
                  class="ml-2 h-4 w-4"
                  :class="sortOrder === 'asc' ? 'transform rotate-180' : ''"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </th>

            <th
              scope="col"
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              学生ID
            </th>

            <th
              scope="col"
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              ファイル名
            </th>

            <th
              scope="col"
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
              @click="$emit('sort', 'submit_date')"
            >
              <div class="flex items-center">
                提出日時
                <svg
                  v-if="sortColumn === 'submit_date'"
                  class="ml-2 h-4 w-4"
                  :class="sortOrder === 'asc' ? 'transform rotate-180' : ''"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </th>

            <th
              scope="col"
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Driveリンク
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr
            v-for="file in files"
            :key="file.composite_key"
            class="hover:bg-gray-50 transition-colors"
          >
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
              {{ file.student_name }}
            </td>

            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
              {{ file.student_id }}
            </td>

            <td class="px-6 py-4 text-sm text-gray-700">
              <div class="max-w-md truncate" :title="file.filename">
                {{ file.filename }}
              </div>
            </td>

            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
              {{ formatDate(file.submit_date) }}
            </td>

            <td class="px-6 py-4 whitespace-nowrap text-sm">
              <button
                @click="$emit('open-drive', getDriveUrl(file.drive_file_id))"
                :disabled="!file.drive_file_id"
                class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                :title="file.drive_file_id ? 'Google Driveで開く' : 'リンクが無効です'"
              >
                <svg
                  class="mr-1.5 h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                  />
                </svg>
                Drive
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- モバイル: カード表示 (md未満) -->
    <div class="md:hidden space-y-4">
      <!-- ソートボタン（モバイル） -->
      <div class="flex gap-2 pb-4" role="group" aria-label="ソートオプション">
        <button
          @click="$emit('sort', 'student_name')"
          class="flex-1 inline-flex items-center justify-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          :aria-pressed="sortColumn === 'student_name'"
          :aria-label="`学生名順でソート${sortColumn === 'student_name' ? (sortOrder === 'asc' ? '（昇順）' : '（降順）') : ''}`"
        >
          学生名順
          <svg
            v-if="sortColumn === 'student_name'"
            class="ml-1.5 h-4 w-4"
            :class="sortOrder === 'asc' ? 'transform rotate-180' : ''"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
        <button
          @click="$emit('sort', 'submit_date')"
          class="flex-1 inline-flex items-center justify-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          :aria-pressed="sortColumn === 'submit_date'"
          :aria-label="`提出日時順でソート${sortColumn === 'submit_date' ? (sortOrder === 'asc' ? '（昇順）' : '（降順）') : ''}`"
        >
          提出日時順
          <svg
            v-if="sortColumn === 'submit_date'"
            class="ml-1.5 h-4 w-4"
            :class="sortOrder === 'asc' ? 'transform rotate-180' : ''"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
      </div>

      <!-- ファイルカード -->
      <div
        v-for="file in files"
        :key="file.composite_key"
        class="bg-white rounded-lg shadow-md p-4 space-y-3"
      >
        <!-- 学生名（大きく表示） -->
        <h3 class="text-lg font-bold text-gray-900">
          {{ file.student_name }}
        </h3>

        <!-- 学生ID -->
        <div class="flex items-center text-sm text-gray-600">
          <svg
            class="h-4 w-4 text-gray-400 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
            />
          </svg>
          <span>{{ file.student_id }}</span>
        </div>

        <!-- ファイル名 -->
        <div class="flex items-start text-sm text-gray-700">
          <svg
            class="h-4 w-4 text-gray-400 mr-2 mt-0.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
          <span class="break-words">{{ file.filename }}</span>
        </div>

        <!-- 提出日時 -->
        <div class="flex items-center text-sm text-gray-600">
          <svg
            class="h-4 w-4 text-gray-400 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{{ formatDate(file.submit_date) }}</span>
        </div>

        <!-- Driveリンクボタン -->
        <button
          @click="$emit('open-drive', getDriveUrl(file.drive_file_id))"
          :disabled="!file.drive_file_id"
          class="w-full inline-flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          :title="file.drive_file_id ? 'Google Driveで開く' : 'リンクが無効です'"
        >
          <svg
            class="mr-2 h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          Google Driveで開く
        </button>
      </div>
    </div>

    <!-- 空状態（フィルタリング後に0件の場合） -->
    <div
      v-if="files.length === 0"
      class="text-center py-12 bg-white rounded-lg"
    >
      <p class="text-sm text-gray-500">
        検索条件に一致するファイルがありません。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FileData, SortColumn, SortOrder } from '../types/models';

/**
 * FileTable Component
 * ファイル一覧をテーブル形式で表示
 */

interface Props {
  files: FileData[];
  sortColumn: SortColumn;
  sortOrder: SortOrder;
}

defineProps<Props>();

defineEmits<{
  sort: [column: SortColumn];
  'open-drive': [driveUrl: string];
}>();

/**
 * 日付文字列を読みやすい形式に変換
 * submit_dateは "YYYY/MM/DD HH:MM:SS" 形式で保存されている
 */
function formatDate(dateString: string): string {
  try {
    // すでにYYYY/MM/DD HH:MM:SS形式の場合はそのまま返す
    if (dateString.includes('/')) {
      return dateString;
    }
    // ISO 8601形式の場合は変換
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    const second = String(date.getSeconds()).padStart(2, '0');
    return `${year}/${month}/${day} ${hour}:${minute}:${second}`;
  } catch (error) {
    console.warn('Failed to format date:', dateString, error);
    return dateString;
  }
}

/**
 * drive_file_idからGoogle DriveのURLを生成
 * Firestoreには正規化されたdrive_file_idのみが保存されており、
 * フロントエンドで動的にURLを生成する
 */
function getDriveUrl(driveFileId: string): string {
  return `https://drive.google.com/file/d/${driveFileId}/view`;
}
</script>
