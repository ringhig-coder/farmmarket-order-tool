import datetime

from farmmarket.models import OrderLine
from farmmarket.order_generation import generate_supplier_orders
from farmmarket.order_writer import load_output_templates


def _line(product_name, qty=1, company_hint=None):
    return OrderLine(
        source_file="naver:test",
        company_hint=company_hint,
        recipient="테스트수취인",
        address="테스트 주소",
        phone="010-0000-0000",
        quantity=qty,
        quantity_unit="unit",
        product_name_raw=product_name,
    )


def test_matched_products_are_grouped_and_written_with_correct_prefix(project_root, catalog, rules, tmp_path):
    templates = load_output_templates(project_root / "config" / "output_templates.json")
    lines = [
        _line("프리미엄 넛츠양갱"),  # 밀양한천, 무무식탁 시트
        _line("존디어 미션오일 20L"),  # 팜마켓, 나는농부 시트 (별칭 등록됨)
    ]
    report = generate_supplier_orders(lines, catalog, rules, templates, tmp_path, order_date=datetime.date(2026, 9, 16))

    assert len(report.files_written) == 2
    names = {p.name for p in report.files_written}
    assert "무무식탁_밀양한천_발주요청서_260916.xlsx" in names
    assert "나는농부_팜마켓_발주요청서_260916.xlsx" in names
    for p in report.files_written:
        assert p.exists()
        assert p.parent.name == "발주서_260916"


def test_unmatched_product_is_reported_not_dropped(project_root, catalog, rules, tmp_path):
    templates = load_output_templates(project_root / "config" / "output_templates.json")
    lines = [_line("완전히 새로운 미등록 상품 999g")]
    report = generate_supplier_orders(lines, catalog, rules, templates, tmp_path)
    assert report.files_written == []
    assert len(report.unmatched_products) == 1
    assert report.has_unhandled


def test_matched_but_no_output_template_is_reported(project_root, catalog, rules, tmp_path):
    templates = load_output_templates(project_root / "config" / "output_templates.json")
    # 이웅식품은 마스터에 있지만 output_templates.json에는 없음 (사전계산형이라 다른 방식 필요)
    lines = [_line("스틱 참기름 10개입")]
    report = generate_supplier_orders(lines, catalog, rules, templates, tmp_path)
    assert report.files_written == []
    assert report.no_template_companies.get("이웅식품") == 1
