from __future__ import annotations

from pathlib import Path

from ..models import ValidationIssue
from . import box_quantity, precomputed, raw_line_item, simple_option
from .base import ParseResult, read_all_sheets

_PARSERS = [box_quantity, precomputed, simple_option, raw_line_item]


def parse_order_file(path: Path) -> ParseResult:
    try:
        sheets = read_all_sheets(path)
    except Exception as exc:  # noqa: BLE001 - 파일 자체를 못 여는 경우
        return ParseResult(
            issues=[
                ValidationIssue(
                    severity="error",
                    code="file_read_failed",
                    message=f"파일을 열 수 없습니다: {exc}",
                    source_file=path.name,
                )
            ],
            format_name="unreadable",
        )

    for sheet_name, rows in sheets.items():
        for parser_module in _PARSERS:
            header_idx = parser_module.detect_header_row(rows)
            if header_idx is not None:
                result = parser_module.parse(path, rows)
                if result.lines:
                    return result

    return ParseResult(
        issues=[
            ValidationIssue(
                severity="error",
                code="unrecognized_format",
                message=(
                    "이 파일의 양식을 인식할 수 없습니다. 업체별로 이미 나뉜 발주요청서인지, "
                    "형식이 알려진 양식과 다른지 확인이 필요합니다."
                ),
                source_file=path.name,
            )
        ],
        format_name="unrecognized",
    )
