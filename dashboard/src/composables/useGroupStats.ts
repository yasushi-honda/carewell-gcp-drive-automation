// src/composables/useGroupStats.ts
// グループ統計（受講生数）と、その課題の提出状況の配分の取得

import { ref, computed, watch, onMounted, toValue, type MaybeRefOrGetter } from 'vue';
import { collection, query, where, getDocs } from 'firebase/firestore';
import { getDb } from '../config/firebase';
import { convertToShortClassName } from '../config/classes';
import { getDocuments } from './useFirestore';

/** グループ内の提出状況の配分（人数） */
export interface GroupSubmission {
  /** 提出済み（合格 + 採点待ち + 不合格） */
  submitted: number;
  notSubmitted: number;
  passed: number;
  pending: number;
  failed: number;
}

export interface GroupStat {
  group: string;
  studentCount: number;
  /** 提出状況が確定している場合のみ入る（取得中・失敗・突合不能のときは undefined） */
  submission?: GroupSubmission;
}

/**
 * 提出状況の取得状態
 * - loading: 取得中（バーの骨格を出す）
 * - ready: 集計済み
 * - error: 取得失敗（カードは残し、バーは出さない）
 * - mismatch: ファイルはあるのに、1人も受講生名簿と突合できなかった（配分を出さず警告）
 */
export type SubmissionState = 'loading' | 'ready' | 'error' | 'mismatch';

export type SubmissionStatus = 'passed' | 'pending' | 'failed';

/** 提出ファイル（Firestore の files ドキュメントのうち、集計に使う項目だけ） */
export interface SubmissionFile {
  student_id?: unknown;
  submit_date?: unknown;
  metadata?: { pass_status?: unknown } | null;
}

/** 集計に使う受講生（active のみ） */
export interface RosterStudent {
  student_id: string;
  group: string;
}

/** 同一秒で並んだ提出を決めるときの優先順位（大きいほど優先） */
const STATUS_RANK: Record<SubmissionStatus, number> = { passed: 2, pending: 1, failed: 0 };

/**
 * 合否表記を状態に分類する。
 * 完全一致（trim 後）で判定する。「不合格」は「合格」を含むため、部分一致は使わない。
 * 文字列以外・空・未知の値は「採点待ち」。
 */
export function classifyPassStatus(value: unknown): SubmissionStatus {
  if (typeof value !== 'string') return 'pending';
  const normalized = value.trim();
  if (normalized === '合格') return 'passed';
  if (normalized === '不合格') return 'failed';
  return 'pending';
}

/** 提出日時（"YYYY/MM/DD HH:mm:ss"）。文字列のまま比較できる。欠損・不正は最古扱い（空文字） */
export function submitDateKey(file: SubmissionFile): string {
  return typeof file.submit_date === 'string' ? file.submit_date.trim() : '';
}

/**
 * 同じ受講生の提出のうち、最新の提出の状態を「現在の状態」とする。
 * 提出日時が同一のときは 合格 ＞ 採点待ち ＞ 不合格 で決める。
 */
export function pickCurrentStatus(files: SubmissionFile[]): SubmissionStatus {
  let best: { key: string; status: SubmissionStatus } | null = null;
  for (const file of files) {
    const candidate = { key: submitDateKey(file), status: classifyPassStatus(file.metadata?.pass_status) };
    if (
      best === null ||
      candidate.key > best.key ||
      (candidate.key === best.key && STATUS_RANK[candidate.status] > STATUS_RANK[best.status])
    ) {
      best = candidate;
    }
  }
  return best ? best.status : 'pending';
}

export interface SubmissionSummary {
  byGroup: Map<string, GroupSubmission>;
  /** 提出ファイルに現れた受講生（日介番号のユニーク数） */
  submitters: number;
  /** そのうち active 名簿に存在しない人（集計に含まれない） */
  unmatchedSubmitters: number;
  /** 日介番号が取れない（空・欠損・文字列以外）ファイル数。誰の提出か分からないため集計に含まれない */
  unidentifiedFiles: number;
}

/**
 * 受講生（active）と提出ファイルを日介番号で突き合わせ、グループごとの配分を数える。
 * 名簿に無い日介番号の提出は集計から除外し、人数だけ返す。
 */
export function summarizeSubmissions(roster: RosterStudent[], files: SubmissionFile[]): SubmissionSummary {
  const filesByStudent = new Map<string, SubmissionFile[]>();
  let unidentifiedFiles = 0;
  for (const file of files) {
    const id = typeof file.student_id === 'string' ? file.student_id.trim() : '';
    if (!id) {
      unidentifiedFiles += 1;
      continue;
    }
    const list = filesByStudent.get(id);
    if (list) list.push(file);
    else filesByStudent.set(id, [file]);
  }

  const byGroup = new Map<string, GroupSubmission>();
  const rosterIds = new Set<string>();
  for (const student of roster) {
    rosterIds.add(student.student_id);
    let summary = byGroup.get(student.group);
    if (!summary) {
      summary = { submitted: 0, notSubmitted: 0, passed: 0, pending: 0, failed: 0 };
      byGroup.set(student.group, summary);
    }
    const submitted = filesByStudent.get(student.student_id);
    if (!submitted) {
      summary.notSubmitted += 1;
      continue;
    }
    summary.submitted += 1;
    summary[pickCurrentStatus(submitted)] += 1;
  }

  let unmatched = 0;
  for (const id of filesByStudent.keys()) {
    if (!rosterIds.has(id)) unmatched += 1;
  }

  return { byGroup, submitters: filesByStudent.size, unmatchedSubmitters: unmatched, unidentifiedFiles };
}

