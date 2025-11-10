// src/config/classes.ts
// Known class list configuration

/**
 * 既知のクラス名リスト
 *
 * Note: Firestore Admin SDKの`listCollections()`は通常のFirebase SDKでは使用不可のため、
 * クラス名リストをフロントエンドで管理する。
 *
 * 新しいクラスを追加する場合は、このリストに追加する。
 * Phase 2では、Firestoreに`/metadata/classes`ドキュメントを追加して動的管理することも検討。
 */
export const KNOWN_CLASSES = [
  '令和7年度 デジタル中核人材養成研修 №01',
  '令和7年度 デジタル中核人材養成研修 №02',
  '令和7年度 デジタル中核人材養成研修 №03',
  '令和7年度 デジタル中核人材養成研修 №04',
  '令和7年度 デジタル中核人材養成研修 №05',
  '令和7年度 デジタル中核人材養成研修 №08',
  '令和7年度 デジタル中核人材養成研修 №09',
];

/**
 * 既知のタスクIDリスト
 *
 * Note: Firestoreではサブコレクション（documents）にデータがあっても、
 * 親ドキュメント（task_id）自体は自動作成されないため、
 * task_idリストをフロントエンドで管理する。
 *
 * Cloud Schedulerで管理されている課題IDに対応。
 */
export const KNOWN_TASK_IDS = ['課題①', '課題②'];

/**
 * クラス名マッピングテーブル
 *
 * Background:
 * - submissions コレクション: フルネーム形式 (例: "令和7年度 デジタル中核人材養成研修 №01")
 * - students コレクション: 短縮形式 (例: "No1")
 *
 * URLから取得するクラス名（フルネーム）をstudentsコレクションのclass_name（短縮形）に
 * 変換するために使用する。
 */
export const CLASS_NAME_MAPPING: Record<string, string> = {
  '令和7年度 デジタル中核人材養成研修 №01': 'No1',
  '令和7年度 デジタル中核人材養成研修 №02': 'No2',
  '令和7年度 デジタル中核人材養成研修 №03': 'No3',
  '令和7年度 デジタル中核人材養成研修 №04': 'No4',
  '令和7年度 デジタル中核人材養成研修 №05': 'No5',
  '令和7年度 デジタル中核人材養成研修 №08': 'No8',
  '令和7年度 デジタル中核人材養成研修 №09': 'No9',
};

/**
 * フルネーム形式のクラス名を短縮形に変換
 *
 * @param fullClassName - フルネーム形式のクラス名 (例: "令和7年度 デジタル中核人材養成研修 №01")
 * @returns 短縮形のクラス名 (例: "No1")、マッピングが存在しない場合は元の値を返す
 */
export function convertToShortClassName(fullClassName: string): string {
  return CLASS_NAME_MAPPING[fullClassName] || fullClassName;
}

/**
 * 短縮形のクラス名をフルネーム形式に変換（逆マッピング）
 *
 * @param shortClassName - 短縮形のクラス名 (例: "No1")
 * @returns フルネーム形式のクラス名 (例: "令和7年度 デジタル中核人材養成研修 №01")、マッピングが存在しない場合は元の値を返す
 */
export function convertToFullClassName(shortClassName: string): string {
  const entry = Object.entries(CLASS_NAME_MAPPING).find(([_, short]) => short === shortClassName);
  return entry ? entry[0] : shortClassName;
}
