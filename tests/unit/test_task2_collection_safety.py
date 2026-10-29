"""
課題②対応の収集側の安全策のテスト。

- 課題①・②の提出記録タブは作成時に非表示、それ以外は表示のまま(サブ講師の誤操作防止)
- 課題名の部分一致で候補が複数あるときは、最初の候補を黙って選ばず中断する
- ダウンロードの一時保存先はリクエストごとに分け、同名ファイルの並行処理で衝突しない
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, "src")


# --- 提出記録タブの非表示 -----------------------------------------------------


@pytest.fixture
def sheets_service():
    with patch("sheets_service.default") as mock_default, patch(
        "sheets_service.build"
    ) as mock_build:
        mock_default.return_value = (Mock(), "test-project")
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from sheets_service import SheetsService

        yield SheetsService(), mock_service


def _created_properties(mock_service):
    body = mock_service.spreadsheets.return_value.batchUpdate.call_args.kwargs["body"]
    return body["requests"][0]["addSheet"]["properties"]


@pytest.mark.parametrize("sheet_name", ["課題①", "課題②"])
def test_task_tabs_are_created_hidden(sheets_service, sheet_name):
    service, mock_service = sheets_service
    mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": []
    }

    service._ensure_sheet_exists("sheet-id", sheet_name)

    assert _created_properties(mock_service) == {"title": sheet_name, "hidden": True}


def test_other_tabs_are_created_visible(sheets_service):
    service, mock_service = sheets_service
    mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": []
    }

    service._ensure_sheet_exists("sheet-id", "課題③")

    assert _created_properties(mock_service) == {"title": "課題③"}


def test_existing_tab_is_not_recreated(sheets_service):
    service, mock_service = sheets_service
    mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "課題②"}}]
    }

    service._ensure_sheet_exists("sheet-id", "課題②")

    mock_service.spreadsheets.return_value.batchUpdate.assert_not_called()


# --- 課題の選択 ----------------------------------------------------------------


@pytest.fixture
def engine():
    from playwright_automation import PlaywrightAutomationEngine

    e = PlaywrightAutomationEngine(class_name="クラス", task_id="課題②")
    e._wait_for_navigation = Mock()
    return e


def _frame(match_count):
    frame = MagicMock()
    frame.locator.return_value.count.return_value = match_count
    return frame


def test_select_task_returns_false_when_no_candidate(engine):
    engine._find_frame_with_selector = Mock(return_value=None)

    assert engine._select_task("課題②") is False


def test_select_task_clicks_the_single_candidate(engine):
    frame = _frame(1)
    engine.page = Mock(frames=[frame])
    engine._find_frame_with_selector = Mock(return_value=frame)

    assert engine._select_task("課題②") is True

    frame.click.assert_called_once_with("text=課題②")


def test_select_task_aborts_when_candidates_are_ambiguous(engine):
    frame = _frame(2)
    engine.page = Mock(frames=[frame])
    engine._find_frame_with_selector = Mock(return_value=frame)

    with pytest.raises(Exception, match="複数"):
        engine._select_task("課題②")

    frame.click.assert_not_called()


def test_select_task_counts_candidates_across_frames(engine):
    first, second = _frame(1), _frame(1)
    engine.page = Mock(frames=[first, second])
    engine._find_frame_with_selector = Mock(return_value=first)

    with pytest.raises(Exception, match="複数"):
        engine._select_task("課題②")

    first.click.assert_not_called()


# --- ダウンロードの一時保存先 -------------------------------------------------


def _download_with(engine, filename):
    """download_file を、保存先だけを記録するモックの download で実行する。"""
    saved = {}

    def save_as(path):
        saved["path"] = path
        with open(path, "wb") as f:
            f.write(b"x")

    download = Mock(save_as=save_as)
    ctx = MagicMock()
    ctx.__enter__.return_value.value = download
    frame = MagicMock()
    frame.name = "dummy"
    engine.page = MagicMock(frames=[frame])
    engine.page.expect_download.return_value = ctx
    engine.page.goto = Mock()
    engine._wait_for_navigation = Mock()
    path = engine.download_file("download.aspx?id=1", filename, "detail.aspx?id=1")
    return path, saved


def test_download_paths_are_unique_per_request_for_same_filename():
    from playwright_automation import PlaywrightAutomationEngine, remove_download

    paths = []
    try:
        for _ in range(2):
            e = PlaywrightAutomationEngine(class_name="クラス", task_id="課題②")
            path, _saved = _download_with(e, "report.pdf")
            paths.append(path)

        assert paths[0] != paths[1]
        assert all(os.path.basename(p) == "report.pdf" for p in paths)
        assert all(os.path.exists(p) for p in paths)
    finally:
        for p in paths:
            remove_download(p)


def test_remove_download_deletes_only_its_own_directory():
    from playwright_automation import PlaywrightAutomationEngine, remove_download

    a, _ = _download_with(PlaywrightAutomationEngine(task_id="課題①"), "same.pdf")
    b, _ = _download_with(PlaywrightAutomationEngine(task_id="課題②"), "same.pdf")

    remove_download(a)

    assert not os.path.exists(a)
    assert not os.path.exists(os.path.dirname(a))
    assert os.path.exists(b)  # 相手のファイルは消えない
    remove_download(b)
    assert not os.path.exists(b)


def test_remove_download_never_removes_tmp_itself(tmp_path):
    from playwright_automation import remove_download

    outsider = tmp_path / "keep.txt"
    outsider.write_text("x")

    remove_download(
        str(outsider)
    )  # 接頭辞のないディレクトリは削除せず、ファイルだけ消す

    assert not outsider.exists()
    assert tmp_path.exists()