export function useGroupStats(className: MaybeRefOrGetter<string>, taskId: MaybeRefOrGetter<string>) {
  const baseStats = ref<{ group: string; studentCount: number }[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const submissionState = ref<SubmissionState>('loading');
  const submissionByGroup = ref<Map<string, GroupSubmission>>(new Map());
  const unmatchedSubmitters = ref(0);
  const unidentifiedFiles = ref(0);
  const submitters = ref(0);

  // active な受講生（提出状況の再取得に使う）
  let roster: RosterStudent[] = [];
  // 古い応答で新しい表示を上書きしないための世代番号
  let studentsGeneration = 0;
  let submissionsGeneration = 0;

  const groupStats = computed<GroupStat[]>(() =>
    baseStats.value.map((stat) => ({
      ...stat,
      submission: submissionState.value === 'ready' ? submissionByGroup.value.get(stat.group) : undefined,
    }))
  );

  /** 取得した提出ファイルを集計して状態に反映する */
  const applyFiles = (files: SubmissionFile[]) => {
    const summary = summarizeSubmissions(roster, files);
    unmatchedSubmitters.value = summary.unmatchedSubmitters;
    unidentifiedFiles.value = summary.unidentifiedFiles;
    submitters.value = summary.submitters;
    submissionByGroup.value = summary.byGroup;
    // ファイルはあるのに誰も名簿に紐付かない（日介番号が空・欠損、または全員が名簿外）場合は、
    // 「全員未提出」と誤表示せず警告に回す
    const matchedSubmitters = summary.submitters - summary.unmatchedSubmitters;
    submissionState.value = files.length > 0 && matchedSubmitters === 0 ? 'mismatch' : 'ready';
  };

  /** 提出ファイルを取得して反映する（初回の取得と再取得で共通）。失敗しても例外を投げず、状態に反映する */
  const loadSubmissions = async (generation: number, currentClassName: string, currentTaskId: string) => {
    submissionState.value = 'loading';
    let files: SubmissionFile[];
    try {
      files = await getDocuments<SubmissionFile>('submissions', currentClassName, 'tasks', currentTaskId, 'files');
    } catch (err) {
      if (generation !== submissionsGeneration) return;
      console.error('Error fetching submissions:', err);
      submissionState.value = 'error';
      return;
    }
    if (generation !== submissionsGeneration) return;
    applyFiles(files);
  };

  const fetchGroupStats = async () => {
    const currentClassName = toValue(className);
    const currentTaskId = toValue(taskId);
    const studentsGen = ++studentsGeneration;
    const submissionsGen = ++submissionsGeneration;

    loading.value = true;
    error.value = null;
    submissionState.value = 'loading';
    unmatchedSubmitters.value = 0;
    unidentifiedFiles.value = 0;
    submitters.value = 0;
    baseStats.value = [];
    roster = [];

    try {
      const db = getDb();

      // URLから来たクラス名（フルネーム）を短縮形に変換
      // 理由: students コレクションには短縮形（"No1"）で保存されているため
      const shortClassName = convertToShortClassName(currentClassName);

      // students コレクションから該当クラスの受講生を取得
      const q = query(
        collection(db, 'students'),
        where('class_name', '==', shortClassName),
        where('status', '==', 'active')
      );

      const snapshot = await getDocs(q);
      if (studentsGen !== studentsGeneration) return;

      // グループごとにカウント
      const groupCounts = new Map<string, number>();
      const nextRoster: RosterStudent[] = [];

      snapshot.docs.forEach((doc) => {
        const data = doc.data();
        const group = data.group || '未分類';
        groupCounts.set(group, (groupCounts.get(group) || 0) + 1);
        nextRoster.push({ student_id: doc.id, group });
      });
      roster = nextRoster;

      // Map を配列に変換してソート
      baseStats.value = Array.from(groupCounts.entries())
        .map(([group, count]) => ({
          group,
          studentCount: count
        }))
        .sort((a, b) => a.group.localeCompare(b.group, 'ja'));
    } catch (err) {
      if (studentsGen !== studentsGeneration) return;
      console.error('Error fetching group stats:', err);
      error.value = 'グループ統計の取得に失敗しました';
      // 提出状況は受講生（名簿）が無いと集計できないため、取得中のまま残さない
      submissionState.value = 'error';
      return;
    } finally {
      if (studentsGen === studentsGeneration) loading.value = false;
    }

    // 提出データは、受講生の取得が終わってから取り始める（カードを先に出し、バーは後から埋める）。
    // 同時に取り始めると、同じ回線を分け合ってカードの表示まで遅れる（本番実測で約+130ms、
    // 全員提出で約630KBになると約+3秒の見込み）。
    await loadSubmissions(submissionsGen, currentClassName, currentTaskId);
  };

  /** 提出状況だけを取り直す（受講生の再取得はしない） */
  const refetchSubmissions = async () => {
    // 受講生の取得中・失敗後は名簿が無く、空の名簿で集計してしまうため何もしない（全体の再取得を使う）
    if (loading.value || roster.length === 0) return;
    const generation = ++submissionsGeneration;
    await loadSubmissions(generation, toValue(className), toValue(taskId));
  };

  onMounted(() => {
    fetchGroupStats();
  });

  // 同じルートのまま className / taskId だけが変わったとき（戻る・進む）に再取得する
  watch([() => toValue(className), () => toValue(taskId)], () => {
    fetchGroupStats();
  });

  return {
    groupStats,
    loading,
    error,
    refetch: fetchGroupStats,
    submissionState,
    unmatchedSubmitters,
    unidentifiedFiles,
    submitters,
    refetchSubmissions,
  };
}
