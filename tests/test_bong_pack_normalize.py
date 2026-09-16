"""고구마 말랭이류 포장단위(봉) 정규화 테스트.

사용자 확인: 발주/정산은 항상 10봉 기준이라, 20봉/40봉처럼 다른 포장 단위가
상품명에 찍혀 있어도 10봉 몇 개인지로 환산해야 한다. 10의 배수가 아니면 계산을 막는다.
"""
from farmmarket.parsers.base import normalize_bong_pack


def test_10bong_is_left_as_is():
    name, qty, err = normalize_bong_pack("더 맛난 반시 고구마 말랭이 60g x 10봉", 3)
    assert name == "더 맛난 반시 고구마 말랭이 60g x 10봉"
    assert qty == 3
    assert err is None


def test_20bong_normalizes_to_two_10bong_units():
    name, qty, err = normalize_bong_pack("더 맛난 반시 고구마 말랭이 60g x 20봉", 1)
    assert name == "더 맛난 반시 고구마 말랭이 60g x 10봉"
    assert qty == 2
    assert err is None


def test_40bong_with_quantity_normalizes_multiplicatively():
    # 40봉짜리 1개 = 10봉 4개, 그런 상품이 2줄이면 총 8개
    name, qty, err = normalize_bong_pack("더 맛난 반시 고구마 말랭이 100g x 40봉", 2)
    assert name == "더 맛난 반시 고구마 말랭이 100g x 10봉"
    assert qty == 8
    assert err is None


def test_non_multiple_of_ten_is_blocked_not_guessed():
    name, qty, err = normalize_bong_pack("더 맛난 반시 고구마 말랭이 60g x 15봉", 1)
    assert err is not None
    assert "15봉" in err


def test_names_without_bong_pattern_are_unaffected():
    name, qty, err = normalize_bong_pack("스틱 참기름(5ml x 10ea)", 3)
    assert name == "스틱 참기름(5ml x 10ea)"
    assert qty == 3
    assert err is None
