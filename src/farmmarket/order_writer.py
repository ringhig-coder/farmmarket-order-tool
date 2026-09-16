"""업체별 발주요청서 자동 생성 (섹션: 원본 주문 -> 업체별 발주서).

파서(parsers/*)가 '업체가 보낸 파일을 읽는' 역할이라면, 이 모듈은 그 반대로
'우리가 업체에 보낼 파일을 쓰는' 역할이다. 실제로 각 업체에 보내던 엑셀 양식을
그대로 재현해서, 생성된 파일을 그 업체에 보낼 수도 있고 기존 송금요청 계산기에
그대로 다시 넣을 수도 있게 한다 (같은 파서가 읽을 수 있는 형태이므로).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from .config import load_supplier_rules

# 발주서 컬럼 이름 -> 내부 필드 이름. 회사마다 컬럼 구성/순서가 달라서
# config/output_templates.json에 회사별 컬럼 목록만 등록하면 이 매핑으로 채운다.
_COLUMN_FIELD_MAP = {
    "수취인명": "recipient",
    "주문자명": "recipient",
    "수취인연락처1": "phone1",
    "수취인연락처": "phone1",
    "수취인연락처2": "phone2",
    "우편번호": "zipcode",
    "배송지": "address",
    "대신화물택배 도착 영업소": "address",
    "배송메세지": "note",
    "옵션정보": "product_name",
    "상품정보": "product_name",
    "상품 정보": "product_name",
    "구매채널": "channel",
    "수량": "quantity",
}


@dataclass
class GeneratedOrderLine:
    recipient: str | None = None
    phone1: str | None = None
    phone2: str | None = None
    zipcode: str | None = None
    address: str | None = None
    note: str | None = None
    product_name: str = ""
    quantity: float = 0
    channel: str | None = "스토어"


def load_output_templates(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def write_supplier_order_file(
    company: str,
    lines: list[GeneratedOrderLine],
    templates: dict,
    out_path: Path,
    order_date: datetime.date | None = None,
) -> None:
    """실제 업체 양식과 동일한 구조로 발주요청서 엑셀을 만든다."""
    spec = templates.get(company)
    if spec is None:
        raise ValueError(
            f"'{company}'의 출력 양식이 config/output_templates.json에 없습니다. "
            f"임의로 만들지 않고 중단합니다."
        )

    order_date = order_date or datetime.date.today()
    date_str = order_date.strftime("%y/%m/%d")
    title = spec["title"].format(date=date_str)
    columns = spec["columns"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "발주발송관리"

    ws.append([title] + [None] * (len(columns) - 1))
    ws.append(columns)

    for line in lines:
        values = {
            "recipient": line.recipient,
            "phone1": line.phone1,
            "phone2": line.phone2,
            "zipcode": line.zipcode,
            "address": line.address,
            "note": line.note,
            "product_name": line.product_name,
            "quantity": line.quantity,
            "channel": line.channel,
        }
        row = []
        for col_name in columns:
            field = _COLUMN_FIELD_MAP.get(col_name)
            row.append(values.get(field) if field else None)
        ws.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


def default_templates_path(project_root: Path) -> Path:
    return project_root / "config" / "output_templates.json"
