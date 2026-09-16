"""네이버 주문 응답 -> 내부 OrderLine 변환 테스트.

실제 API에서 받은 응답 구조(2026-09-16 확인)를 그대로 흉내낸 fixture를 사용한다.
"""
from farmmarket.channels.naver import naver_product_key, order_details_to_lines

_REAL_SHAPE_CONFIRMED = {
    "order": {"orderId": "2026091538606901", "ordererName": "최승훈", "ordererTel": "010-3770-9462"},
    "productOrder": {
        "productOrderId": "2026091593560611",
        "productId": "5474106992",
        "quantity": 2,
        "productOrderStatus": "PAYED",
        "productName": "충전식 전동 분무기 BMC 18L",
        "shippingAddress": {
            "name": "최승훈",
            "tel1": "010-3770-9462",
            "zipCode": "33403",
            "baseAddress": "충청남도 보령시 천북면 세편길 48 (천북면)",
            "detailedAddress": "잘부탁드립니다~~",
        },
    },
}

_REAL_SHAPE_WITH_OPTION = {
    "order": {"orderId": "x", "ordererName": "황석찬", "ordererTel": "010-0000-0000"},
    "productOrder": {
        "productOrderId": "p2",
        "productId": "10774800180",
        "productOption": "필수선택: (1) 일반모델",
        "quantity": 1,
        "productOrderStatus": "PAYED",
        "productName": "톤백 걸이 콤바인 전용 자루 거치대 농업용 마대 걸이대 나는농부 팜마켓",
        "shippingAddress": {
            "name": "김철수",
            "tel1": "010-1111-2222",
            "baseAddress": "서울시 어딘가",
            "detailedAddress": None,
        },
    },
}

_REAL_SHAPE_UNCONFIRMED = {
    "order": {"orderId": "2026091538600000", "ordererName": "김철수", "ordererTel": "010-0000-0000"},
    "productOrder": {
        "productOrderId": "2026091500000001",
        "productId": "999",
        "quantity": 1,
        "productOrderStatus": "PAYED",
        "productName": "톤백 걸이 콤바인 전용 자루 거치대",
        # shippingAddress 없음 - 발주확인 전
    },
}


def test_confirmed_order_produces_line_with_full_address():
    lines, pending = order_details_to_lines([_REAL_SHAPE_CONFIRMED])
    assert pending == []
    assert len(lines) == 1
    line = lines[0]
    assert line.recipient == "최승훈"
    assert line.phone == "010-3770-9462"
    assert "천북면 세편길 48" in line.address
    assert "잘부탁드립니다" in line.address
    assert line.quantity == 2
    assert line.product_name_raw == "충전식 전동 분무기 BMC 18L"
    assert line.external_product_id == "5474106992"


def test_unconfirmed_order_is_reported_as_pending_not_dropped_silently():
    lines, pending = order_details_to_lines([_REAL_SHAPE_UNCONFIRMED])
    assert lines == []
    assert pending == ["2026091500000001"]


def test_mixed_batch_separates_confirmed_and_pending():
    lines, pending = order_details_to_lines([_REAL_SHAPE_CONFIRMED, _REAL_SHAPE_UNCONFIRMED])
    assert len(lines) == 1
    assert len(pending) == 1


def test_option_product_uses_composite_key():
    assert naver_product_key("10774800180", "필수선택: (1) 일반모델") == "10774800180::필수선택: (1) 일반모델"
    assert naver_product_key("5474106992", None) == "5474106992"


def test_registered_product_map_resolves_company_and_canonical_name():
    product_map = {
        "10774800180::필수선택: (1) 일반모델": {"company": "팜마켓", "product_name": "톤백걸이 (오거슈터)"},
    }
    lines, _ = order_details_to_lines([_REAL_SHAPE_WITH_OPTION], product_map)
    assert len(lines) == 1
    assert lines[0].company_hint == "팜마켓"
    assert lines[0].product_name_raw == "톤백걸이 (오거슈터)"
    assert lines[0].external_product_id == "10774800180::필수선택: (1) 일반모델"


def test_unregistered_product_keeps_naver_raw_name_for_fallback_matching():
    lines, _ = order_details_to_lines([_REAL_SHAPE_WITH_OPTION], product_map={})
    assert lines[0].company_hint is None
    assert lines[0].product_name_raw == "톤백 걸이 콤바인 전용 자루 거치대 농업용 마대 걸이대 나는농부 팜마켓"
