import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h, toValue } from 'vue';
import GroupListView from '../GroupListView.vue';
import type { GroupStat, SubmissionState } from '../../composables/useGroupStats';

// 取得の順序・失敗・競合は useGroupStats.spec.ts で確認済み。ここでは、状態ごとの画面の出し分けを確認する。
const composable = vi.hoisted(() => ({
  args: [] as unknown[],
  refetch: vi.fn(),
  refetchSubmissions: vi.fn(),
}));

vi.mock('../../composables/useGroupStats', async () => {
  const { ref } = await import('vue');
  const groupStats = ref<GroupStat[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const submissionState = ref<SubmissionState>('ready');
  const unmatchedSubmitters = ref(0);
  const unidentifiedFiles = ref(0);
  const submitters = ref(0);
  return {
    useGroupStats: (...args: unknown[]) => {
      composable.args = args;
      return {
        groupStats,
        loading,
        error,
        refetch: composable.refetch,
        submissionState,
        unmatchedSubmitters,
        unidentifiedFiles,
        submitters,
        refetchSubmissions: composable.refetchSubmissions,
      };
    },
    __state: { groupStats, loading, error, submissionState, unmatchedSubmitters, unidentifiedFiles, submitters },
  };
});

const state = (await import('../../composables/useGroupStats') as any).__state;

const SUBMISSION = { submitted: 12, notSubmitted: 5, passed: 8, pending: 3, failed: 1 };
const STATS: GroupStat[] = [
  { group: 'A', studentCount: 17, submission: SUBMISSION },
  { group: 'B', studentCount: 17, submission: { submitted: 17, notSubmitted: 0, passed: 17, pending: 0, failed: 0 } },
];

const mounted: VueWrapper[] = [];

async function mountView(path = '/class/クラスX/task/課題①/groups') {
  const Stub = defineComponent({ render: () => h('div') });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Stub },
      { path: '/class/:className', component: Stub },
      { path: '/class/:className/task/:taskId', component: Stub },
      { path: '/class/:className/task/:taskId/groups', component: GroupListView },
      { path: '/class/:className/task/:taskId/group/:groupName/students', component: Stub },
    ],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(GroupListView, { global: { plugins: [router] } });
  mounted.push(wrapper);
  return { wrapper, router };
}

const cards = (wrapper: VueWrapper) => wrapper.findAll('[role="button"]');

