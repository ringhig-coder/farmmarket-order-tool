from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from ..models import OrderLine, ValidationIssue


def normalize_header(v: object) -> str:
    if v is None:
        return ""
    return str(v).replace(" ", "").replace("\n", "").strip()


_BONG_PACK_RE = re.compile(r"(\d+)\s*g\s*[x×]\s*(\d+)\s*봉")


def normalize_bong_pack(raw_name: str, quantity: float) -> tuple[str, float, str | None]:
    """'...60g x 20봉' 같은 표기를 '...60g x 10봉' 기준 수량으로 환산한다.

    다모식품 등 고구마 말랭이류는 실제 발주/정산이 항상 10봉 단위로 이뤄지기 때문에,
    상품명에 20봉/30봉/40봉처럼 다른 포장 단위가 찍혀 있어도 10봉 몇 개인지로 바꿔서 계산한다.
    10의 배수가 아니면(예: 15봉) 임의로 환산하지 않고 오류로 알린다.
    반환값: (환산된 상품명, 환산된 수량, 오류 메시지 또는 None)
    """
    m = _BONG_PACK_RE.search(raw_name)
    if not m:
        return raw_name, quantity, None

    size, bong = m.group(1), int(m.group(2))
    if bong % 10 != 0:
        return (
            raw_name,
            quantity,
            f"'{raw_name}'의 포장 단위({bong}봉)가 10의 배수가 아니라 10봉 기준으로 자동 환산할 수 없습니다.",
        )

    normalized_name = _BONG_PACK_RE.sub(f"{size}g x 10봉", raw_name, count=1)
    multiplier = bong // 10
    return normalized_name, quantity * multiplier, None


def read_all_sheets(path: Path) -> dict[str, list[tuple]]:
    """xlsx/xlsm -> openpyxl. xls -> xlrd. 시트명 -> 행 리스트(튜플)로 반환."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(path, data_only=True)
        result = {}
        for sn in wb.sheetnames:
            ws = wb[sn]
            result[sn] = [
                tuple(row) for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)
            ]
        wb.close()
        return result
    if suffix == ".xls":
        import xlrd

        wb = xlrd.open_workbook(str(path))
        result = {}
        for sheet in wb.sheets():
            rows = []
            for r in range(sheet.nrows):
                rows.append(tuple(sheet.cell_value(r, c) for c in range(sheet.ncols)))
            result[sheet.name] = rows
        return result
    raise ValueError(f"지원하지 않는 파일 형식입니다: {path.suffix} ({path.name})")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class ParseResult:
    lines: list[OrderLine] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    format_name: str = "unknown"
