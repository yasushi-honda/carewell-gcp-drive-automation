import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ClassCard from '../ClassCard.vue';

describe('ClassCard', () => {
  it('should render class information correctly', () => {
    const wrapper = mount(ClassCard, {
      props: {
        className: '令和8年度 デジタル中核人材養成研修 №01',
        taskCount: 5,
        fileCount: 25,
        lastUpdated: '2025-10-13T10:00:00.000Z',
      },
    });

    expect(wrapper.text()).toContain('令和8年度 デジタル中核人材養成研修 №01');
    expect(wrapper.text()).toContain('5');
    expect(wrapper.text()).toContain('25');
  });

  it('should emit click event when clicked', async () => {
    const wrapper = mount(ClassCard, {
      props: {
        className: 'Test Class',
        taskCount: 3,
        fileCount: 10,
        lastUpdated: null,
      },
    });

    await wrapper.trigger('click');

    expect(wrapper.emitted('click')).toHaveLength(1);
  });

  it('should handle keyboard interaction (Enter)', async () => {
    const wrapper = mount(ClassCard, {
      props: {
        className: 'Test Class',
        taskCount: 3,
        fileCount: 10,
        lastUpdated: null,
      },
    });

    await wrapper.trigger('keydown.enter');

    expect(wrapper.emitted('click')).toHaveLength(1);
  });

  it('should have proper accessibility attributes', () => {
    const wrapper = mount(ClassCard, {
      props: {
        className: 'Test Class',
        taskCount: 3,
        fileCount: 10,
        lastUpdated: null,
      },
    });

    const card = wrapper.find('[role="button"]');
    expect(card.exists()).toBe(true);
    expect(card.attributes('tabindex')).toBe('0');
    expect(card.attributes('aria-label')).toContain('Test Class');
  });

  it('should display "未更新" when lastUpdated is null', () => {
    const wrapper = mount(ClassCard, {
      props: {
        className: 'Test Class',
        taskCount: 3,
        fileCount: 10,
        lastUpdated: null,
      },
    });

    expect(wrapper.text()).toContain('未更新');
  });

  it('should apply hover and active styles', () => {
    const wrapper = mount(ClassCard, {
      props: {
        className: 'Test Class',
        taskCount: 3,
        fileCount: 10,
        lastUpdated: null,
      },
    });

    const card = wrapper.find('.cursor-pointer');
    expect(card.exists()).toBe(true);
    expect(card.classes()).toContain('hover:shadow-lg');
    expect(card.classes()).toContain('active:shadow-xl');
  });
});
