"""송금 요청 텍스트 생성 (섹션 11, 12, 13).

무무식탁/나는농부 정산금액은 절대 출력하지 않는다. 업체 송금 요청만 만든다.
"""
from __future__ import annotations

import re

from .config import SupplierRules
from .master import SELF_SUPPLY_SHEET
from .models import SupplierResult

# 섹션 10~11에서 지정된, 사이즈별 묶음("60*6+100*4")으로 보여주는 특수 표기 업체.
# 상품 단가 계산 로직과는 무관한 '표시 방식'만 다루는 설정이라 하드코딩해도 안전하지만,
# 새 업체를 추가해야 하면 이 dict만 늘리면 된다.
SWEET_POTATO_LABELS: dict[str, str] = {
    "다모식품": "고구마 말랭이1",
    "주줌": "고구마 말랭이2",
    "해남고구마식품": "고구마 말랭이3",
}

_SIZE_RE = re.compile(r"(\d+)\s*g")


def _fmt_money(v: float) -> str:
    return f"{round(v):,}"


def _sweet_potato_line(result: SupplierResult) -> str:
    label = SWEET_POTATO_LABELS[result.company]
    total_qty = sum(item.quantity for item in result.breakdown)

    size_totals: dict[str, float] = {}
    for item in result.breakdown:
        m = _SIZE_RE.search(item.product_name)
        size_key = m.group(1) if m else item.product_name
        size_totals[size_key] = size_totals.get(size_key, 0) + item.quantity

    qty_str = f"{round(total_qty)}" if float(total_qty).is_integer() else f"{total_qty}"
    parts = [f"{label} ({qty_str})"]

    if len(size_totals) > 1:
        breakdown_str = "+".join(
            f"{size}*{round(qty) if float(qty).is_integer() else qty}" for size, qty in size_totals.items()
        )
        parts.append(f"({breakdown_str})")

    if result.shipment_count:
        parts.append(f"{result.shipment_count}명")
    if result.shipping_fee_per_shipment:
        parts.append(f"{round(result.shipping_fee_per_shipment)}")

    return " ".join(parts)


def _generic_lines(result: SupplierResult) -> list[str]:
    lines = []
    for item in result.breakdown:
        qty_str = f"{round(item.quantity)}" if float(item.quantity).is_integer() else f"{item.quantity}"
        lines.append(f"{item.product_name} ({qty_str})")
    return lines


def format_supplier_block(result: SupplierResult) -> str:
    """업체 하나에 대한 상품/계좌/금액 블록 (섹션 12 형식)."""
    lines: list[str] = []

    if result.company in SWEET_POTATO_LABELS and not result.is_self_supply:
        lines.append(_sweet_potato_line(result))
    else:
        lines.extend(_generic_lines(result))
        if not result.is_self_supply and result.shipment_count:
            shipping = f"{round(result.shipping_fee_per_shipment)}" if result.shipping_fee_per_shipment else ""
            lines.append(f"{result.shipment_count}명 {shipping}".strip())

    lines.append(result.account or "⚠ 계좌번호 미확인")
    lines.append(f"{_fmt_money(result.grand_total)}원")
    return "\n".join(lines)


def build_remittance_message(results: dict[str, SupplierResult], rules: SupplierRules) -> str:
    """카카오톡 등에 붙여넣을 최종 송금 요청 메시지 전체를 만든다."""
    mumu_blocks = []
    self_supply_blocks = []

    for company, result in results.items():
        if not result.is_valid:
            continue
        block = format_supplier_block(result)
        if result.source_sheet == SELF_SUPPLY_SHEET:
            self_supply_blocks.append(block)
        else:
            mumu_blocks.append(block)

    sections: list[str] = []
    if mumu_blocks:
        sections.append("안녕하세요.\n하기 주문건 송금 부탁드립니다!\n\n" + "\n\n".join(mumu_blocks))
    if self_supply_blocks:
        sections.append("[나는농부] 발주 확인 부탁드립니다!\n\n" + "\n\n".join(self_supply_blocks))

    return "\n\n".join(sections)