describe('GroupListView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.groupStats.value = STATS;
    state.loading.value = false;
    state.error.value = null;
    state.submissionState.value = 'ready';
    state.unmatchedSubmitters.value = 0;
    state.unidentifiedFiles.value = 0;
    state.submitters.value = 0;
  });

  afterEach(() => {
    mounted.splice(0).forEach((w) => w.unmount());
  });

  it('should pass the route class and task to the composable (as values that follow the route)', async () => {
    const { router } = await mountView('/class/クラスX/task/課題①/groups');

    expect(toValue(composable.args[0] as never)).toBe('クラスX');
    expect(toValue(composable.args[1] as never)).toBe('課題①');

    await router.push('/class/クラスX/task/課題②/groups');
    expect(toValue(composable.args[1] as never)).toBe('課題②');
  });

  it('should render a card per group with the legend and no banner when everything is ready', async () => {
    const { wrapper } = await mountView();

    expect(cards(wrapper)).toHaveLength(2);
    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(true);
    const legend = wrapper.get('ul[aria-label="バーの凡例"]').text();
    for (const label of ['合格', '採点待ち', '不合格', '未提出']) expect(legend).toContain(label);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('should show skeleton bars and the legend (so the cards do not move on arrival) while the submissions are loading', async () => {
    state.submissionState.value = 'loading';
    state.groupStats.value = STATS.map(({ group, studentCount }) => ({ group, studentCount }));

    const { wrapper } = await mountView();

    expect(cards(wrapper)).toHaveLength(2);
    expect(wrapper.findAll('[data-testid="submission-skeleton"]')).toHaveLength(2);
    expect(wrapper.find('ul[aria-label="バーの凡例"]').exists()).toBe(true);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
  });

  it('should keep the cards and offer a retry when only the submissions failed', async () => {
    state.submissionState.value = 'error';
    state.groupStats.value = STATS.map(({ group, studentCount }) => ({ group, studentCount }));

    const { wrapper } = await mountView();

    expect(cards(wrapper)).toHaveLength(2);
    expect(wrapper.get('[role="alert"]').text()).toContain('提出状況を取得できませんでした');
    expect(wrapper.find('ul[aria-label="バーの凡例"]').exists()).toBe(false);
    // 「全員未提出」のような数字は出さない
    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="submission-skeleton"]').exists()).toBe(false);

    await wrapper.get('[role="alert"] button').trigger('click');
    expect(composable.refetchSubmissions).toHaveBeenCalledTimes(1);
    expect(composable.refetch).not.toHaveBeenCalled();
  });

  it('should warn instead of showing a breakdown when the submissions do not match the roster', async () => {
    state.submissionState.value = 'mismatch';
    state.groupStats.value = STATS.map(({ group, studentCount }) => ({ group, studentCount }));

    const { wrapper } = await mountView();

    expect(cards(wrapper)).toHaveLength(2);
    expect(wrapper.get('[role="alert"]').text()).toContain('受講生名簿が一致しなかった');
    expect(wrapper.find('ul[aria-label="バーの凡例"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(false);
  });

  it('should note a few submitters who are not on the roster, below the cards, in the normal tone', async () => {
    state.unmatchedSubmitters.value = 2;
    state.submitters.value = 13;

    const { wrapper } = await mountView();

    const note = wrapper.get('[role="status"]');
    expect(note.text()).toContain('2 人分');
    expect(note.text()).not.toContain('食い違い');
    expect(note.classes()).not.toContain('text-amber-800');
    // カードより後ろ（下）に出る
    const html = wrapper.html();
    expect(html.indexOf('受講生名簿にない提出')).toBeGreaterThan(html.lastIndexOf('role="button"'));
    expect(cards(wrapper)).toHaveLength(2);
  });

  it('should raise the tone and suspect a student id mismatch when most submitters are not on the roster', async () => {
    state.unmatchedSubmitters.value = 7;
    state.submitters.value = 13;

    const { wrapper } = await mountView();

    const note = wrapper.get('[role="status"]');
    expect(note.text()).toContain('食い違いの可能性');
    expect(note.classes()).toContain('text-amber-800');
  });

  it('should treat exactly half as most (the boundary)', async () => {
    state.unmatchedSubmitters.value = 5;
    state.submitters.value = 10;

    const { wrapper } = await mountView();

    expect(wrapper.get('[role="status"]').text()).toContain('食い違いの可能性');
  });

  it('should note files with an empty student id', async () => {
    state.unidentifiedFiles.value = 3;

    const { wrapper } = await mountView();

    expect(wrapper.get('[role="status"]').text()).toContain('日介番号が空の提出ファイルが 3 件');
  });

  it('should not show any note when nothing is excluded', async () => {
    const { wrapper } = await mountView();

    expect(wrapper.find('[role="status"]').exists()).toBe(false);
  });

  it('should show the page-level error and retry the whole fetch when the students failed', async () => {
    state.error.value = 'グループ統計の取得に失敗しました';
    state.groupStats.value = [];

    const { wrapper } = await mountView();

    expect(wrapper.text()).toContain('グループ統計の取得に失敗しました');
    expect(cards(wrapper)).toHaveLength(0);
    await wrapper.get('button').trigger('click');
    expect(composable.refetch).toHaveBeenCalledTimes(1);
  });

  it('should show the loading skeleton (and no cards) while the students are loading', async () => {
    state.loading.value = true;
    state.groupStats.value = [];

    const { wrapper } = await mountView();

    expect(cards(wrapper)).toHaveLength(0);
    expect(wrapper.findAll('[aria-busy="true"]').length).toBeGreaterThan(0);
  });

  it('should show the empty state when the class has no groups', async () => {
    state.groupStats.value = [];

    const { wrapper } = await mountView();

    expect(wrapper.text()).toContain('グループが見つかりませんでした');
  });

  it('should keep the groups in the order given (A to Z)', async () => {
    const { wrapper } = await mountView();

    expect(cards(wrapper).map((c) => c.text().slice(0, 1))).toEqual(['A', 'B']);
  });
});
