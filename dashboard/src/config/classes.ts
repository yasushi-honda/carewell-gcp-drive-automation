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
