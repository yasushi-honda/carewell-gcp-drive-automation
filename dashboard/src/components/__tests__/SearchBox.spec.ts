import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SearchBox from '../SearchBox.vue';

describe('SearchBox', () => {
  it('should render with initial value', () => {
    const wrapper = mount(SearchBox, {
      props: {
        modelValue: 'initial search',
      },
    });

    const input = wrapper.find('input');
    expect(input.element.value).toBe('initial search');
  });

  it('should emit update:modelValue on input', async () => {
    const wrapper = mount(SearchBox, {
      props: {
        modelValue: '',
      },
    });

    const input = wrapper.find('input');
    await input.setValue('森平');

    expect(wrapper.emitted('update:modelValue')).toBeTruthy();
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['森平']);
  });

  it('should have proper placeholder text', () => {
    const wrapper = mount(SearchBox, {
      props: {
        modelValue: '',
        placeholder: '学生名または学生IDで検索',
      },
    });

    const input = wrapper.find('input');
    expect(input.attributes('placeholder')).toBe('学生名または学生IDで検索');
  });

  it('should have search icon', () => {
    const wrapper = mount(SearchBox, {
      props: {
        modelValue: '',
      },
    });

    const svg = wrapper.find('svg');
    expect(svg.exists()).toBe(true);
  });

  it('should have proper input attributes for accessibility', () => {
    const wrapper = mount(SearchBox, {
      props: {
        modelValue: '',
      },
    });

    const input = wrapper.find('input');
    expect(input.attributes('type')).toBe('text');
  });
});
