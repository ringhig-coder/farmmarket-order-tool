"""'박스수량형' 발주요청서 파서.

예1) 무무식탁_해남고구마식품_발주요청서_260916.xlsx
    받는분성명 | 받는분주소(전체, 분할) | 받는분전화번호 | 받는분기타연락처 | 박스수량 | 품목명 | 배송메모 | 구매자명
예2) 무무식탁_현미왕_발주요청서_260915.xlsx (수량 컬럼명과 기본운임 컬럼이 다름)
    받는분 성명 | 받는분전화번호 | 받는분기타연락처 | 받는분주소(전체, 분할) | 품목명 | 수량 | 기본운임 | 배송메세지
"""
from __future__ import annotations

from pathlib import Path

from ..models import OrderLine, ValidationIssue
from .base import ParseResult, normalize_bong_pack, normalize_header

_REQUIRED_BASE = {"받는분성명", "품목명"}
_QUANTITY_KEYS = ["박스수량", "수량"]

_COL_ALIASES = {
    "recipient": ["받는분성명"],
    "address": ["받는분주소(전체,분할)", "받는분주소"],
    "phone": ["받는분전화번호"],
    "quantity": _QUANTITY_KEYS,
    "product": ["품목명"],
    "note": ["배송메모", "배송메세지"],
    "shipping_fee": ["기본운임"],
}


def detect_header_row(rows: list[tuple]) -> int | None:
    for idx, row in enumerate(rows[:5]):
        normalized = {normalize_header(v) for v in row if v is not None}
        if not _REQUIRED_BASE.issubset(normalized):
            continue
        if any(key in normalized for key in _QUANTITY_KEYS):
            return idx
    return None


def _find_col(header_row: tuple, keys: list[str]) -> int | None:
    normalized = [normalize_header(v) for v in header_row]
    for key in keys:
        if key in normalized:
            return normalized.index(key)
    return None


def _num(v: object) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse(path: Path, rows: list[tuple]) -> ParseResult:
    header_idx = detect_header_row(rows)
    if header_idx is None:
        return ParseResult(format_name="box_quantity")

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

        phone = cell("phone")
        note = cell("note")
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
                    message=f"'{product}' 상품의 박스수량을 숫자로 읽을 수 없습니다 (값: {raw_qty!r}).",
                    source_file=path.name,
                    product=str(product),
                )
            )
            continue

        product_name = str(product).strip()
        normalized_name, normalized_qty, bong_error = normalize_bong_pack(product_name, qty)
        if bong_error:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="bong_pack_not_multiple_of_ten",
                    message=bong_error,
                    source_file=path.name,
                    product=product_name,
                )
            )
            continue

        lines.append(
            OrderLine(
                source_file=path.name,
                company_hint=None,
                recipient=str(recipient).strip() if recipient else None,
                address=str(address).strip() if address else None,
                phone=str(phone).strip() if phone else None,
                quantity=normalized_qty,
                quantity_unit="box",
                product_name_raw=normalized_name,
                note=str(note).strip() if note else None,
                declared_shipping_fee=_num(cell("shipping_fee")),
            )
        )

    return ParseResult(lines=lines, issues=issues, format_name="box_quantity")
