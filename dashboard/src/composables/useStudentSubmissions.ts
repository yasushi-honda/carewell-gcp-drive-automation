// src/composables/useStudentSubmissions.ts
// 課題ごとの「受講生ごとの提出状況」の取得（受講生一覧で、誰が提出済みかを一目で分かるようにする）

import { ref, watch, onMounted, toValue, type MaybeRefOrGetter } from 'vue';
import { getDocuments } from './useFirestore';
import {
  pickCurrentStatus,
  submitDateKey,
  type SubmissionFile,
  type SubmissionStatus,
} from './useGroupStats';

/** 受講生1人の、その課題での提出状況（提出ファイルがある受講生のみ） */
export interface StudentSubmission {
  /** 最新の提出の状態（同一秒は 合格 ＞ 採点待ち ＞ 不合格） */
  status: SubmissionStatus;
  /** 最新の提出日時（"YYYY/MM/DD HH:mm:ss"）。欠損・不正のときは空文字 */
  latestSubmitDate: string;
  /** 提出ファイル数（再提出を含む） */
  fileCount: number;
}

/** 一覧に出す状態。提出ファイルが無い受講生は「未提出」 */
export type StudentStatus = SubmissionStatus | 'not_submitted';

/**
 * 取得状態
 * - loading: 取得中
 * - ready: 取得済み
 * - error: 取得失敗（「全員未提出」と区別するため、状態は出さない）
 */
export type StudentSubmissionsState = 'loading' | 'ready' | 'error';

/** 提出ファイルを日介番号ごとにまとめ、受講生ごとの現在の状態を求める。日介番号が取れないファイルは数だけ返す */
export function summarizeByStudent(files: SubmissionFile[]): {
  byStudent: Map<string, StudentSubmission>;
  unidentifiedFiles: number;
} {
  const grouped = new Map<string, SubmissionFile[]>();
  let unidentifiedFiles = 0;
  for (const file of files) {
    const id = typeof file.student_id === 'string' ? file.student_id.trim() : '';
    if (!id) {
      unidentifiedFiles += 1;
      continue;
    }
    const list = grouped.get(id);
    if (list) list.push(file);
    else grouped.set(id, [file]);
  }

  const byStudent = new Map<string, StudentSubmission>();
  for (const [id, list] of grouped) {
    // 文字列のまま比較できる形式のため、辞書順の最大が最新
    const latestSubmitDate = list.map(submitDateKey).reduce((a, b) => (b > a ? b : a), '');
    byStudent.set(id, { status: pickCurrentStatus(list), latestSubmitDate, fileCount: list.length });
  }
  return { byStudent, unidentifiedFiles };
}

/** 受講生の一覧表示用の状態。提出が無ければ「未提出」 */
export function statusOf(byStudent: Map<string, StudentSubmission>, studentId: string): StudentStatus {
  return byStudent.get(studentId)?.status ?? 'not_submitted';
}

export function useStudentSubmissions(className: MaybeRefOrGetter<string>, taskId: MaybeRefOrGetter<string>) {
  const state = ref<StudentSubmissionsState>('loading');
  const byStudent = ref<Map<string, StudentSubmission>>(new Map());
  /** 提出ファイルの総数（受講生名簿と突き合わせて、日介番号の食い違いを検出するために使う） */
  const fileCount = ref(0);
  const unidentifiedFiles = ref(0);

  // 古い応答で新しい表示を上書きしない（className / taskId の切替・再取得の競合）
  let generation = 0;

  const load = async () => {
    const current = ++generation;
    state.value = 'loading';
    let files: SubmissionFile[];
    try {
      files = await getDocuments<SubmissionFile>(
        'submissions',
        toValue(className),
        'tasks',
        toValue(taskId),
        'files'
      );
    } catch (err) {
      if (current !== generation) return;
      console.error('Error fetching student submissions:', err);
      state.value = 'error';
      return;
    }
    if (current !== generation) return;
    const summary = summarizeByStudent(files);
    byStudent.value = summary.byStudent;
    unidentifiedFiles.value = summary.unidentifiedFiles;
    fileCount.value = files.length;
    state.value = 'ready';
  };

  onMounted(load);
  watch([() => toValue(className), () => toValue(taskId)], load);

  return { state, byStudent, fileCount, unidentifiedFiles, refetch: load };
}
