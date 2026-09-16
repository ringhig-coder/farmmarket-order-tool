"""'수취인+옵션정보형' 발주요청서 파서.

예1) 무무식탁_주줌_발주요청서_260914.xlsx, 무무식탁_한칼식품_발주요청서_260914.xlsx,
    무무식탁_밀양한천_발주요청서_260805.xlsx, 무무식탁_하영이네_발주요청서_260915.xlsx
    헤더: 수취인명 | 수취인연락처1 | 수취인연락처2 | (우편번호) | 배송지 | 배송메세지 | 옵션정보 | 수량
예2) 나는농부_신안산업_발주요청서_260803.xlsx, 나는농부_팜마켓_발주요청서_260915.xlsx
    헤더: 수취인명 | 수취인연락처(1) | (구매채널) | 우편번호 | 배송지 | 배송메세지 | 상품(정보|정보) | 수량
1행은 "OO 발주요청서 26/09/14" 같은 제목, 2행이 실제 헤더.
"""
from __future__ import annotations

from pathlib import Path

from ..models import OrderLine, ValidationIssue
from .base import ParseResult, normalize_header

_REQUIRED_BASE = {"수취인명", "배송지", "수량"}
_PRODUCT_KEYS = ["옵션정보", "상품정보"]

_COL_ALIASES = {
    "recipient": ["수취인명"],
    "address": ["배송지"],
    "phone": ["수취인연락처1", "수취인연락처"],
    "quantity": ["수량"],
    "product": _PRODUCT_KEYS,
    "note": ["배송메세지", "배송메모"],
}


def detect_header_row(rows: list[tuple]) -> int | None:
    for idx, row in enumerate(rows[:5]):
        normalized = {normalize_header(v) for v in row if v is not None}
        if not _REQUIRED_BASE.issubset(normalized):
            continue
        if any(key in normalized for key in _PRODUCT_KEYS):
            return idx
    return None


def _find_col(header_row: tuple, keys: list[str]) -> int | None:
    normalized = [normalize_header(v) for v in header_row]
    for key in keys:
        if key in normalized:
            return normalized.index(key)
    return None


def parse(path: Path, rows: list[tuple]) -> ParseResult:
    header_idx = detect_header_row(rows)
    if header_idx is None:
        return ParseResult(format_name="simple_option")

    header_row = rows[header_idx]
    col = {name: _find_col(header_row, aliases) for name, aliases in _COL_ALIASES.items()}

    lines: list[OrderLine] = []
    issues: list[ValidationIssue] = []

    for row in rows[header_idx + 1 :]:
        if col["product"] is None or col["product"] >= len(row):
            continue
        product = row[col["product"]]
        if product in (None, ""):
            continue

        def cell(key: str):
            idx = col.get(key)
            return row[idx] if idx is not None and idx < len(row) else None

        recipient = cell("recipient")
        address = cell("address")

        if recipient in (None, "") and address in (None, ""):
            continue  # 빈 템플릿 행

        raw_qty = cell("quantity")
        try:
            qty = float(raw_qty) if raw_qty not in (None, "") else None
        except (TypeError, ValueError):
            qty = None

        if qty is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="quantity_parse_failed",
                    message=f"'{product}' 상품의 수량을 숫자로 읽을 수 없습니다 (값: {raw_qty!r}).",
                    source_file=path.name,
                    product=str(product),
                )
            )
            continue

        phone = cell("phone")
        note = cell("note")

        lines.append(
            OrderLine(
                source_file=path.name,
                company_hint=None,
                recipient=str(recipient).strip() if recipient else None,
                address=str(address).strip() if address else None,
                phone=str(phone).strip() if phone else None,
                quantity=qty,
                quantity_unit="box",
                product_name_raw=str(product).strip(),
                note=str(note).strip() if note else None,
            )
        )

    return ParseResult(lines=lines, issues=issues, format_name="simple_option")
