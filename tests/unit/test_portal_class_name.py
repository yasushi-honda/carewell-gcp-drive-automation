"""
ポータル(study.jp)上のクラス名が、システム内部のクラス名と異なるクラスの扱い。

背景: №08・10はポータル上の名称に接尾辞が付く（№08（山形県対象）／№10（短縮版））。
収集コードはクラスを完全一致(`text="..."`)で選ぶため、内部名のままだと見つからず
「未作成」と誤判定されていた(2026-11-14、Playwrightでポータルを直接確認して判明)。
内部名(Firestoreキー・Drive・Dashboardで使用)は変えず、ポータルで選ぶ時だけ別名を引く。
"""

import sys
from unittest.mock import MagicMock

sys.path.insert(0, "src")

from config import classes as classes_config  # noqa: E402
from playwright_automation import PlaywrightAutomationEngine  # noqa: E402

PREFIX = "令和8年度 デジタル中核人材養成研修 "


class TestResolvePortalClassName:
    def test_class08_resolves_to_portal_name_with_suffix(self):
        assert (
            classes_config.resolve_portal_class_name(f"{PREFIX}№08")
            == f"{PREFIX}№08（山形県対象）"
        )

    def test_class10_resolves_to_portal_name_with_suffix(self):
        assert (
            classes_config.resolve_portal_class_name(f"{PREFIX}№10")
            == f"{PREFIX}№10（短縮版）"
        )

    def test_unregistered_classes_are_returned_unchanged(self):
        for num in ("01", "02", "03", "04", "05", "06", "07", "09"):
            name = f"{PREFIX}№{num}"
            assert classes_config.resolve_portal_class_name(name) == name

    def test_unknown_name_is_returned_unchanged(self):
        assert classes_config.resolve_portal_class_name("別のクラス") == "別のクラス"

    def test_aliases_only_for_known_classes(self):
        # 対応表のキー(内部名)は、必ず KNOWN_CLASSES に存在する
        for internal in classes_config.PORTAL_CLASS_NAME_ALIASES:
            assert internal in classes_config.KNOWN_CLASSES

    def test_alias_is_not_a_prefix_collision_between_classes(self):
        # 別名が他クラスの内部名や別名と重複しない(誤って別クラスを選ばない)
        values = list(classes_config.PORTAL_CLASS_NAME_ALIASES.values())
        assert len(values) == len(set(values))
        assert not set(values) & set(classes_config.KNOWN_CLASSES)


class TestSelectClassUsesPortalName:
    def _engine(self):
        engine = PlaywrightAutomationEngine()
        engine._click_in_any_frame = MagicMock(return_value=True)
        engine._wait_for_navigation = MagicMock()
        return engine

    def test_aliased_class_is_selected_by_portal_name(self):
        engine = self._engine()
        assert engine._select_class(f"{PREFIX}№08") is True
        selector = engine._click_in_any_frame.call_args[0][0]
        assert selector == f'text="{PREFIX}№08（山形県対象）"'

    def test_regular_class_is_still_selected_by_exact_name(self):
        engine = self._engine()
        assert engine._select_class(f"{PREFIX}№07") is True
        selector = engine._click_in_any_frame.call_args[0][0]
        assert selector == f'text="{PREFIX}№07"'

    def test_not_found_returns_false(self):
        engine = self._engine()
        engine._click_in_any_frame.return_value = False
        assert engine._select_class(f"{PREFIX}№08") is False
        engine._wait_for_navigation.assert_not_called()
