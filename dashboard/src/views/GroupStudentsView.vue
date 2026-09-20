<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- パンくずリスト -->
    <Breadcrumb
      :items="[
        { label: 'ホーム', to: '/' },
        { label: className, to: `/class/${className}` },
        { label: taskId, to: `/class/${className}/task/${taskId}` },
        { label: 'グループ一覧', to: `/class/${className}/task/${taskId}/groups` },
        { label: `${groupName}グループ` }
      ]"
    />

    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-2 mt-6">
      {{ groupName }} グループの受講生一覧
    </h1>
    <p class="text-gray-600 mb-6">{{ className }} - {{ taskId }} の提出状況</p>

    <!-- 検索ボックス -->
    <div class="bg-white shadow-sm rounded-lg p-4 mb-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="search-query" class="block text-sm font-medium text-gray-700 mb-1">
            検索
          </label>
          <input
            id="search-query"
            v-model="searchQuery"
            type="text"
            placeholder="氏名・ふりがな・日介番号で検索"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3 border min-h-11 lg:min-h-0"
          />
        </div>
      </div>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading" class="space-y-4">
      <LoadingSkeleton v-for="i in 5" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert v-else-if="error" :message="error" />

    <!-- 受講生一覧テーブル -->
    <div v-else>
    <!-- 提出状況の取得失敗（一覧は残す）。「全員未提出」とは区別する -->
    <div
      v-if="submissionState === 'error'"
      role="alert"
      class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
    >
      <p>提出状況を取得できませんでした。受講生のみ表示しています。</p>
      <button
        type="button"
        class="inline-flex min-h-11 items-center rounded-md border border-amber-400 bg-white px-4 font-medium text-amber-900 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
        @click="refetchSubmissions"
      >
        再取得
      </button>
    </div>

    <!-- 提出ファイルはあるのに、誰も受講生名簿と一致しない（状態は出さない） -->
    <div
      v-else-if="submissionState === 'mismatch'"
      role="alert"
      class="mb-4 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
    >
      提出データと受講生名簿が一致しなかったため、提出状況を表示できません。提出データの日介番号が空、または受講生名簿と食い違っている可能性があります。
    </div>

    <!-- 取得中: チップと同じ高さの骨格を出し、届いたときに一覧が動かないようにする -->
    <div
      v-else-if="submissionState === 'loading'"
      class="mb-4 h-11 w-2/3 max-w-md animate-pulse rounded-full bg-gray-200 lg:h-8"
      aria-hidden="true"
      data-testid="chips-skeleton"
    ></div>

    <!-- 提出状況の集計（押すと、その状態の受講生だけに絞り込む） -->
    <div v-else-if="submissionState === 'ready'" class="mb-4">
      <ul class="flex flex-wrap gap-2" aria-label="提出状況で絞り込み">
        <li v-for="chip in statusChips" :key="chip.key">
          <button
            type="button"
            class="inline-flex min-h-11 items-center gap-1.5 rounded-full border px-4 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 lg:min-h-0 lg:py-1.5"
            :class="
              statusFilter === chip.key
                ? 'border-blue-600 bg-blue-600 text-white'
                : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
            "
            :aria-pressed="statusFilter === chip.key"
            :data-chip="chip.key"
            @click="statusFilter = chip.key"
          >
            {{ chip.label }}
            <span class="font-semibold">{{ chip.count }}</span>
          </button>
        </li>
      </ul>
      <p v-if="unidentifiedFiles > 0" role="status" class="mt-2 text-sm font-medium text-amber-800">
        日介番号が空の提出ファイルが {{ unidentifiedFiles }} 件あります（該当する受講生は「未提出」と表示されます）。
      </p>
    </div>

    <div class="bg-white shadow-sm rounded-lg overflow-hidden">
      <!-- テーブルヘッダー -->
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <p class="text-sm text-gray-700">
          {{ filteredAndSortedStudents.length }} 人の受講生が見つかりました
        </p>
      </div>

      <!-- 1024px未満（表は最小幅が約812px）: カードリスト -->
      <template v-if="isCompact">
        <SortOptions :options="sortOptions" @toggle="onSortToggle" />
        <StudentCardList
          :students="filteredAndSortedStudents"
          :submission-state="submissionState"
          :submissions="byStudent"
        />
      </template>

      <!-- 広い画面: テーブル本体（従来どおり） -->
      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
                @click="toggleSortStudentNumber"
              >
                <div class="flex items-center gap-2">
                  <span>受講者番号</span>
                  <span class="text-xs" v-if="sortBy === 'student_number' && sortOrder === 'asc'">▲</span>
                  <span class="text-xs" v-else-if="sortBy === 'student_number' && sortOrder === 'desc'">▼</span>
                  <span class="text-xs text-gray-300" v-else>⇅</span>
                </div>
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                日介番号
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                氏名
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
                @click="toggleSortFurigana"
              >
                <div class="flex items-center gap-2">
                  <span>ふりがな</span>
                  <span class="text-xs" v-if="sortBy === 'furigana' && sortOrder === 'asc'">▲</span>
                  <span class="text-xs" v-else-if="sortBy === 'furigana' && sortOrder === 'desc'">▼</span>
                  <span class="text-xs text-gray-300" v-else>⇅</span>
                </div>
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                サービス種別
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                提出状況
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="student in filteredAndSortedStudents"
              :key="student.student_id"
              class="cursor-pointer transition-colors"
              :class="student.status === 'withdrawn' ? 'bg-gray-100 hover:bg-gray-200 opacity-60' : 'hover:bg-gray-50'"
              @click="navigateToDetail(student.student_id)"
            >
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ student.student_number || '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <router-link
                  :to="`/students/${student.student_id}`"
                  class="text-blue-600 hover:text-blue-800 font-medium"
                  @click.stop
                >
                  {{ student.student_id }}
                </router-link>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ student.name }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ student.furigana }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ student.service_type }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <StudentSubmissionCell :state="submissionState" :submission="byStudent.get(student.student_id)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 空状態（カード・テーブル共通） -->
      <div v-if="filteredAndSortedStudents.length === 0" class="px-6 py-12 text-center">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        <p class="mt-2 text-sm text-gray-500">該当する受講生が見つかりませんでした</p>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStudents } from '../composables/useStudents';
