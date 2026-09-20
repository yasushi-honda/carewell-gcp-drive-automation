import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SubmissionBar from '../SubmissionBar.vue';
import type { GroupSubmission } from '../../composables/useGroupStats';

const mix: GroupSubmission = { submitted: 12, notSubmitted: 5, passed: 8, pending: 3, failed: 1 };

function mountBar(props: { total: number; submission?: GroupSubmission | null; loading?: boolean }) {
  return mount(SubmissionBar, { props });
}

const widths = (wrapper: ReturnType<typeof mountBar>) =>
  wrapper.findAll('[data-segment]').map((el) => [el.attributes('data-segment'), (el.element as HTMLElement).style.width]);

describe('SubmissionBar', () => {
  it('should show submitted and not-submitted numbers with the pass/pending/fail breakdown', () => {
    const wrapper = mountBar({ total: 17, submission: mix });

    const text = wrapper.text().replace(/\s+/g, ' ');
    expect(text).toContain('提出 12');
    expect(text).toContain('未提出 5');
    expect(text).toContain('合格 8');
    expect(text).toContain('採点待ち 3');
    expect(text).toContain('不合格 1');
  });

  it('should size each segment by its share of the group (passed, pending, failed; the rest is the grey background)', () => {
    const wrapper = mountBar({ total: 20, submission: { submitted: 10, notSubmitted: 10, passed: 5, pending: 4, failed: 1 } });

    expect(widths(wrapper)).toEqual([
      ['passed', '25%'],
      ['pending', '20%'],
      ['failed', '5%'],
    ]);
  });

  it('should round the widths to two decimals (no floating point noise)', () => {
    expect(widths(mountBar({ total: 3, submission: { submitted: 1, notSubmitted: 2, passed: 1, pending: 0, failed: 0 } }))).toEqual([
      ['passed', '33.33%'],
    ]);
    expect(widths(mountBar({ total: 7, submission: { submitted: 1, notSubmitted: 6, passed: 0, pending: 1, failed: 0 } }))).toEqual([
      ['pending', '14.29%'],
    ]);
    expect(widths(mountBar({ total: 15, submission: { submitted: 3, notSubmitted: 12, passed: 0, pending: 0, failed: 3 } }))).toEqual([
      ['failed', '20%'],
    ]);
  });

  it('should never let the segments add up to more than the bar', () => {
    const wrapper = mountBar({ total: 3, submission: { submitted: 3, notSubmitted: 0, passed: 1, pending: 1, failed: 1 } });

    const sum = wrapper.findAll('[data-segment]').reduce((acc, el) => acc + parseFloat((el.element as HTMLElement).style.width), 0);
    expect(sum).toBeLessThanOrEqual(100.01);
  });

  it('should omit segments with zero people', () => {
    const wrapper = mountBar({ total: 10, submission: { submitted: 4, notSubmitted: 6, passed: 4, pending: 0, failed: 0 } });

    expect(widths(wrapper)).toEqual([['passed', '40%']]);
  });

  it('should show 全員提出 instead of a not-submitted count when nobody is missing', () => {
    const wrapper = mountBar({ total: 3, submission: { submitted: 3, notSubmitted: 0, passed: 1, pending: 1, failed: 1 } });

    expect(wrapper.text()).toContain('全員提出');
    expect(wrapper.text()).not.toContain('未提出');
  });

  it('should emphasise the not-submitted count when someone is missing', () => {
    const wrapper = mountBar({ total: 17, submission: mix });

    const missing = wrapper.findAll('span').find((s) => s.text().replace(/\s+/g, ' ').includes('未提出 5'))!;
    expect(missing.classes()).toContain('font-semibold');
  });

  it('should show everyone as not submitted with an empty bar', () => {
    const wrapper = mountBar({ total: 4, submission: { submitted: 0, notSubmitted: 4, passed: 0, pending: 0, failed: 0 } });

    expect(widths(wrapper)).toEqual([]);
    expect(wrapper.text().replace(/\s+/g, ' ')).toContain('未提出 4');
  });

  it('should not draw any segments when the group size is 0 (no division by zero)', () => {
    const wrapper = mountBar({ total: 0, submission: { submitted: 0, notSubmitted: 0, passed: 0, pending: 0, failed: 0 } });

    expect(widths(wrapper)).toEqual([]);
  });

  it('should render a placeholder (hidden from assistive technology) while loading', () => {
    const wrapper = mountBar({ total: 17, submission: null, loading: true });

    const skeleton = wrapper.find('[data-testid="submission-skeleton"]');
    expect(skeleton.exists()).toBe(true);
    expect(skeleton.attributes('aria-hidden')).toBe('true');
    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(false);
  });

  it('should render nothing when there is no submission data and it is not loading (failed or mismatched)', () => {
    const wrapper = mountBar({ total: 17, submission: undefined, loading: false });

    expect(wrapper.find('[data-testid="submission-bar"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="submission-skeleton"]').exists()).toBe(false);
    expect(wrapper.text()).toBe('');
  });
});
