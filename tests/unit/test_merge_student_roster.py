"""
Unit tests for scripts/merge_student_roster.py の純粋関数(正規化・突合・検証ゲート)。

ネットワーク呼び出しを含まない。境界値(重複あり/なし、欠損あり/なし、
未知グループ、例外テーブル適用あり/なし)を中心に検証する。
"""

import sys

sys.path.insert(0, "scripts")

from merge_student_roster import (  # noqa: E402
    match_students,
    normalize_key,
    validate_expected_count,
    validate_group_mapping,
    validate_required_fields,
    validate_student_number_sequence,
    validate_student_number_uniqueness,
)


def client_row(**overrides):
    base = {
        "group": "A",
        "sub_teacher": "先生",
        "student_number": "A001",
        "name": "山田 太郎",
        "kana": "やまだ たろう",
        "service_type": "介護老人保健施設",
    }
    base.update(overrides)
    return base


def app_row(**overrides):
    base = {
        "name": "山田 太郎",
        "kana": "やまだ たろう",
        "nichikai": "N0000001",
        "company": "社会福祉法人テスト会",
        "office": "テスト施設",
    }
    base.update(overrides)
    return base


class TestNormalizeKey:
    def test_identical_strings_match(self):
        assert normalize_key("山田 太郎", "やまだ たろう") == normalize_key(
            "山田 太郎", "やまだ たろう"
        )

    def test_fullwidth_and_halfwidth_space_are_equivalent(self):
        assert normalize_key("山田 太郎", "やまだ　たろう") == normalize_key(
            "山田　太郎", "やまだ たろう"
        )

    def test_katakana_and_hiragana_are_equivalent(self):
        assert normalize_key("山田 太郎", "ヤマダ タロウ") == normalize_key(
            "山田 太郎", "やまだ たろう"
        )

    def test_small_youon_variant_is_not_equivalent(self):
        # 拗音(小さい「ゅ」 vs 大きい「ゆ」)はNFKC/カタカナ変換では解決できない
        assert normalize_key("植田 隆介", "うえだ りゅうすけ") != normalize_key(
            "植田 隆介", "うえだ りゆうすけ"
        )


class TestValidateExpectedCount:
    def test_matching_count_passes(self):
        rows = [client_row(student_number=f"A{i:03d}") for i in range(1, 4)]
        assert validate_expected_count(rows, 3) == []

    def test_truncated_pull_fails_even_if_internally_consistent(self):
        # 取得が途中で欠落しても、行数から逆算する連番チェックだけでは検知できない
        # (Codex指摘)。件数の突き合わせで検知できることを確認する。
        rows = [client_row(student_number=f"A{i:03d}") for i in range(1, 201)]
        issues = validate_expected_count(rows, 254)
        assert any("254" in i and "200" in i for i in issues)

    def test_excess_count_fails(self):
        rows = [client_row(student_number=f"A{i:03d}") for i in range(1, 256)]
        issues = validate_expected_count(rows, 254)
        assert len(issues) == 1


class TestValidateStudentNumberSequence:
    def test_contiguous_sequence_passes(self):
        rows = [client_row(student_number=f"A{i:03d}") for i in range(1, 4)]
        assert validate_student_number_sequence(rows) == []

    def test_duplicate_number_fails(self):
        rows = [client_row(student_number="A001"), client_row(student_number="A001")]
        issues = validate_student_number_sequence(rows)
        assert any("重複" in i for i in issues)

    def test_gap_in_sequence_fails(self):
        rows = [client_row(student_number="A001"), client_row(student_number="A003")]
        issues = validate_student_number_sequence(rows)
        assert any("欠番" in i for i in issues)

    def test_malformed_number_fails(self):
        rows = [client_row(student_number="ZZ1")]
        issues = validate_student_number_sequence(rows)
        assert any("形式" in i for i in issues)


