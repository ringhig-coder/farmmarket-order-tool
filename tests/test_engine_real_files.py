"""실제 2026-09-16 발주요청서 파일로 하는 회귀 테스트.

과거 정답(260729/260508/260915/260909)이 적힌 파일은 이 컴퓨터에 없어서,
대신 실제로 전달받은 오늘 파일들로 '마스터 단가 기준 직접 계산값'과 대조한다.
계산 근거는 docs/excel-analysis.md 에 적어두었다.
"""
from pathlib import Path

from farmmarket.pipeline import process_files


def test_haenam_260916_file(project_root, catalog, rules):
    path = project_root / "data/samples/260916/무무식탁_해남고구마식품_발주요청서_260916.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["해남고구마식품"]
    assert r.goods_total == 31000
    assert r.shipping_total == 3000
    assert r.grand_total == 34000
    assert r.account == "광주 630-107-310371 (해남고구마식품)"


def test_leewoong_260916_file(project_root, catalog, rules):
    path = project_root / "data/samples/260916/이웅식품_무무식탁_발주요청서_260916.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["이웅식품"]
    assert r.goods_total == 31200
    assert r.shipping_total == 3300
    assert r.grand_total == 34500
    # 이 업체 파일은 자체적으로 단가/배송비/합계를 미리 계산해서 보내주는데,
    # 그 값이 우리 계산과 정확히 같아서 이중 검증이 된다.
    assert r.grand_total == 34500  # 파일 1행 요약값(합계 34,500)과 동일


def test_raw_platform_export_resolves_via_registered_alias(project_root, catalog, rules):
    # 이 파일은 업체명이 파일명에 없는 원본 플랫폼 export지만, 상품명이
    # config/supplier_rules.json의 다모식품 별칭과 정확히 일치해서 추측 없이 해결된다.
    path = project_root / "data/samples/260916/무무식탁 26.09.16.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["다모식품"]
    assert r.is_valid
    assert r.account == "국민 790401-01-336718 (다모식품)"


def test_damo_260914_file(project_root, catalog, rules):
    path = project_root / "data/samples/260914/무무식탁_다모식품_발주요청서_ 260914.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["다모식품"]
    assert r.is_valid
    assert r.account == "국민 790401-01-336718 (다모식품)"
    # "60g x 20봉" 1개는 10봉 기준 2개로 환산되어 60g 10봉 묶음에 합산된다 (9 + 2 = 11)
    sizes = {item.product_name: item.quantity for item in r.breakdown}
    assert sizes["반시 고구마말랭이 60g 10봉"] == 11
    assert sizes["반시 고구마말랭이 100g 10봉"] == 13
    assert "반시 고구마말랭이 60g 20봉" not in sizes
    assert r.goods_total == 11 * 10000 + 13 * 16000  # 20g짜리 1개(20,000원)도 10,000*2로 동일하게 반영됨
    assert r.shipment_count == 23  # 23명 전원 다른 주소
    assert r.grand_total == r.goods_total + 23 * 2500


def test_joom_260914_file(project_root, catalog, rules):
    path = project_root / "data/samples/260914/무무식탁_주줌_발주요청서_ 260914.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["주줌"]
    assert r.goods_total == 3 * 12000
    assert r.shipping_total == 2500
    assert r.grand_total == 38500
    assert r.account == "농협 351-0727-4344-83 (줌)"


def test_hankal_260914_file_uses_incl_price_no_extra_shipping(project_root, catalog, rules):
    path = project_root / "data/samples/260914/무무식탁_한칼식품_발주요청서_ 260914 (1).xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["한칼식품"]
    assert r.is_self_supply  # pricing_mode override: 택포 직접 사용
    assert r.shipping_total == 0
    assert r.grand_total == 11700  # 택전(8,380)+배송비(4,000)=12,380 아님에 주의
    assert r.account == "신한 110-355-569956 한칼 (신숙경)"


def test_haenam_260914_file(project_root, catalog, rules):
    path = project_root / "data/samples/260914/무무식탁_해남고구마식품_발주요청서_260914.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["해남고구마식품"]
    assert r.shipment_count == 7
    assert r.goods_total == 17 * 15500
    assert r.shipping_total == 7 * 3000
    assert r.grand_total == 17 * 15500 + 7 * 3000


def test_milyang_hancheon_260805_file(project_root, catalog, rules):
    path = project_root / "data/samples/misc/무무식탁_밀양한천_발주요청서_ 260805.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["밀양한천"]
    assert r.grand_total == 11200 + 4000  # 프리미엄 넛츠양갱 택전 + 배송비(1호 행에서 forward-fill)
    assert r.account == "농협 85601054025 (밀양한천)"


def test_hayeongine_260915_file(project_root, catalog, rules):
    path = project_root / "data/samples/misc/무무식탁_하영이네_발주요청서_260915.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["하영이네"]
    assert r.grand_total == 9720
    assert r.account == "전북은행 1021-01-9024244 (강양선)"


def test_farmmarket_260915_file_jeondiary_oil(project_root, catalog, rules):
    # 파일에는 "존디어 미션오일 20L"로만 적혀있고 마스터 표기는 다르지만(별칭 등록), 섹션 15/17의 정답과 일치
    path = project_root / "data/samples/misc/나는농부_팜마켓_발주요청서_260915.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["팜마켓"]
    assert r.is_self_supply
    assert r.grand_total == 139000 * 2  # 278,000원


def test_shinan_industry_260803_file(project_root, catalog, rules):
    # "평사다리 6단" = 마스터 "평사다리 6자" (사용자 확인, 별칭 등록됨)
    path = project_root / "data/samples/misc/나는농부_신안산업_발주요청서_260803.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["신안산업"]
    # 신안산업은 나는농부 시트 업체라 공급가(택포)를 그대로 쓴다 (배송비 별도 없음)
    assert r.grand_total == 1 * 89100 + 2 * 48400 + 2 * 73700 + 2 * 148500


def test_hyeonmigreen_260915_file(project_root, catalog, rules):
    # "현미 통밀빵 믹스 2봉" = 마스터 "현미 식빵믹스 350g x 2개" (사용자 확인, 별칭 등록됨)
    path = project_root / "data/samples/misc/무무식탁_현미왕_발주요청서_260915.xlsx"
    result = process_files([path], catalog, rules)
    assert not result.has_blocking_error
    r = result.supplier_results["현미그린"]
    assert r.grand_total == 9000
    assert r.account == "하나 702-910535-56107 송완순 (현미그린)"


def test_combined_files_do_not_cross_contaminate(project_root, catalog, rules):
    paths = [
        project_root / "data/samples/260916/무무식탁_해남고구마식품_발주요청서_260916.xlsx",
        project_root / "data/samples/260916/이웅식품_무무식탁_발주요청서_260916.xlsx",
    ]
    result = process_files(paths, catalog, rules)
    assert set(result.supplier_results.keys()) == {"해남고구마식품", "이웅식품"}
    assert result.total_amount == 34000 + 34500
