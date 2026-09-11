"""
Unit tests for scripts/merge_student_roster.py の純粋関数(正規化・突合・検証ゲート)。

ネットワーク呼び出しを含まない。境界値(重複あり/なし、欠損あり/なし、
未知グループ、例外テーブル適用あり/なし)を中心に検証する。
"""

import sys

sys.path.insert(0, "scripts")

from merge_student_roster import (  # noqa: E402
    APPLICATION_HEADER_PREFIX,
    CLIENT_SOURCE_HEADER,
    ValidationError,
    _find_key_duplicates,
    _rstrip_blank_rows,
    match_students,
    normalize_key,
    parse_application_data,
    parse_client_source,
    validate_expected_count,
    validate_group_mapping,
    validate_nichikai_uniqueness,
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


APPLICATION_FULL_HEADER = APPLICATION_HEADER_PREFIX + [
    "会員番号",
    "所属都道府県会",
    "所属部門",
    "E-mail①",
    "E-mail②",
    "送付先郵便番号",
    "送付先住所",
    "勤務先法人名称",
    "勤務先名称",
]


class TestParseClientSource:
    def test_valid_row_is_parsed(self):
        rows = [
            CLIENT_SOURCE_HEADER,
            ["A", "先生", "A001", "山田 太郎", "やまだ たろう", "介護老人保健施設", ""],
        ]
        parsed = parse_client_source(rows, "テスト")
        assert parsed == [
            {
                "group": "A",
                "sub_teacher": "先生",
                "student_number": "A001",
                "name": "山田 太郎",
                "kana": "やまだ たろう",
                "service_type": "介護老人保健施設",
            }
        ]

    def test_completely_blank_row_is_skipped(self):
        rows = [
            CLIENT_SOURCE_HEADER,
            ["A", "先生", "A001", "山田 太郎", "やまだ たろう", "介護老人保健施設", ""],
            ["", "", "", "", "", "", ""],
        ]
        parsed = parse_client_source(rows, "テスト")
        assert len(parsed) == 1

    def test_partially_filled_row_raises(self):
        # 受講者番号・グループはあるが氏名が空(取得漏れ等)は異常系として検知する
        rows = [
            CLIENT_SOURCE_HEADER,
            ["A", "先生", "A001", "", "", "介護老人保健施設", ""],
        ]
        try:
            parse_client_source(rows, "テスト")
            assert False, "ValidationErrorが送出されるべき"
        except ValidationError as e:
            assert "部分的" in str(e)

    def test_header_mismatch_raises(self):
        rows = [["不正な", "ヘッダー"]]
        try:
            parse_client_source(rows, "テスト")
            assert False, "ValidationErrorが送出されるべき"
        except ValidationError:
            pass

    def test_empty_input_raises(self):
        try:
            parse_client_source([], "テスト")
            assert False, "ValidationErrorが送出されるべき"
        except ValidationError:
            pass


class TestParseApplicationData:
    def test_valid_row_is_parsed(self):
        rows = [
            APPLICATION_FULL_HEADER,
            [
                "山田 太郎",
                "やまだ たろう",
                "N0000001",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "社会福祉法人テスト会",
                "テスト施設",
            ],
        ]
        parsed = parse_application_data(rows, "テスト")
        assert parsed == [
            {
                "name": "山田 太郎",
                "kana": "やまだ たろう",
                "nichikai": "N0000001",
                "company": "社会福祉法人テスト会",
                "office": "テスト施設",
            }
        ]

    def test_completely_blank_row_is_skipped(self):
        rows = [
            APPLICATION_FULL_HEADER,
            [
                "山田 太郎",
                "やまだ たろう",
                "N0000001",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "社会福祉法人テスト会",
                "テスト施設",
            ],
            [""] * 12,
        ]
        parsed = parse_application_data(rows, "テスト")
        assert len(parsed) == 1

    def test_empty_company_and_office_is_allowed(self):
        # company/officeは申込データ原本にも空欄がありうる正当なデータ
        rows = [
            APPLICATION_FULL_HEADER,
            [
                "山田 太郎",
                "やまだ たろう",
                "N0000001",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ],
        ]
        parsed = parse_application_data(rows, "テスト")
        assert parsed[0]["company"] == ""
        assert parsed[0]["office"] == ""

    def test_partially_filled_row_raises(self):
        # 氏名はあるが日介番号が空(取得漏れ等)は異常系として検知する
        rows = [
            APPLICATION_FULL_HEADER,
            ["山田 太郎", "やまだ たろう", "", "", "", "", "", "", "", "", ""],
        ]
        try:
            parse_application_data(rows, "テスト")
            assert False, "ValidationErrorが送出されるべき"
        except ValidationError as e:
            assert "部分的" in str(e)

    def test_company_office_column_mismatch_raises(self):
        bad_header = APPLICATION_HEADER_PREFIX + [""] * 7 + ["違う列", "違う列2"]
        rows = [bad_header]
        try:
            parse_application_data(rows, "テスト")
            assert False, "ValidationErrorが送出されるべき"
        except ValidationError as e:
            assert "会社/事業所列" in str(e)

    def test_header_prefix_mismatch_raises(self):
        rows = [["不正な", "ヘッダー"]]
        try:
            parse_application_data(rows, "テスト")
            assert False, "ValidationErrorが送出されるべき"
        except ValidationError:
            pass


class TestFindKeyDuplicates:
    def test_no_duplicates_passes(self):
        rows = [
            client_row(),
            client_row(student_number="A002", name="佐藤 花子", kana="さとう はなこ"),
        ]
        assert _find_key_duplicates(rows, "テスト") == []

    def test_duplicate_key_within_rows_fails(self):
        rows = [
            client_row(student_number="A001"),
            client_row(student_number="A002"),  # 同じ氏名+ふりがな
        ]
        issues = _find_key_duplicates(rows, "テスト")
        assert len(issues) == 1
        assert "テスト" in issues[0]


class TestValidateNichikaiUniqueness:
    def test_no_duplicate_nichikai_passes(self):
        merged = [
            {"student_number": "A001", "nichikai": "N0000001"},
            {"student_number": "A002", "nichikai": "N0000002"},
        ]
        assert validate_nichikai_uniqueness(merged) == []

    def test_duplicate_nichikai_across_different_students_fails(self):
        # 氏名+ふりがなキーは別でも、申込データ側の日介番号自体が重複していれば
        # 2名が同一日介番号にマッピングされうる(_find_key_duplicatesでは検出不可)
        merged = [
            {"student_number": "A001", "nichikai": "N0000001"},
            {"student_number": "A002", "nichikai": "N0000001"},
        ]
        issues = validate_nichikai_uniqueness(merged)
        assert len(issues) == 1
        assert "A001" in issues[0] and "A002" in issues[0]


class TestRstripBlankRows:
    def test_trailing_blank_rows_are_removed(self):
        rows = [["a", "b"], ["c", "d"], ["", ""], ["", ""]]
        assert _rstrip_blank_rows(rows) == [["a", "b"], ["c", "d"]]

    def test_non_trailing_blank_row_is_preserved(self):
        # 途中の空行は除去対象ではない(末尾のみが対象)
        rows = [["a", "b"], ["", ""], ["c", "d"]]
        assert _rstrip_blank_rows(rows) == rows

    def test_all_blank_rows_become_empty_list(self):
        rows = [["", ""], ["", ""]]
        assert _rstrip_blank_rows(rows) == []

    def test_no_blank_rows_is_unchanged(self):
        rows = [["a", "b"], ["c", "d"]]
        assert _rstrip_blank_rows(rows) == rows

    def test_empty_input_returns_empty(self):
        assert _rstrip_blank_rows([]) == []


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

    def test_ambiguous_direct_match_is_unmatched_not_arbitrarily_paired(self):
        # 申込データ側に同一正規化キー(氏名+ふりがな)を持つ行が2件以上ある場合、
        # どちらかを勝手に選ばず未突合として扱う(誤った日介番号を割り当てない)
        c = client_row(student_number="A001", name="山田 太郎", kana="やまだ たろう")
        dup_a = app_row(name="山田 太郎", kana="やまだ たろう", nichikai="N0000001")
        dup_b = app_row(name="山田 太郎", kana="やまだ たろう", nichikai="N0000002")
        merged, unmatched, exc_issues, exc_used = match_students(
            [c], [dup_a, dup_b], {}
        )
        assert merged == []
        assert unmatched == ["A001"]

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
