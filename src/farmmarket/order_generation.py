"""원본 주문(OrderLine) -> 업체별 발주요청서 파일 생성까지의 핵심 로직.

네트워크 호출(네이버/쿠팡/카페24 API)과 분리해서 테스트 가능하게 만든 부분.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path

from .config import SupplierRules
from .engine import resolve_line_product
from .master import SELF_SUPPLY_SHEET, MasterCatalog
from .models import OrderLine, ValidationIssue
from .order_writer import GeneratedOrderLine, write_supplier_order_file


@dataclass
class GenerationReport:
    files_written: list[Path] = field(default_factory=list)
    unmatched_products: list[ValidationIssue] = field(default_factory=list)
    no_template_companies: dict[str, int] = field(default_factory=dict)

    @property
    def has_unhandled(self) -> bool:
        return bool(self.unmatched_products) or bool(self.no_template_companies)


def generate_supplier_orders(
    lines: list[OrderLine],
    catalog: MasterCatalog,
    rules: SupplierRules,
    templates: dict,
    out_dir: Path,
    order_date: datetime.date | None = None,
) -> GenerationReport:
    order_date = order_date or datetime.date.today()
    report = GenerationReport()

    by_company: dict[str, list[GeneratedOrderLine]] = {}
    company_sheet: dict[str, str] = {}

    for line in lines:
        product, issues = resolve_line_product(line, catalog, rules)
        if product is None:
            report.unmatched_products.extend(issues)
            continue

        if product.company not in templates:
            report.no_template_companies[product.company] = report.no_template_companies.get(product.company, 0) + 1
            continue

        company_sheet[product.company] = product.sheet
        gen_line = GeneratedOrderLine(
            recipient=line.recipient,
            phone1=line.phone,
            address=line.address,
            note=line.note,
            product_name=product.product_name,
            quantity=line.quantity,
            channel="스토어",
        )
        by_company.setdefault(product.company, []).append(gen_line)

    date_str = order_date.strftime("%y%m%d")
    date_folder = out_dir / f"발주서_{date_str}"
    for company, gen_lines in by_company.items():
        prefix = "나는농부" if company_sheet[company] == SELF_SUPPLY_SHEET else "무무식탁"
        out_path = date_folder / f"{prefix}_{company}_발주요청서_{date_str}.xlsx"
        write_supplier_order_file(company, gen_lines, templates, out_path, order_date=order_date)
        report.files_written.append(out_path)

    return report
