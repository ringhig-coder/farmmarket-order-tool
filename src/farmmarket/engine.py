"""핵심 계산 엔진: 발주 라인 -> 업체별 송금 결과.

절대 하지 않는 것:
- 마스터에서 찾을 수 없는 상품/업체를 추측해서 계산하지 않는다 (에러로 중단).
- 공급가/배송비가 없는데 임의의 기본값을 넣지 않는다.
"""
from __future__ import annotations

from .config import SupplierRules
from .dedup import group_into_shipments
from .master import SELF_SUPPLY_SHEET, MasterCatalog, MasterProduct
from .models import OrderLine, ProductBreakdownItem, SupplierResult, ValidationIssue

_PRICE_TOLERANCE = 0.5


def resolve_line_product(
    line: OrderLine, catalog: MasterCatalog, rules: SupplierRules
) -> tuple[MasterProduct | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    raw = line.product_name_raw
    hint = rules.resolve_company(line.company_hint) if line.company_hint else None

    candidate: MasterProduct | None = None
    if hint:
        candidate = catalog.find_exact(hint, raw)
        if candidate is None:
            alias = rules.resolve_product_alias(hint, raw)
            if alias:
                candidate = catalog.find_exact(hint, alias)

    if candidate is not None:
        return candidate, issues

    # 힌트로 못 찾았으면 전체 마스터에서 정확히 같은 상품명을 검색 (업체명 불일치 여부 확인용)
    matches = catalog.find_all_by_product_name(raw)
    if not matches:
        # 파일명에서 업체 힌트를 못 얻은 경우 (예: 원본 플랫폼 export), 등록된 별칭 전체에서
        # 정확히 같은 원본 상품명을 찾는다. 추측이 아니라 이미 확인/등록된 별칭만 사용한다.
        for alias_company, alias_table in rules.product_aliases.items():
            master_name = alias_table.get(raw)
            if master_name:
                m = catalog.find_exact(alias_company, master_name)
                if m:
                    matches.append(m)

    deduped: list[MasterProduct] = []
    seen_keys: set[tuple[str, str]] = set()
    for m in matches:
        key = (m.company, m.product_name)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(m)
    matches = deduped

    if len(matches) == 0:
        issues.append(
            ValidationIssue(
                severity="error",
                code="product_not_found",
                message=f"⚠ 발주정보에서 '{raw}' 상품을 찾을 수 없습니다.",
                source_file=line.source_file,
                company=hint,
                product=raw,
            )
        )
        return None, issues

    distinct_companies = {m.company for m in matches}
    if len(distinct_companies) > 1:
        issues.append(
            ValidationIssue(
                severity="error",
                code="ambiguous_product",
                message=(
                    f"⚠ '{raw}' 상품명이 여러 업체({', '.join(sorted(distinct_companies))})에 "
                    f"동시에 등록되어 있어 자동으로 업체를 결정할 수 없습니다."
                ),
                source_file=line.source_file,
                product=raw,
            )
        )
        return None, issues

    match = matches[0]
    if hint and match.company != hint:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="company_mismatch",
                message=(
                    f"파일명 기준 업체는 '{hint}'이지만 상품 '{raw}'은(는) 실제로 "
                    f"'{match.company}'에 등록된 상품입니다. '{match.company}' 기준으로 계산합니다."
                ),
                source_file=line.source_file,
                company=hint,
                product=raw,
            )
        )
    return match, issues


