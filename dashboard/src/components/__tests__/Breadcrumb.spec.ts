import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { defineComponent, h } from 'vue';
import Breadcrumb from '../Breadcrumb.vue';

async function mountBreadcrumb(items: { label: string; to?: string }[]) {
  const Stub = defineComponent({ render: () => h('div') });
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: Stub }] });
  await router.push('/');
  await router.isReady();
  return mount(Breadcrumb, { props: { items }, global: { plugins: [router] } });
}

describe('Breadcrumb', () => {
  it('should render middle items with a target as links and the last item as the current page', async () => {
    const wrapper = await mountBreadcrumb([
      { label: 'ホーム', to: '/' },
      { label: 'クラスX', to: '/class/クラスX' },
      { label: 'グループ一覧' },
    ]);

    expect(wrapper.findAll('a').map((a) => a.text())).toEqual(['ホーム', 'クラスX']);
    expect(wrapper.get('[aria-current="page"]').text()).toBe('グループ一覧');
  });

  it('should render a middle item without a target as plain text (not a link, not the current page)', async () => {
    const wrapper = await mountBreadcrumb([
      { label: 'ホーム', to: '/' },
      { label: 'クラスX', to: '/class/クラスX' },
      { label: '課題①' },
      { label: 'グループ一覧' },
    ]);

    expect(wrapper.findAll('a').map((a) => a.text())).toEqual(['ホーム', 'クラスX']);
    expect(wrapper.text()).toContain('課題①');
    expect(wrapper.findAll('[aria-current="page"]')).toHaveLength(1);
    expect(wrapper.get('[aria-current="page"]').text()).toBe('グループ一覧');
  });
});
