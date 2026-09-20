import { describe, it, expect, afterEach } from 'vitest';
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h } from 'vue';
import GroupCard from '../GroupCard.vue';
import type { GroupSubmission } from '../../composables/useGroupStats';

const mounted: VueWrapper[] = [];

async function mountCard(props: { submission?: GroupSubmission | null; submissionLoading?: boolean } = {}) {
  const Stub = defineComponent({ render: () => h('div') });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Stub },
      { path: '/class/:className/task/:taskId/group/:groupName/students', component: Stub },
    ],
  });
  await router.push('/');
  await router.isReady();
  const wrapper = mount(GroupCard, {
    props: { className: 'クラスX', taskId: '課題①', group: 'A', studentCount: 17, ...props },
    global: { plugins: [router] },
  });
  mounted.push(wrapper);
  return { wrapper, router };
}

describe('GroupCard', () => {
  afterEach(() => {
    mounted.splice(0).forEach((w) => w.unmount());
  });

  it('should keep the original card (title, student count, plain label) when there is no submission data', async () => {
    const { wrapper } = await mountCard();

    expect(wrapper.text()).toContain('A グループ');
    expect(wrapper.text()).toContain('17 人');
    expect(wrapper.attributes('aria-label')).toBe('Aグループ、受講生17人');
    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="submission-skeleton"]').exists()).toBe(false);
  });

  it('should show the submission bar and include the breakdown in the accessible label', async () => {
    const { wrapper } = await mountCard({
      submission: { submitted: 12, notSubmitted: 5, passed: 8, pending: 3, failed: 1 },
    });

    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(true);
    expect(wrapper.attributes('aria-label')).toBe(
      'Aグループ、受講生17人、提出12人、未提出5人（合格8・採点待ち3・不合格1）'
    );
  });

  it('should show the placeholder while loading and keep the plain label', async () => {
    const { wrapper } = await mountCard({ submissionLoading: true });

    expect(wrapper.find('[data-testid="submission-skeleton"]').exists()).toBe(true);
    expect(wrapper.attributes('aria-label')).toBe('Aグループ、受講生17人');
  });

  it('should stay a keyboard-operable button and navigate to the group students on click and Enter', async () => {
    const { wrapper, router } = await mountCard();
    expect(wrapper.attributes('role')).toBe('button');
    expect(wrapper.attributes('tabindex')).toBe('0');

    await wrapper.trigger('click');
    await flushPromises();
    expect(router.currentRoute.value.path).toBe('/class/クラスX/task/課題①/group/A/students');

    await router.push('/');
    await wrapper.trigger('keydown.enter');
    await flushPromises();
    expect(router.currentRoute.value.path).toBe('/class/クラスX/task/課題①/group/A/students');
  });
});