def calculate(
    lines: list[OrderLine], catalog: MasterCatalog, rules: SupplierRules
) -> tuple[dict[str, SupplierResult], list[ValidationIssue]]:
    """반환값: (업체명 -> SupplierResult, 어떤 업체에도 못 붙인 최상위 오류/경고 목록)."""
    by_company: dict[str, list[tuple[OrderLine, MasterProduct]]] = {}
    by_company_issues: dict[str, list[ValidationIssue]] = {}
    top_level_issues: list[ValidationIssue] = []

    for line in lines:
        product, issues = resolve_line_product(line, catalog, rules)
        if product is None:
            top_level_issues.extend(issues)
            continue
        # company_mismatch 경고는 해당 업체 결과에 같이 보이도록 나중에 붙인다.
        by_company.setdefault(product.company, []).append((line, product))
        for issue in issues:
            issue.company = product.company
        by_company_issues.setdefault(product.company, []).extend(issues)

    results: dict[str, SupplierResult] = {}

    for company, pairs in by_company.items():
        sheet_default = "incl" if pairs[0][1].sheet == SELF_SUPPLY_SHEET else "ex_plus_fee"
        pricing_mode = rules.pricing_mode_override(company) or sheet_default
        is_self_supply = pricing_mode == "incl"
        account = catalog.account_for(company)
        override_account, warning = rules.account_override(company, account)
        issues: list[ValidationIssue] = list(by_company_issues.get(company, []))
        if override_account:
            account = override_account
        if warning:
            issues.append(ValidationIssue(severity="warning", code="account_override", message=warning, company=company))

        if account is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_account",
                    message=f"⚠ {company}의 송금계좌가 등록되어 있지 않습니다.",
                    company=company,
                )
            )

        breakdown_map: dict[str, ProductBreakdownItem] = {}
        goods_total = 0.0
        product_price_ok = True

        for line, product in pairs:
            if is_self_supply:
                unit_price = product.supply_price_incl_shipping
                if unit_price is None:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="missing_price",
                            message=f"⚠ '{product.product_name}'의 공급가(택포)가 확인되지 않아 송금액을 계산하지 않았습니다.",
                            company=company,
                            product=product.product_name,
                        )
                    )
                    product_price_ok = False
                    continue
            else:
                unit_price = product.supply_price_ex_shipping
                if unit_price is None:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="missing_price",
                            message=f"⚠ '{product.product_name}'의 공급가가 확인되지 않아 송금액을 계산하지 않았습니다.",
                            company=company,
                            product=product.product_name,
                        )
                    )
                    product_price_ok = False
                    continue

                if line.declared_unit_price is not None and abs(line.declared_unit_price - unit_price) > _PRICE_TOLERANCE:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="unit_price_mismatch",
                            message=(
                                f"⚠ '{product.product_name}' 발주서 단가({line.declared_unit_price:,.0f}원)가 "
                                f"마스터 공급가({unit_price:,.0f}원)와 다릅니다."
                            ),
                            source_file=line.source_file,
                            company=company,
                            product=product.product_name,
                        )
                    )
                    product_price_ok = False
                    continue

            key = product.product_name
            item = breakdown_map.setdefault(
                key,
                ProductBreakdownItem(
                    product_name=product.product_name,
                    quantity=0.0,
                    quantity_unit=line.quantity_unit,
                    unit_price=unit_price,
                    subtotal=0.0,
                ),
            )
            item.quantity += line.quantity
            item.subtotal += line.quantity * unit_price
            goods_total += line.quantity * unit_price

        shipment_count = 0
        shipping_fee_per_shipment = None
        shipping_total = 0.0

        if not is_self_supply:
            company_lines = [line for line, product in pairs]
            shipments, dedup_issues = group_into_shipments(company_lines)
            for di in dedup_issues:
                di.company = company
            issues.extend(dedup_issues)
            shipment_count = len(shipments)
            shipping_fee_per_shipment = catalog.shipping_fee_for(company)
            if shipping_fee_per_shipment is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="missing_shipping_fee",
                        message=f"⚠ {company}의 배송비가 확인되지 않아 송금액을 계산하지 않았습니다.",
                        company=company,
                    )
                )
                product_price_ok = False
            else:
                shipping_total = shipment_count * shipping_fee_per_shipment

            for line in company_lines:
                if line.declared_shipping_fee is not None and shipping_fee_per_shipment is not None:
                    if abs(line.declared_shipping_fee - shipping_fee_per_shipment) > _PRICE_TOLERANCE:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                code="shipping_fee_mismatch",
                                message=(
                                    f"⚠ 발주서 배송비({line.declared_shipping_fee:,.0f}원)가 마스터 "
                                    f"배송비({shipping_fee_per_shipment:,.0f}원)와 다릅니다."
                                ),
                                source_file=line.source_file,
                                company=company,
                            )
                        )
                        product_price_ok = False

        grand_total = goods_total + shipping_total if product_price_ok else 0.0

        results[company] = SupplierResult(
            company=company,
            display_name=rules.display_name(company),
            account=account,
            source_sheet=pairs[0][1].sheet,
            is_self_supply=is_self_supply,
            breakdown=list(breakdown_map.values()),
            shipment_count=shipment_count,
            shipping_fee_per_shipment=shipping_fee_per_shipment,
            shipping_total=shipping_total if product_price_ok else 0.0,
            goods_total=goods_total if product_price_ok else 0.0,
            grand_total=grand_total,
            issues=issues,
        )

    return results, top_level_issues
