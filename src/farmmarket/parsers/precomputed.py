"""'사전계산형' 발주요청서 파서.

예: 이웅식품_무무식탁_발주요청서_260916.xlsx
업체가 단가/합계/배송비를 직접 계산해서 보내주는 포맷.
파일에 적힌 숫자를 그대로 믿지 않고, 나중에 engine 단계에서 마스터 값과 대조해 검증한다.
"""
from __future__ import annotations

from pathlib import Path

from ..models import OrderLine, ValidationIssue
from .base import ParseResult, normalize_header

_REQUIRED_HEADERS = {"주문상품명", "단가A", "수량B", "배송비D"}

_COL_ALIASES = {
    "recipient": ["수령자"],
    "phone": ["수령자연락처"],
    "address": ["수령지주소"],
    "note": ["배송메모"],
    "product": ["주문상품명"],
    "unit_price": ["단가A"],
    "quantity": ["수량B"],
    "shipping_fee": ["배송비D"],
    "grand_total": ["합계C+D"],
}


def detect_header_row(rows: list[tuple]) -> int | None:
    for idx, row in enumerate(rows[:5]):
        normalized = {normalize_header(v) for v in row if v is not None}
        if _REQUIRED_HEADERS.issubset(normalized):
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
        return ParseResult(format_name="precomputed")

    header_row = rows[header_idx]
    col = {name: _find_col(header_row, aliases) for name, aliases in _COL_ALIASES.items()}

    lines: list[OrderLine] = []
    issues: list[ValidationIssue] = []

    for row in rows[header_idx + 1 :]:
        product = row[col["product"]] if col["product"] is not None and col["product"] < len(row) else None
        if product in (None, ""):
            continue

        def cell(key: str):
            idx = col.get(key)
            return row[idx] if idx is not None and idx < len(row) else None

        qty = _num(cell("quantity"))
        if qty is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="quantity_parse_failed",
                    message=f"'{product}' 상품의 수량을 숫자로 읽을 수 없습니다.",
                    source_file=path.name,
                    product=str(product),
                )
            )
            continue

        recipient = cell("recipient")
        address = cell("address")
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
                quantity_unit="unit",
                product_name_raw=str(product).strip(),
                note=str(note).strip() if note else None,
                declared_unit_price=_num(cell("unit_price")),
                declared_shipping_fee=_num(cell("shipping_fee")),
                declared_total=_num(cell("grand_total")),
            )
        )

    return ParseResult(lines=lines, issues=issues, format_name="precomputed")