class TestMatchStudents:
    def test_direct_key_match(self):
        merged, unmatched, exc_issues, exc_used = match_students(
            [client_row()], [app_row()], {}
        )
        assert len(merged) == 1
        assert merged[0]["nichikai"] == "N0000001"
        assert unmatched == []
        assert exc_issues == []
        assert exc_used == []

    def test_no_candidate_and_no_exception_is_unmatched(self):
        merged, unmatched, exc_issues, exc_used = match_students(
            [client_row(student_number="A099")], [], {}
        )
        assert merged == []
        assert unmatched == ["A099"]

    def test_exception_table_rescues_unmatched_row(self):
        c = client_row(
            student_number="K165", name="植田 隆介", kana="うえだ りゆうすけ"
        )
        a = app_row(name="植田　隆介", kana="ウエダ　リュウスケ", nichikai="N9905863")
        merged, unmatched, exc_issues, exc_used = match_students(
            [c], [a], {"K165": "N9905863"}
        )
        assert len(merged) == 1
        assert merged[0]["nichikai"] == "N9905863"
        assert unmatched == []
        assert exc_issues == []
        assert exc_used == ["K165"]

    def test_exception_table_with_ambiguous_nichikai_is_rejected(self):
        c = client_row(
            student_number="K165", name="植田 隆介", kana="うえだ りゆうすけ"
        )
        dup_a = app_row(name="A", kana="a", nichikai="N9905863")
        dup_b = app_row(name="B", kana="b", nichikai="N9905863")
        merged, unmatched, exc_issues, exc_used = match_students(
            [c], [dup_a, dup_b], {"K165": "N9905863"}
        )
        assert merged == []
        assert any("一意に存在しません" in i for i in exc_issues)

    def test_exception_table_match_preserves_original_row_order(self):
        # 例外テーブル救済分がmerged末尾に回り、以降の全行が1行分ずれる回帰を防ぐ
        before = client_row(student_number="K164", name="前 太郎", kana="まえ たろう")
        exception_target = client_row(
            student_number="K165", name="植田 隆介", kana="うえだ りゆうすけ"
        )
        after = client_row(student_number="K166", name="後 花子", kana="あと はなこ")
        before_app = app_row(name="前 太郎", kana="まえ たろう", nichikai="N0000010")
        exception_app = app_row(
            name="植田　隆介", kana="ウエダ　リュウスケ", nichikai="N9905863"
        )
        after_app = app_row(name="後 花子", kana="あと はなこ", nichikai="N0000020")

        merged, unmatched, exc_issues, exc_used = match_students(
            [before, exception_target, after],
            [before_app, exception_app, after_app],
            {"K165": "N9905863"},
        )
        assert unmatched == []
        assert [r["student_number"] for r in merged] == ["K164", "K165", "K166"]

    def test_exception_table_cannot_double_assign_already_matched_nichikai(self):
        normal = client_row(
            student_number="A001", name="通常 太郎", kana="つうじょう たろう"
        )
        normal_app = app_row(
            name="通常 太郎", kana="つうじょう たろう", nichikai="N0000001"
        )
        exception_target = client_row(
            student_number="K165", name="植田 隆介", kana="うえだ りゆうすけ"
        )
        merged, unmatched, exc_issues, exc_used = match_students(
            [normal, exception_target],
            [normal_app],
            {"K165": "N0000001"},
        )
        assert len(merged) == 1  # 通常マッチのみ成功
        assert any("使用済み" in i for i in exc_issues)


class TestValidateRequiredFields:
    def test_all_present_passes(self):
        merged, *_ = match_students([client_row()], [app_row()], {})
        assert validate_required_fields(merged) == []

    def test_missing_nichikai_fails(self):
        merged, *_ = match_students([client_row()], [app_row(nichikai="")], {})
        issues = validate_required_fields(merged)
        assert any("nichikai" in i for i in issues)

    def test_empty_company_office_is_allowed(self):
        merged, *_ = match_students(
            [client_row()], [app_row(company="", office="")], {}
        )
        assert validate_required_fields(merged) == []


class TestValidateGroupMapping:
    def test_known_group_passes(self):
        assert (
            validate_group_mapping([client_row(group="A")], {"A": "入所系居住系"}) == []
        )

    def test_unknown_group_fails(self):
        issues = validate_group_mapping([client_row(group="Z")], {"A": "入所系居住系"})
        assert any("Z" in i for i in issues)


class TestValidateStudentNumberUniqueness:
    def test_unique_passes(self):
        merged = [
            {"student_number": "A001"},
            {"student_number": "A002"},
        ]
        assert validate_student_number_uniqueness(merged) == []

    def test_duplicate_fails(self):
        merged = [
            {"student_number": "A001"},
            {"student_number": "A001"},
        ]
        issues = validate_student_number_uniqueness(merged)
        assert any("A001" in i for i in issues)
