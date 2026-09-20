import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SortOptions from '../SortOptions.vue';

type Options = Array<{ key: string; label: string; order: 'asc' | 'desc' | null }>;

function mountOptions(options: Options) {
  return mount(SortOptions, { props: { options } });
}

describe('SortOptions', () => {
  const idle: Options = [
    { key: 'furigana', label: 'ふりがな', order: null },
    { key: 'serial_number', label: '通し番号', order: null },
  ];

  it('should render a labelled group with one button per option', () => {
    const wrapper = mountOptions(idle);

    const group = wrapper.get('[role="group"]');
    expect(group.attributes('aria-label')).toBe('ソートオプション');
    const buttons = group.findAll('button');
    expect(buttons.map((b) => b.text())).toEqual([
      expect.stringContaining('ふりがな'),
      expect.stringContaining('通し番号'),
    ]);
  });

  it('should keep every button a 44px minimum height touch target', () => {
    const wrapper = mountOptions(idle);

    for (const button of wrapper.findAll('button')) {
      expect(button.classes()).toContain('min-h-11');
      expect(button.attributes('type')).toBe('button');
    }
  });

  it('should emit toggle with the option key when a button is clicked', async () => {
    const wrapper = mountOptions(idle);

    await wrapper.findAll('button')[1].trigger('click');
    await wrapper.findAll('button')[0].trigger('click');

    expect(wrapper.emitted('toggle')).toEqual([['serial_number'], ['furigana']]);
  });

  it('should show the idle indicator and mark nothing as pressed when no sort is active', () => {
    const wrapper = mountOptions(idle);

    for (const button of wrapper.findAll('button')) {
      expect(button.attributes('aria-pressed')).toBe('false');
      expect(button.text()).toContain('⇅');
      expect(button.text()).toContain('並べ替えなし');
    }
  });

  it('should show ▲ / 昇順 and mark the active option as pressed for ascending order', () => {
    const wrapper = mountOptions([
      { key: 'furigana', label: 'ふりがな', order: 'asc' },
      { key: 'serial_number', label: '通し番号', order: null },
    ]);

    const [furigana, serial] = wrapper.findAll('button');
    expect(furigana.attributes('aria-pressed')).toBe('true');
    expect(furigana.text()).toContain('▲');
    expect(furigana.text()).toContain('昇順');
    expect(serial.attributes('aria-pressed')).toBe('false');
  });

  it('should show ▼ / 降順 for descending order', () => {
    const wrapper = mountOptions([
      { key: 'furigana', label: 'ふりがな', order: null },
      { key: 'serial_number', label: '通し番号', order: 'desc' },
    ]);

    const serial = wrapper.findAll('button')[1];
    expect(serial.attributes('aria-pressed')).toBe('true');
    expect(serial.text()).toContain('▼');
    expect(serial.text()).toContain('降順');
  });

  it('should hide the visual indicator from assistive technology and describe the state in text instead', () => {
    const wrapper = mountOptions([{ key: 'furigana', label: 'ふりがな', order: 'asc' }]);

    const spans = wrapper.get('button').findAll('span');
    const indicator = spans.find((s) => s.text() === '▲')!;
    expect(indicator.attributes('aria-hidden')).toBe('true');
    const description = spans.find((s) => s.text() === '（昇順）')!;
    expect(description.classes()).toContain('sr-only');
  });
});
