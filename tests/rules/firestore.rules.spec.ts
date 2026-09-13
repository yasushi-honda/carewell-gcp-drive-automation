// Firestore Security Rules のユニットテスト（Issue #12）
//
// 公式推奨のv9 modular API（initializeTestEnvironment + authenticatedContext /
// unauthenticatedContext）を使用する。legacyのinitializeTestAppは使わない。
//
// 注意: @firebase/rules-unit-testing の context.firestore() は名前付きDB
// （本番のcarewell-native）ではなくエミュレータのデフォルトDBを使う。ルール本文は
// 同一のためルールロジックの検証としては有効だが、DB名そのものの検証はしていない。

import { describe, it, beforeAll, afterAll, beforeEach } from 'vitest';
import {
  initializeTestEnvironment,
  assertSucceeds,
  assertFails,
  type RulesTestEnvironment,
} from '@firebase/rules-unit-testing';
import {
  doc,
  getDoc,
  getDocs,
  collection,
  collectionGroup,
  query,
  where,
  setDoc,
  updateDoc,
  deleteDoc,
  initializeFirestore,
} from 'firebase/firestore';
import { initializeApp, deleteApp } from 'firebase/app';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RULES_PATH = resolve(__dirname, '../../dashboard/firestore.rules');

const PROJECT_ID = 'demo-carewell-rules-test';
const ADMIN_EMAIL = 'admin@example.com';
const NON_ADMIN_EMAIL = 'nobody@example.com';

let testEnv: RulesTestEnvironment;

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: {
      rules: readFileSync(RULES_PATH, 'utf8'),
      host: 'localhost',
      port: 8080,
    },
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
});

async function seedAdmin(email: string) {
  await testEnv.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'admins', email), { added_by: 'test' });
  });
}

async function seedStudent(id: string, data: Record<string, unknown>) {
  await testEnv.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'students', id), data);
  });
}

// collectionGroupの回帰テストは、RulesTestContextのcompat Firestoreを追加生成せずに
// Emulatorのownerトークンでシードする。withSecurityRulesDisabled()と同じ権限で、
// compatラッパーの初期化状態との干渉を避ける。
async function seedCollectionGroupFile(
  path: string,
  data: { filename: string; student_id: string }
) {
  const response = await fetch(
    `http://localhost:8080/v1/projects/${PROJECT_ID}/databases/(default)/documents/${path}`,
    {
      method: 'PATCH',
      headers: {
        Authorization: 'Bearer owner',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fields: {
          filename: { stringValue: data.filename },
          student_id: { stringValue: data.student_id },
        },
      }),
    }
  );
  if (!response.ok) {
    throw new Error(`collectionGroup用シードに失敗しました: ${await response.text()}`);
  }
}

function adminDb(email: string) {
  return testEnv
    .authenticatedContext(email, { email, email_verified: true })
    .firestore();
}

function unauthedDb() {
  return testEnv.unauthenticatedContext().firestore();
}

// collectionGroupクエリはcompatラッパーを経由せず、modular SDKの専用Appで実行する。
// 接続先は initializeFirestore() の時点で一度だけ設定する。
async function unauthedDbForCollectionGroup() {
  const app = initializeApp(
    { projectId: PROJECT_ID },
    `collection-group-test-${Date.now()}-${Math.random()}`
  );
  const db = initializeFirestore(app, {
    host: 'localhost:8080',
    ssl: false,
  });
  return { db, cleanup: () => deleteApp(app) };
}

