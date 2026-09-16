from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MasterProduct:
    """마스터 발주정보의 상품 한 행."""

    sheet: str
    row: int
    company: str  # 정규화된(공백/개행 제거) 업체명
    product_name: str
    supply_price_ex_shipping: float | None  # 공급가 (택전)
    supply_price_incl_shipping: float | None  # 공급가 (택포)
    shipping_fee: float | None  # 택배비
    account: str | None
    note: str | None


@dataclass
class OrderLine:
    """발주요청서 파일에서 파싱한 한 줄."""

    source_file: str
    company_hint: str | None  # 파일명 등에서 추정한 업체명 (검증용, 신뢰하지 않음)
    recipient: str | None
    address: str | None
    phone: str | None
    quantity: float
    quantity_unit: str  # "box" | "unit"
    product_name_raw: str
    note: str | None = None
    # 이미 계산된 값이 원본 파일에 있는 경우 (교차검증용, 계산에 그대로 신뢰해서 쓰지 않음)
    declared_unit_price: float | None = None
    declared_shipping_fee: float | None = None
    declared_total: float | None = None
    external_product_id: str | None = None  # 채널(네이버 등)의 고유 상품번호. 이름보다 안정적인 매칭 키.


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    source_file: str | None = None
    company: str | None = None
    product: str | None = None


@dataclass
class ProductBreakdownItem:
    product_name: str
    quantity: float
    quantity_unit: str
    unit_price: float
    subtotal: float


@dataclass
class SupplierResult:
    company: str  # 정규화된 업체명
    display_name: str  # 화면/메시지에 보여줄 이름
    account: str | None
    source_sheet: str  # 마스터의 어느 시트 상품인지 ("🍽️무무식탁" / "🌳나는농부") - 메시지 섹션 분리에 사용
    is_self_supply: bool  # True면 공급가(택포)를 최종가로 그대로 쓰고 배송비를 더하지 않는다.
    # 나는농부 시트 업체(팜마켓 등)는 항상 True. 한칼식품처럼 무무식탁 시트 업체인데
    # pricing_mode_overrides에 "incl"로 등록된 예외도 True가 된다 - 이름과 달리
    # "진짜 자체상품"인지가 아니라 "가격 계산 방식"을 나타내는 플래그다.
    breakdown: list[ProductBreakdownItem] = field(default_factory=list)
    shipment_count: int = 0
    shipping_fee_per_shipment: float | None = None
    shipping_total: float = 0.0
    goods_total: float = 0.0
    grand_total: float = 0.0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors and self.account is not None
