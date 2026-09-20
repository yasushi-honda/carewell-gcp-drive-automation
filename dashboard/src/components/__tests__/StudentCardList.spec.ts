import { describe, it, expect } from 'vitest';
import { mount, RouterLinkStub } from '@vue/test-utils';
import StudentCardList from '../StudentCardList.vue';
import type { Student } from '../../types/models';
import type { StudentSubmission } from '../../composables/useStudentSubmissions';

function student(overrides: Partial<Student> = {}): Student {
  return {
    student_id: 'N0000001',
    name: '山田　太郎',
    furigana: 'やまだ　たろう',
    group: 'A',
    company: '',
    office: '',
    service_type: '通所系',
    serial_number: 14,
    student_number: 'A014',
    class_name: 'No1',
    status: 'active',
    ...overrides,
  };
}

function mountList(props: {
  students: Student[];
  showClass?: boolean;
  showGroup?: boolean;
  submissionState?: 'loading' | 'ready' | 'error' | 'mismatch';
  submissions?: Map<string, StudentSubmission>;
}) {
  return mount(StudentCardList, {
    props,
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe('StudentCardList', () => {
  it('should render one card per student, each as a link to the detail page', () => {
    const wrapper = mountList({
      students: [student({ student_id: 'N0000001' }), student({ student_id: 'N0000002', name: '佐藤　花子' })],
    });

    const links = wrapper.findAllComponents(RouterLinkStub);
    expect(links).toHaveLength(2);
    expect(links.map((l) => l.props('to'))).toEqual(['/students/N0000001', '/students/N0000002']);
  });

  it('should show name, furigana and student id on the card', () => {
    const wrapper = mountList({ students: [student()] });

    expect(wrapper.text()).toContain('山田　太郎');
    expect(wrapper.text()).toContain('やまだ　たろう');
    expect(wrapper.text()).toContain('N0000001');
  });

  it('should show student number and service type', () => {
    const wrapper = mountList({ students: [student({ student_number: 'A014', service_type: '入所・居住系' })] });

    expect(wrapper.text()).toContain('受講者番号');
    expect(wrapper.text()).toContain('A014');
    expect(wrapper.text()).toContain('入所・居住系');
  });

  it('should hide class and group by default (they are the same for everyone in a group list)', () => {
    const wrapper = mountList({ students: [student({ class_name: 'No1', group: 'A' })] });

    expect(wrapper.text()).not.toContain('クラス');
    expect(wrapper.text()).not.toContain('グループ');
  });

  it('should show class and group when requested', () => {
    const wrapper = mountList({
      students: [student({ class_name: 'No3', group: 'K' })],
      showClass: true,
      showGroup: true,
    });

    expect(wrapper.text()).toContain('クラス');
    expect(wrapper.text()).toContain('No3');
    expect(wrapper.text()).toContain('グループ');
    expect(wrapper.text()).toContain('K');
  });

  it('should show "-" for a missing student number and class name', () => {
    const wrapper = mountList({
      students: [student({ student_number: '', class_name: '' })],
      showClass: true,
    });

    const values = wrapper.findAll('dd').map((dd) => dd.text());
    // 受講者番号 / クラス / サービス種別
    expect(values.slice(0, 2)).toEqual(['-', '-']);
  });

  it('should show "-" only for the missing student number, not for the other fields', () => {
    const wrapper = mountList({
      students: [student({ student_number: '', class_name: 'No1' })],
      showClass: true,
    });

    const values = wrapper.findAll('dd').map((dd) => dd.text());
    expect(values[0]).toBe('-');
    expect(values[1]).not.toBe('-');
  });

  it('should visually mute withdrawn students, like the table rows do', () => {
    const wrapper = mountList({
      students: [student({ student_id: 'N0000009', status: 'withdrawn' }), student({ student_id: 'N0000010' })],
    });

    const [withdrawn, active] = wrapper.findAllComponents(RouterLinkStub);
    expect(withdrawn.classes()).toContain('opacity-60');
    expect(active.classes()).not.toContain('opacity-60');
  });

  it('should render an empty list without cards', () => {
    const wrapper = mountList({ students: [] });

    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(0);
  });

  it('should give every card a 44px minimum height touch target', () => {
    const wrapper = mountList({ students: [student(), student({ student_id: 'N0000002' })] });

    for (const link of wrapper.findAllComponents(RouterLinkStub)) {
      expect(link.classes()).toContain('min-h-11');
    }
  });
  describe('提出状況（グループ内の一覧のみ）', () => {
    it('should not show a submission row unless submissionState is given (the all-students list has none)', () => {
      const wrapper = mountList({ students: [student()] });

      expect(wrapper.text()).not.toContain('提出状況');
      expect(wrapper.find('[data-testid="submission-cell"]').exists()).toBe(false);
    });

    it('should show each student\'s own status, and 未提出 for a student without files', () => {
      const wrapper = mountList({
        students: [student({ student_id: 'N1' }), student({ student_id: 'N2' })],
        submissionState: 'ready',
        submissions: new Map([['N1', { status: 'failed', latestSubmitDate: '2026/09/20 10:00:00', fileCount: 1 }]]),
      });

      const badges = wrapper.findAll('[data-status]').map((b) => b.attributes('data-status'));
      expect(badges).toEqual(['failed', 'not_submitted']);
    });

    it('should say 対象外 (not 未提出) on the card of a withdrawn student without files', () => {
      const wrapper = mountList({
        students: [student({ student_id: 'N1', status: 'withdrawn' })],
        submissionState: 'ready',
        submissions: new Map(),
      });

      expect(wrapper.text()).toContain('対象外');
      expect(wrapper.text()).not.toContain('未提出');
    });

    it('should not claim 未提出 while loading or when the status could not be fetched', () => {
      for (const submissionState of ['loading', 'error', 'mismatch'] as const) {
        const wrapper = mountList({ students: [student()], submissionState, submissions: new Map() });

        expect(wrapper.text()).not.toContain('未提出');
        expect(wrapper.find('[data-status]').exists()).toBe(false);
        // 行そのものは残し、読み込み中は骨格、それ以外は「-」を出す
        expect(wrapper.text()).toContain('提出状況');
        expect(wrapper.find('[data-testid="submission-cell-loading"]').exists()).toBe(submissionState === 'loading');
        if (submissionState !== 'loading') {
          expect(wrapper.find('[data-testid="submission-cell-unavailable"]').text()).toBe('-');
        }
      }
    });
  });
});
