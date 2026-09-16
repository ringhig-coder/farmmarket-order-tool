"""'원본 라인아이템형' 발주요청서 파서.

플랫폼에서 내려받은 배송/주문 리스트 형태. 한 행 = 수취인 한 명에게 보낼 상품 한 종류.
수량은 그 상품(박스/팩) 단위 그대로다 (예: '더 맛난 반시 고구마 말랭이 60g x 10봉' 수량=1 은 그 팩 1개).

예1) 무무식탁_다모식품_발주요청서_260914.xlsx:
    우편번호 | 주소 | 상품명 | 수량 | 수령자명 | 수령자연락처1 | 수령자연락처2 | 주문자 | ...
예2) 무무식탁 26.09.16.xlsx:
    운송장번호 | 주문번호 | 수하인명 | 수하인기본주소 | 수량 | 상품명 | 특기사항 | 고객메시지
"""
from __future__ import annotations

from pathlib import Path

from ..models import OrderLine, ValidationIssue
from .base import ParseResult, normalize_header

_REQUIRED_HEADERS = {"상품명", "수량"}
_RECIPIENT_KEYS = ["수령자명", "수하인명"]

_COL_ALIASES = {
    "recipient": _RECIPIENT_KEYS,
    "address": ["주소", "수하인기본주소"],
    "phone": ["수령자연락처1", "수하인전화번호", "수하인연락처"],
    "quantity": ["수량"],
    "product": ["상품명"],
    "note": ["배송메모", "특기사항", "고객메시지"],
}


def detect_header_row(rows: list[tuple]) -> int | None:
    for idx, row in enumerate(rows[:5]):
        normalized = {normalize_header(v) for v in row if v is not None}
        if not _REQUIRED_HEADERS.issubset(normalized):
            continue
        if any(key in normalized for key in _RECIPIENT_KEYS):
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
        return ParseResult(format_name="raw_line_item")

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
            # 수취인/주소가 전혀 없는 빈 템플릿 행 (엑셀 드롭다운으로 상품명만 남아있는 경우) - 실제 주문 아님
            continue

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

    return ParseResult(lines=lines, issues=issues, format_name="raw_line_item")
