from farmmarket.master import clean_company_name, clean_product_name


def test_clean_company_name_strips_annotations():
    assert clean_company_name(" 해남 고구마 식품\n\n*단가인상\n(26.04.16)") == "해남고구마식품"
    assert clean_company_name("한칼식품\n\n*단가인상\n(26.04.17)") == "한칼식품"
    assert clean_company_name("NEW\n밀양한천\n(쿠팡 x)") == "밀양한천"
    assert clean_company_name("팜 마 켓") == "팜마켓"


def test_clean_product_name_collapses_whitespace():
    assert clean_product_name("반시 고구마말랭이  60g\n10봉") == "반시 고구마말랭이 60g 10봉"


def test_master_catalog_loaded(catalog):
    assert len(catalog.products) > 0
    assert "다모식품" in catalog.companies()
    assert "해남고구마식품" in catalog.companies()
    assert "팜마켓" in catalog.companies()


def test_damo_account_is_corrected_by_override(catalog):
    p = catalog.find_exact("다모식품", "반시 고구마말랭이 60g 10봉")
    assert p is not None
    assert p.account == "국민 790401-01-336718 (다모식품)"


def test_known_prices_match_user_verified_values(catalog):
    damo_60 = catalog.find_exact("다모식품", "반시 고구마말랭이 60g 10봉")
    damo_100 = catalog.find_exact("다모식품", "반시 고구마말랭이 100g 10봉")
    assert damo_60.supply_price_ex_shipping == 10000
    assert damo_100.supply_price_ex_shipping == 16000
    assert catalog.shipping_fee_for("다모식품") == 2500

    haenam = catalog.find_exact("해남고구마식품", "해남에서말린 고구마말랭이 60g 10봉")
    assert haenam.supply_price_ex_shipping == 15500
    assert catalog.shipping_fee_for("해남고구마식품") == 3000
    assert haenam.account == "광주 630-107-310371 (해남고구마식품)"

    joom = catalog.find_exact("주줌", "한입에 반한 반시고구마 60g x 10봉")
    assert joom.account == "농협 351-0727-4344-83 (줌)"

    hyeonmi = catalog.find_exact("현미그린", "현미 식빵믹스 350g x 2개")
    assert hyeonmi.supply_price_incl_shipping == 9000

    farmmarket_tonback = catalog.find_exact("팜마켓", "톤백걸이 (오거슈터)")
    assert farmmarket_tonback.supply_price_incl_shipping == 86000