describe('firestore.rules', () => {
  describe('未認証', () => {
    it('students read = 成功（リンク共有運用の維持を確認）', async () => {
      await seedStudent('S1', { status: 'active' });
      await assertSucceeds(getDoc(doc(unauthedDb(), 'students', 'S1')));
    });

    it('submissions のネストしたドキュメント read = 成功', async () => {
      await testEnv.withSecurityRulesDisabled(async (context) => {
        await setDoc(
          doc(context.firestore(), 'submissions/ClassA/tasks/Task1/files/File1'),
          { filename: 'x.pdf' }
        );
      });
      await assertSucceeds(
        getDoc(doc(unauthedDb(), 'submissions/ClassA/tasks/Task1/files/File1'))
      );
    });

    it('submissions配下のfilesへのcollectionGroupクエリ read = 成功（受講生詳細ページの提出履歴表示で使用。回帰テスト: match /submissions/{document=**}はpath-specificのためcollectionGroupクエリに適用されない仕様の穴を検出する）', async () => {
      await seedCollectionGroupFile('submissions/ClassA/tasks/Task1/files/File1', {
        filename: 'x.pdf',
        student_id: 'N0001',
      });
      await seedCollectionGroupFile('submissions/ClassB/tasks/Task2/files/File2', {
        filename: 'y.pdf',
        student_id: 'N0002',
      });
      const { db, cleanup } = await unauthedDbForCollectionGroup();
      try {
        const q = query(collectionGroup(db, 'files'), where('student_id', '==', 'N0001'));
        const snapshot = await assertSucceeds(getDocs(q));
        if (snapshot.size !== 1) {
          throw new Error(`期待した件数と異なります: expected=1 actual=${snapshot.size}`);
        }
      } finally {
        await cleanup();
      }
    });

    it('admins get = 拒否（再帰ワイルドカードのトラップの回帰テスト）', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await assertFails(getDoc(doc(unauthedDb(), 'admins', ADMIN_EMAIL)));
    });

    it('admins list = 拒否', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await assertFails(getDocs(collection(unauthedDb(), 'admins')));
    });

    it('students update = 拒否', async () => {
      await seedStudent('S1', { status: 'active' });
      await assertFails(
        updateDoc(doc(unauthedDb(), 'students', 'S1'), { status: 'withdrawn' })
      );
    });

    it('未知コレクションへの書き込み = 拒否（default-deny）', async () => {
      await assertFails(setDoc(doc(unauthedDb(), 'teachers', 'T1'), { name: 'x' }));
    });
  });

  describe('認証あり・非管理者', () => {
    it('admins list = 拒否', async () => {
      await assertFails(getDocs(collection(adminDb(NON_ADMIN_EMAIL), 'admins')));
    });

    it('他人のadmins get = 拒否', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await assertFails(getDoc(doc(adminDb(NON_ADMIN_EMAIL), 'admins', ADMIN_EMAIL)));
    });

    it('自分のadmins get（存在せず）= 成功（exists()===falseが返る）', async () => {
      await assertSucceeds(
        getDoc(doc(adminDb(NON_ADMIN_EMAIL), 'admins', NON_ADMIN_EMAIL))
      );
    });

    it('students update = 拒否', async () => {
      await seedStudent('S1', { status: 'active' });
      await assertFails(
        updateDoc(doc(adminDb(NON_ADMIN_EMAIL), 'students', 'S1'), {
          status: 'withdrawn',
          last_updated: 'x',
        })
      );
    });
  });

  describe('認証あり・管理者', () => {
    it('students update(status, last_updated) = 成功', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await seedStudent('S1', { status: 'active' });
      await assertSucceeds(
        updateDoc(doc(adminDb(ADMIN_EMAIL), 'students', 'S1'), {
          status: 'withdrawn',
          last_updated: 'x',
        })
      );
    });

    it('許可されていないフィールドを含む更新 = 拒否', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await seedStudent('S1', { status: 'active' });
      await assertFails(
        updateDoc(doc(adminDb(ADMIN_EMAIL), 'students', 'S1'), {
          status: 'withdrawn',
          name: 'hacked',
        })
      );
    });

    it('students create = 拒否', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await assertFails(setDoc(doc(adminDb(ADMIN_EMAIL), 'students', 'S2'), { status: 'active' }));
    });

    it('students delete = 拒否', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await seedStudent('S3', { status: 'active' });
      await assertFails(deleteDoc(doc(adminDb(ADMIN_EMAIL), 'students', 'S3')));
    });

    it('admins write = 拒否（Admin SDK経由のみ許可）', async () => {
      await seedAdmin(ADMIN_EMAIL);
      await assertFails(setDoc(doc(adminDb(ADMIN_EMAIL), 'admins', 'new@example.com'), {}));
    });

    it('email_verified=false = 拒否', async () => {
      await seedStudent('S1', { status: 'active' });
      const db = testEnv
        .authenticatedContext(ADMIN_EMAIL, { email: ADMIN_EMAIL, email_verified: false })
        .firestore();
      await assertFails(updateDoc(doc(db, 'students', 'S1'), { status: 'withdrawn' }));
    });

    it('大文字混じりメール Foo@Bar.com は admins/foo@bar.com に一致して成功（lower()の検証）', async () => {
      await seedAdmin('foo@bar.com');
      await seedStudent('S1', { status: 'active' });
      const db = testEnv
        .authenticatedContext('mixed-case-uid', { email: 'Foo@Bar.com', email_verified: true })
        .firestore();
      await assertSucceeds(
        updateDoc(doc(db, 'students', 'S1'), { status: 'withdrawn', last_updated: 'x' })
      );
    });
  });

  describe('その他', () => {
    it('email claimを持たない認証ユーザー = 拒否', async () => {
      await seedStudent('S1', { status: 'active' });
      const db = testEnv.authenticatedContext('anon-uid', {}).firestore();
      await assertFails(updateDoc(doc(db, 'students', 'S1'), { status: 'withdrawn' }));
    });

    it('新規コレクション（未定義）への未認証read = 拒否（default-deny）', async () => {
      await testEnv.withSecurityRulesDisabled(async (context) => {
        await setDoc(doc(context.firestore(), 'teachers', 'T1'), { name: 'x' });
      });
      await assertFails(getDoc(doc(unauthedDb(), 'teachers', 'T1')));
    });
  });
});
