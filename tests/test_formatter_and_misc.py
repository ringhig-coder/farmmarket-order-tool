from pathlib import Path

from farmmarket.formatter import _fmt_money
from farmmarket.pipeline import DuplicateFileTracker


def test_money_formatting_uses_thousand_separator():
    assert _fmt_money(136500) == "136,500"
    assert _fmt_money(9000) == "9,000"
    assert _fmt_money(0) == "0"


def test_duplicate_file_tracker(tmp_path):
    tracker = DuplicateFileTracker()
    path = tmp_path / "dummy.xlsx"
    path.write_bytes(b"content")
    assert tracker.is_duplicate(path) is False
    assert tracker.is_duplicate(path) is True  # 같은 파일 두 번째는 중복


def test_filename_hint_extraction(rules):
    from farmmarket.filename_hint import extract_company_hint

    assert extract_company_hint("무무식탁_해남고구마식품_발주요청서_260916.xlsx", rules) == "해남고구마식품"
    assert extract_company_hint("이웅식품_무무식탁_발주요청서_260916.xlsx", rules) == "이웅식품"
    assert extract_company_hint("무무식탁 26.09.16.xlsx", rules) is None
