<template>
  <div class="overflow-x-auto">
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

    <!-- 空状態（フィルタリング後に0件の場合） -->
    <div
      v-if="files.length === 0"
      class="text-center py-12 bg-white"
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
