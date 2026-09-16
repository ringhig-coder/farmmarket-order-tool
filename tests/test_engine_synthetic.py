"""엔진 계산 검증 (섹션 17 등에서 제공된 검증된 숫자와 대조).

실제 다모식품/나는농부 발주요청서 샘플 파일을 아직 받지 못해서, 여기서는 마스터의 실제 단가를
그대로 쓰되 주문 라인(수취인/주소/수량)만 사람이 구성한 합성 데이터로 엔진 로직 자체
(배송지 중복제거, 사이즈별 묶음 표기, 자체상품 계산)를 검증한다.
실제 파일이 오면 tests/test_engine_real_files.py 쪽에 진짜 회귀 테스트로 옮긴다.
"""
from farmmarket.engine import calculate
from farmmarket.formatter import build_remittance_message
from farmmarket.models import OrderLine


def _damo_line(recipient, size_g, boxes):
    product = f"반시 고구마말랭이 {size_g}g 10봉"
    return OrderLine(
        source_file="synthetic.xlsx",
        company_hint="다모식품",
        recipient=recipient,
        address=f"{recipient}의 주소",
        phone="010-0000-0000",
        quantity=boxes,
        quantity_unit="box",
        product_name_raw=product,
    )


def test_damo_260909_style_matches_spec_total(catalog, rules):
    # 60g 6박스 + 100g 4박스, 5명 배송지 -> "고구마 말랭이1 (10) (60*6+100*4) 5명 2500", 136,500원
    lines = [
        _damo_line("A", 60, 2),
        _damo_line("B", 60, 2),
        _damo_line("C", 60, 2),
        _damo_line("D", 100, 2),
        _damo_line("E", 100, 2),
    ]
    results, top_issues = calculate(lines, catalog, rules)
    assert top_issues == []
    r = results["다모식품"]
    assert r.is_valid
    assert r.shipment_count == 5
    assert r.goods_total == 6 * 10000 + 4 * 16000  # 124,000
    assert r.shipping_total == 5 * 2500  # 12,500
    assert r.grand_total == 136500

    message = build_remittance_message(results, rules)
    assert "고구마 말랭이1 (10) (60*6+100*4) 5명 2500" in message
    assert "136,500원" in message


def _haenam_line(recipient, boxes):
    return OrderLine(
        source_file="synthetic.xlsx",
        company_hint="해남고구마식품",
        recipient=recipient,
        address=f"{recipient}의 주소",
        phone="010-0000-0000",
        quantity=boxes,
        quantity_unit="box",
        product_name_raw="해남에서말린 고구마말랭이 60g 10봉",
    )


def test_haenam_260909_style_matches_spec_total(catalog, rules):
    # 7세트, 4명 -> 108,500 + 12,000 = 120,500원
    lines = [
        _haenam_line("A", 2),
        _haenam_line("B", 2),
        _haenam_line("C", 2),
        _haenam_line("D", 1),
    ]
    results, top_issues = calculate(lines, catalog, rules)
    r = results["해남고구마식품"]
    assert r.shipment_count == 4
    assert r.goods_total == 7 * 15500
    assert r.shipping_total == 4 * 3000
    assert r.grand_total == 120500


def _farmmarket_line(product_name, qty):
    return OrderLine(
        source_file="synthetic.xlsx",
        company_hint="팜마켓",
        recipient="농부",
        address="철원 어딘가",
        phone="010-0000-0000",
        quantity=qty,
        quantity_unit="unit",
        product_name_raw=product_name,
    )


def test_farmmarket_self_supply_uses_incl_shipping_price_no_extra_fee(catalog, rules):
    lines = [_farmmarket_line("톤백걸이 (오거슈터)", 1)]
    results, _ = calculate(lines, catalog, rules)
    r = results["팜마켓"]
    assert r.is_self_supply
    assert r.shipping_total == 0
    assert r.grand_total == 86000


def test_farmmarket_jeondiary_oil_two_units(catalog, rules):
    lines = [_farmmarket_line("⭐존디어 HY-Gard 20L (유압/미션오일 겸용)", 2)]
    results, _ = calculate(lines, catalog, rules)
    r = results["팜마켓"]
    assert r.grand_total == 139000 * 2


def test_farmmarket_tf700(catalog, rules):
    lines = [_farmmarket_line("품절 트랙터 공용 TF700", 1)]
    results, _ = calculate(lines, catalog, rules)
    r = results["팜마켓"]
    assert r.grand_total == 69500


def _generic_line(company, product_name, qty=1):
    return OrderLine(
        source_file="synthetic.xlsx",
        company_hint=company,
        recipient="수취인",
        address="주소",
        phone="010-0000-0000",
        quantity=qty,
        quantity_unit="unit",
        product_name_raw=product_name,
    )


def test_hyeonmigreen_singlebox_matches_spec_total(catalog, rules):
    # TEST A: 현미 식빵믹스 350g x 2개 (1) 1명 3000 -> 9,000원
    lines = [_generic_line("현미그린", "현미 식빵믹스 350g x 2개", 1)]
    results, _ = calculate(lines, catalog, rules)
    r = results["현미그린"]
    assert r.shipment_count == 1
    assert r.grand_total == 9000
    assert r.account == "하나 702-910535-56107 송완순 (현미그린)"


def test_milyang_hancheon_3ho_matches_spec_total(catalog, rules):
    # TEST B: 명품종합양갱 3호 (1) 1명 4000 -> 19,600원 (택배비는 1호 행에만 있어서 forward-fill 필요)
    lines = [_generic_line("밀양한천", "명품종합양갱 3호", 1)]
    results, _ = calculate(lines, catalog, rules)
    r = results["밀양한천"]
    assert r.shipment_count == 1
    assert r.shipping_fee_per_shipment == 4000
    assert r.grand_total == 19600
    assert r.account == "농협 85601054025 (밀양한천)"


def test_hayeongine_matches_spec_total(catalog, rules):
    # TEST C: 순한맛 떡갈비 120g*4 (1) 1명 4040 -> 9,720원
    lines = [_generic_line("하영이네", "순한맛 떡갈비 120g*4", 1)]
    results, _ = calculate(lines, catalog, rules)
    r = results["하영이네"]
    assert r.grand_total == 9720
    assert r.account == "전북은행 1021-01-9024244 (강양선)"


def test_unmapped_product_within_aliased_company_is_not_silently_matched(catalog, rules):
    # 회귀 테스트: 다모식품처럼 별칭이 여러 개 등록된 업체에서, 별칭 테이블에 없는
    # 전혀 다른 상품명이 들어왔을 때 등록된 별칭 중 아무거나로 잘못 매칭되면 안 된다.
    lines = [
        OrderLine(
            source_file="synthetic.xlsx",
            company_hint="다모식품",
            recipient="A",
            address="어딘가",
            phone="010",
            quantity=1,
            quantity_unit="box",
            product_name_raw="다모식품이 팔지 않는 전혀 다른 상품",
        )
    ]
    results, top_issues = calculate(lines, catalog, rules)
    assert results == {}
    assert any(i.code == "product_not_found" for i in top_issues)


def test_unknown_product_blocks_calculation_instead_of_guessing(catalog, rules):
    lines = [
        OrderLine(
            source_file="synthetic.xlsx",
            company_hint=None,
            recipient="A",
            address="어딘가",
            phone="010",
            quantity=1,
            quantity_unit="unit",
            product_name_raw="완전히 새로운 미등록 상품 999g",
        )
    ]
    results, top_issues = calculate(lines, catalog, rules)
    assert results == {}
    assert any(i.code == "product_not_found" for i in top_issues)
