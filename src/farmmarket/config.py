"""supplier_rules.json 로더. 단가/계좌는 여기 저장하지 않는다 - 마스터 파일이 유일한 출처."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SupplierRules:
    company_aliases: dict[str, str] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)
    account_overrides: dict[str, dict] = field(default_factory=dict)
    product_aliases: dict[str, dict[str, str]] = field(default_factory=dict)
    # 기본값: 🍽️무무식탁 시트 업체는 "공급가(택전)+배송비", 🌳나는농부 시트는 "공급가(택포) 그대로".
    # 한칼식품처럼 무무식탁 시트인데 택포를 그대로 쓰는 예외만 여기 등록한다 (섹션 17에서 확인됨).
    pricing_mode_overrides: dict[str, dict] = field(default_factory=dict)

    def resolve_company(self, raw_name: str) -> str:
        name = raw_name.strip()
        return self.company_aliases.get(name, name)

    def display_name(self, canonical_company: str) -> str:
        return self.display_names.get(canonical_company, canonical_company)

    def resolve_product_alias(self, canonical_company: str, raw_product_name: str) -> str | None:
        table = self.product_aliases.get(canonical_company, {})
        return table.get(raw_product_name.strip())

    def pricing_mode_override(self, canonical_company: str) -> str | None:
        """'incl' (택포 직접 사용, 배송비 별도 추가 안 함) 또는 None (해당 업체는 시트 기본값을 따름)."""
        rule = self.pricing_mode_overrides.get(canonical_company)
        return rule.get("mode") if rule else None

    def account_override(self, canonical_company: str, master_account: str | None) -> tuple[str | None, str | None]:
        """(정정계좌 or None, 경고문구 or None) 반환. 마스터 값이 이미 정정되어 있으면 아무것도 하지 않는다."""
        rule = self.account_overrides.get(canonical_company)
        if not rule:
            return None, None
        if master_account == rule.get("correct_value"):
            return None, None  # 마스터가 이미 고쳐졌음
        warning = (
            f"⚠ {canonical_company}의 마스터 계좌번호가 확인된 최신 계좌와 다릅니다. "
            f"정정된 계좌를 사용합니다. ({rule.get('note', '')})"
        )
        return rule.get("correct_value"), warning


def load_supplier_rules(path: Path) -> SupplierRules:
    if not path.exists():
        return SupplierRules()
    data = json.loads(path.read_text(encoding="utf-8"))
    return SupplierRules(
        company_aliases=data.get("company_aliases", {}),
        display_names=data.get("display_names", {}),
        account_overrides=data.get("account_overrides", {}),
        product_aliases=data.get("product_aliases", {}),
        pricing_mode_overrides=data.get("pricing_mode_overrides", {}),
    )
