import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import StudentSubmissionCell from '../StudentSubmissionCell.vue';
import type { StudentSubmission } from '../../composables/useStudentSubmissions';

function mountCell(props: { state: 'loading' | 'ready' | 'error' | 'mismatch'; submission?: StudentSubmission }) {
  return mount(StudentSubmissionCell, { props });
}

const submission = (overrides: Partial<StudentSubmission> = {}): StudentSubmission => ({
  status: 'passed',
  latestSubmitDate: '2026/09/20 10:05:33',
  fileCount: 1,
  ...overrides,
});

describe('StudentSubmissionCell', () => {
  it.each([
    ['passed', '合格'],
    ['pending', '採点待ち'],
    ['failed', '不合格'],
  ] as const)('should show %s as a "%s" badge with the latest submit time (no seconds)', (status, label) => {
    const wrapper = mountCell({ state: 'ready', submission: submission({ status }) });

    const badge = wrapper.find('[data-status]');
    expect(badge.text()).toBe(label);
    expect(badge.attributes('data-status')).toBe(status);
    expect(wrapper.text()).toContain('最終提出 2026/09/20 10:05');
    expect(wrapper.text()).not.toContain('10:05:33');
  });

  it('should show 未提出 (and no date) for a student without a submission', () => {
    const wrapper = mountCell({ state: 'ready' });

    const badge = wrapper.find('[data-status]');
    expect(badge.text()).toBe('未提出');
    expect(badge.attributes('data-status')).toBe('not_submitted');
    expect(wrapper.text()).not.toContain('最終提出');
  });

  it('should show the number of submissions only for a resubmission', () => {
    expect(mountCell({ state: 'ready', submission: submission({ fileCount: 1 }) }).text()).not.toContain('回）');
    expect(mountCell({ state: 'ready', submission: submission({ fileCount: 3 }) }).text()).toContain('（3回）');
  });

  it('should omit the date line when the submit date is missing', () => {
    const wrapper = mountCell({ state: 'ready', submission: submission({ latestSubmitDate: '' }) });

    expect(wrapper.find('[data-status]').text()).toBe('合格');
    expect(wrapper.text()).not.toContain('最終提出');
  });

  it('should show only a skeleton while loading', () => {
    const wrapper = mountCell({ state: 'loading' });

    expect(wrapper.find('[data-testid="submission-cell-loading"]').exists()).toBe(true);
    expect(wrapper.find('[data-status]').exists()).toBe(false);
  });

  it.each(['error', 'mismatch'] as const)(
    'should show "-" and never 未提出 when the status is unavailable (%s)',
    (state) => {
      const wrapper = mountCell({ state });

      expect(wrapper.text()).toBe('-');
      expect(wrapper.text()).not.toContain('未提出');
      expect(wrapper.find('[data-status]').exists()).toBe(false);
    }
  );
});
