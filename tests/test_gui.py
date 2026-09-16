"""GUI 로직 테스트 (헤드리스, QT_QPA_PLATFORM=offscreen).

화면 배치가 아니라 '상태 전이'를 검증한다: 파일 추가 -> 계산 -> 버튼 활성화,
오류 시 복사 비활성화, 중복 파일 차단, 전체 삭제 시 초기화.
"""
from pathlib import Path


def test_master_loads_on_startup(qapp, project_root, catalog):
    from farmmarket.gui import MainWindow

    win = MainWindow()
    assert win.catalog is not None
    assert "정상 로드됨" in win.master_status_label.text()


def test_valid_file_enables_copy_and_fills_table(qapp, project_root, catalog):
    from farmmarket.gui import MainWindow

    win = MainWindow()
    win._add_files(
        [project_root / "data/samples/260916/무무식탁_해남고구마식품_발주요청서_260916.xlsx"]
    )
    assert win.table.rowCount() == 1
    assert win.copy_btn.isEnabled()
    assert win.save_btn.isEnabled()
    assert "34,000원" in win.message_box.toPlainText()
    assert "68,500원" not in win.message_box.toPlainText()  # 정산금액류 텍스트 없음 확인용 반례 아님, 그냥 실제 없음


def test_duplicate_file_is_rejected(qapp, project_root, catalog):
    from farmmarket.gui import MainWindow

    win = MainWindow()
    path = project_root / "data/samples/260916/이웅식품_무무식탁_발주요청서_260916.xlsx"
    win._add_files([path])
    win._add_files([path])
    assert win.file_list.count() == 1
    assert "이미 추가된" in win.status_label.text()


def test_unresolved_product_blocks_copy_button(qapp, project_root, tmp_path, catalog):
    import openpyxl

    from farmmarket.gui import MainWindow

    bad_file = tmp_path / "미등록상품.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["받는분성명", "받는분주소(전체, 분할)", "받는분전화번호", "박스수량", "품목명"])
    ws.append(["테스트", "서울시 어딘가", "010-0000-0000", 1, "완전히 새로운 미등록 상품"])
    wb.save(bad_file)

    win = MainWindow()
    win._add_files([bad_file])
    assert not win.copy_btn.isEnabled()
    assert not win.save_btn.isEnabled()
    assert "찾을 수 없습니다" in win.issues_box.toPlainText()
    assert "오류가 있어" in win.message_box.toPlainText()


def test_clear_files_resets_state(qapp, project_root, catalog):
    from farmmarket.gui import MainWindow

    win = MainWindow()
    win._add_files([project_root / "data/samples/260916/이웅식품_무무식탁_발주요청서_260916.xlsx"])
    win._clear_files()
    assert win.table.rowCount() == 0
    assert win.file_list.count() == 0
    assert not win.copy_btn.isEnabled()
    assert win.total_label.text() == "총 송금액: -"


def test_copy_button_puts_message_on_clipboard(qapp, project_root, catalog):
    from farmmarket.gui import MainWindow

    win = MainWindow()
    win._add_files([project_root / "data/samples/260916/이웅식품_무무식탁_발주요청서_260916.xlsx"])
    win._copy_message()
    assert "34,500원" in qapp.clipboard().text()
    assert "복사했습니다" in win.status_label.text()
