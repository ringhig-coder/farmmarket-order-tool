"""동일 배송지 판단 (섹션 9).

같은 수취인 + 같은 주소면 같은 배송지로 보고 배송비를 한 번만 계산한다.
주소/수취인 정보가 불완전하면 억지로 합치지 않고 별도 배송지로 두되 경고를 남긴다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import OrderLine, ValidationIssue


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", "", str(text)).strip()


@dataclass
class ShipmentGroup:
    key: str
    recipient: str | None
    address: str | None
    lines: list[OrderLine] = field(default_factory=list)


def group_into_shipments(lines: list[OrderLine]) -> tuple[list[ShipmentGroup], list[ValidationIssue]]:
    """수취인+주소가 같은 라인들을 하나의 배송지로 묶는다."""
    groups: dict[str, ShipmentGroup] = {}
    order: list[str] = []
    issues: list[ValidationIssue] = []
    incomplete_counter = 0

    for line in lines:
        recipient_norm = _normalize(line.recipient)
        address_norm = _normalize(line.address)

        if not recipient_norm or not address_norm:
            incomplete_counter += 1
            key = f"__incomplete_{incomplete_counter}"
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="incomplete_address",
                    message=(
                        f"수취인 또는 주소 정보가 없어 다른 주문과 배송지를 합치지 않고 "
                        f"별도 배송지로 처리했습니다. (수취인={line.recipient or '없음'})"
                    ),
                    source_file=line.source_file,
                    product=line.product_name_raw,
                )
            )
        else:
            key = f"{recipient_norm}|{address_norm}"

        if key not in groups:
            groups[key] = ShipmentGroup(key=key, recipient=line.recipient, address=line.address)
            order.append(key)
        groups[key].lines.append(line)

    return [groups[k] for k in order], issues