import { useStudentSubmissions, statusOf, type StudentStatus } from '../composables/useStudentSubmissions';
import { convertToShortClassName } from '../config/classes';
import Breadcrumb from '../components/Breadcrumb.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';
import StudentCardList from '../components/StudentCardList.vue';
import SortOptions from '../components/SortOptions.vue';
import StudentSubmissionCell from '../components/StudentSubmissionCell.vue';
import { useMediaQuery, BELOW_LG } from '../composables/useMediaQuery';

const route = useRoute();
const router = useRouter();

const className = route.params.className as string;
const taskId = route.params.taskId as string;
const groupName = route.params.groupName as string;

const searchQuery = ref('');
const statusFilter = ref<'all' | StudentStatus>('all');
const sortBy = ref<'furigana' | 'student_number' | null>(null);
const sortOrder = ref<'asc' | 'desc' | null>(null);

// URLから来たクラス名（フルネーム）を短縮形に変換
const shortClassName = convertToShortClassName(className);

const { students, loading, error } = useStudents();

// この課題の提出状況（受講生一覧の取得とは別に取り、届くまでは骨格を出す）
const {
  state: submissionsState,
  byStudent,
  fileCount,
  unidentifiedFiles,
  refetch: refetchSubmissions,
} = useStudentSubmissions(className, taskId);

// 表は最小幅が約812pxのため、1024px未満ではカード表示にする
const isCompact = useMediaQuery(BELOW_LG);

