import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ErrorAlert from '../ErrorAlert.vue';

describe('ErrorAlert', () => {
  it('should render error message', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'データの取得に失敗しました',
      },
    });

    expect(wrapper.text()).toContain('データの取得に失敗しました');
  });

  it('should render custom title', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        title: 'カスタムエラー',
        message: 'エラー詳細',
      },
    });

    expect(wrapper.text()).toContain('カスタムエラー');
    expect(wrapper.text()).toContain('エラー詳細');
  });

  it('should render default title when not provided', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'エラーメッセージ',
      },
    });

    expect(wrapper.text()).toContain('エラーが発生しました');
  });

  it('should show retry button by default', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'エラーメッセージ',
      },
    });

    const retryButton = wrapper.find('button');
    expect(retryButton.exists()).toBe(true);
    expect(retryButton.text()).toContain('再試行');
  });

  it('should hide retry button when showRetry is false', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'エラーメッセージ',
        showRetry: false,
      },
    });

    const retryButton = wrapper.find('button');
    expect(retryButton.exists()).toBe(false);
  });

  it('should emit retry event when retry button is clicked', async () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'エラーメッセージ',
        showRetry: true,
      },
    });

    const retryButton = wrapper.find('button');
    await retryButton.trigger('click');

    expect(wrapper.emitted('retry')).toHaveLength(1);
  });

  it('should have proper ARIA attributes', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'エラーメッセージ',
      },
    });

    const alert = wrapper.find('[role="alert"]');
    expect(alert.exists()).toBe(true);
    expect(alert.attributes('aria-live')).toBe('assertive');
  });

  it('should display error icon', () => {
    const wrapper = mount(ErrorAlert, {
      props: {
        message: 'エラーメッセージ',
      },
    });

    const icon = wrapper.find('svg');
    expect(icon.exists()).toBe(true);
  });
});
