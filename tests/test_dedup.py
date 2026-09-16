from farmmarket.dedup import group_into_shipments
from farmmarket.models import OrderLine


def _line(recipient, address, product="상품", qty=1, phone="010-0000-0000"):
    return OrderLine(
        source_file="test.xlsx",
        company_hint="테스트",
        recipient=recipient,
        address=address,
        phone=phone,
        quantity=qty,
        quantity_unit="box",
        product_name_raw=product,
    )


def test_same_recipient_same_address_merges_into_one_shipment():
    lines = [
        _line("홍길동", "서울시 강남구 1번지", product="60g"),
        _line("홍길동", "서울시 강남구 1번지", product="100g"),
    ]
    groups, issues = group_into_shipments(lines)
    assert len(groups) == 1
    assert len(groups[0].lines) == 2
    assert issues == []


def test_different_address_creates_separate_shipments():
    lines = [
        _line("홍길동", "서울시 강남구 1번지"),
        _line("김철수", "부산시 해운대구 2번지"),
    ]
    groups, issues = group_into_shipments(lines)
    assert len(groups) == 2


def test_whitespace_differences_still_merge():
    lines = [
        _line("홍  길동", "서울시  강남구 1번지"),
        _line("홍길동", "서울시 강남구 1번지"),
    ]
    groups, issues = group_into_shipments(lines)
    assert len(groups) == 1


def test_missing_address_is_not_merged_and_warns():
    lines = [
        _line("홍길동", None),
        _line("홍길동", None),
    ]
    groups, issues = group_into_shipments(lines)
    assert len(groups) == 2  # 억지로 합치지 않음
    assert any(i.code == "incomplete_address" for i in issues)