// このクラスの受講生（無効な受講生を除く）
const classStudents = computed(() =>
  students.value.filter((student) => student.status !== 'inactive' && student.class_name === shortClassName)
);

// 提出ファイルはあるのに、このクラスの誰とも日介番号が一致しない場合は、「全員未提出」と誤表示せず警告に回す
const submissionState = computed<'loading' | 'ready' | 'error' | 'mismatch'>(() => {
  if (submissionsState.value !== 'ready') return submissionsState.value;
  const anyMatched = classStudents.value.some((student) => byStudent.value.has(student.student_id));
  return fileCount.value > 0 && !anyMatched ? 'mismatch' : 'ready';
});

// グループの受講生（提出状況・検索での絞り込み前）
const groupStudents = computed(() => classStudents.value.filter((student) => student.group === groupName));

// 提出状況の集計チップ（グループの全員に対する人数）
const statusChips = computed(() => {
  const counts: Record<StudentStatus, number> = { not_submitted: 0, passed: 0, pending: 0, failed: 0 };
  for (const student of groupStudents.value) counts[statusOf(byStudent.value, student.student_id)] += 1;
  return [
    { key: 'all' as const, label: '全員', count: groupStudents.value.length },
    { key: 'not_submitted' as const, label: '未提出', count: counts.not_submitted },
    { key: 'passed' as const, label: '合格', count: counts.passed },
    { key: 'pending' as const, label: '採点待ち', count: counts.pending },
    { key: 'failed' as const, label: '不合格', count: counts.failed },
  ];
});

// フィルタリング（提出状況、検索クエリ）
const filteredStudents = computed(() => {
  return groupStudents.value.filter((student) => {
    if (statusFilter.value !== 'all' && statusOf(byStudent.value, student.student_id) !== statusFilter.value) {
      return false;
    }

    // 検索クエリ（氏名、ふりがな、日介番号で検索）
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase();
      const matchName = student.name.toLowerCase().includes(query);
      const matchFurigana = student.furigana.toLowerCase().includes(query);
      const matchStudentId = student.student_id.toLowerCase().includes(query);
      return matchName || matchFurigana || matchStudentId;
    }

    return true;
  });
});

// ソート機能
const toggleSortFurigana = () => {
  if (sortBy.value === 'furigana') {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortBy.value = 'furigana';
    sortOrder.value = 'asc';
  }
};

const toggleSortStudentNumber = () => {
  if (sortBy.value === 'student_number') {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortBy.value = 'student_number';
    sortOrder.value = 'asc';
  }
};

// フィルタ + ソート
const filteredAndSortedStudents = computed(() => {
  let result = [...filteredStudents.value];

  if (sortBy.value === 'furigana' && sortOrder.value) {
    result.sort((a, b) => {
      const comparison = a.furigana.localeCompare(b.furigana, 'ja');
      return sortOrder.value === 'asc' ? comparison : -comparison;
    });
  } else if (sortBy.value === 'student_number' && sortOrder.value) {
    result.sort((a, b) => {
      const comparison = (a.student_number || '').localeCompare(b.student_number || '', 'ja', { numeric: true });
      return sortOrder.value === 'asc' ? comparison : -comparison;
    });
  }

  return result;
});

// カード表示用の並べ替えボタン（テーブルの見出しクリックと同じ状態遷移: 昇順 ⇄ 降順）
const sortOptions = computed(() => [
  { key: 'furigana', label: 'ふりがな', order: sortBy.value === 'furigana' ? sortOrder.value : null },
  { key: 'student_number', label: '受講者番号', order: sortBy.value === 'student_number' ? sortOrder.value : null },
]);

const onSortToggle = (key: string) => {
  if (key === 'student_number') {
    toggleSortStudentNumber();
  } else {
    toggleSortFurigana();
  }
};

const navigateToDetail = (studentId: string) => {
  router.push(`/students/${studentId}`);
};
</script>
