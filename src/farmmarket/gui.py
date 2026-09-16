"""PySide6 메인 화면 (섹션 18~23).

직원이 설명 없이 쓸 수 있어야 하므로 화면은 하나로 단순하게 구성한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QClipboard, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import SupplierRules, load_supplier_rules
from .formatter import build_remittance_message
from .master import SELF_SUPPLY_SHEET, MasterCatalog, load_master_catalog
from .pipeline import DuplicateFileTracker, PipelineResult, process_files

ORG_NAME = "FarmMarket"
APP_NAME = "발주송금요청생성기"
MASTER_FILENAME = "💰팜마켓 발주정보.xlsx"


def app_base_dir() -> Path:
    """PyInstaller로 묶였을 때는 exe가 있는 폴더, 개발 중에는 프로젝트 루트."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve_supplier_rules_path() -> Path:
    """exe 옆의 config/supplier_rules.json을 우선 쓰고, 없으면 exe에 번들된 기본값을 쓴다.

    이렇게 하면 관리자가 재빌드 없이 exe 옆 config 폴더만 고쳐서 별칭/오버라이드를 바꿀 수 있다.
    """
    external = app_base_dir() / "config" / "supplier_rules.json"
    if external.exists():
        return external
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "config" / "supplier_rules.json"
        if bundled.exists():
            return bundled
    return external


def find_master_file() -> Path | None:
    settings = QSettings(ORG_NAME, APP_NAME)
    remembered = settings.value("master_path", "")
    if remembered and Path(remembered).exists():
        return Path(remembered)

    candidates = [
        app_base_dir() / MASTER_FILENAME,
        app_base_dir() / "data" / "master" / MASTER_FILENAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def remember_master_file(path: Path) -> None:
    QSettings(ORG_NAME, APP_NAME).setValue("master_path", str(path))


class DropArea(QFrame):
    def __init__(self, on_files_dropped):
        super().__init__()
        self._on_files_dropped = on_files_dropped
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(120)
        self.setStyleSheet(
            "QFrame { border: 2px dashed #999; border-radius: 8px; background: #fafafa; }"
        )
        layout = QVBoxLayout(self)
        label = QLabel("오늘 발주요청서 파일을 여기에 끌어다 놓으세요.")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("border: none; color: #666; font-size: 14px;")
        layout.addWidget(label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        excel_paths = [p for p in paths if p.suffix.lower() in (".xlsx", ".xlsm", ".xls")]
        if excel_paths:
            self._on_files_dropped(excel_paths)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("팜마켓 발주 송금요청 생성기")
        self.resize(1000, 750)

        self.rules: SupplierRules = SupplierRules()
        self.catalog: MasterCatalog | None = None
        self.master_path: Path | None = None
        self.added_files: list[Path] = []
        self.dup_tracker = DuplicateFileTracker()
        self.last_result: PipelineResult | None = None

        self._build_ui()
        self._load_master()

    # ---- UI 구성 ----
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("팜마켓 발주 송금요청 생성기")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        self.master_status_label = QLabel("발주정보 확인 중...")
        root.addWidget(self.master_status_label)

        self.drop_area = DropArea(self._add_files)
        root.addWidget(self.drop_area)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("파일 추가")
        add_btn.clicked.connect(self._choose_files)
        clear_btn = QPushButton("전체 삭제")
        clear_btn.clicked.connect(self._clear_files)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(90)
        root.addWidget(self.file_list)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["구분", "업체", "상품", "수량", "배송지", "배송비", "송금액", "상태"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

        self.issues_box = QTextEdit()
        self.issues_box.setReadOnly(True)
        self.issues_box.setMaximumHeight(90)
        self.issues_box.setPlaceholderText("오류/경고가 여기에 표시됩니다.")
        root.addWidget(self.issues_box)

        root.addWidget(QLabel("송금 요청 메시지"))
        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        root.addWidget(self.message_box)

        bottom_row = QHBoxLayout()
        self.copy_btn = QPushButton("송금요청 복사")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_message)
        self.save_btn = QPushButton("TXT 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_message)
        self.total_label = QLabel("총 송금액: -")
        self.total_label.setStyleSheet("font-weight: bold;")
        bottom_row.addWidget(self.copy_btn)
        bottom_row.addWidget(self.save_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(self.total_label)
        root.addLayout(bottom_row)

        self.status_label = QLabel("")
        root.addWidget(self.status_label)

    # ---- 마스터 로드 ----
    def _load_master(self) -> None:
        self.rules = load_supplier_rules(resolve_supplier_rules_path())

        master_path = find_master_file()
        if master_path is None:
            master_path = self._ask_for_master_file()

        if master_path is None:
            self.master_status_label.setText("⚠ 발주정보 파일을 찾을 수 없습니다.")
            self.master_status_label.setStyleSheet("color: #b00020; font-weight: bold;")
            return

        try:
            self.catalog = load_master_catalog(master_path, self.rules)
            self.master_path = master_path
            remember_master_file(master_path)
            self.master_status_label.setText(f"발주정보: 정상 로드됨 ({master_path.name})")
            self.master_status_label.setStyleSheet("color: #1a7f37;")
        except Exception as exc:  # noqa: BLE001
            self.master_status_label.setText(f"⚠ 발주정보 파일을 읽을 수 없습니다: {exc}")
            self.master_status_label.setStyleSheet("color: #b00020; font-weight: bold;")

    def _ask_for_master_file(self) -> Path | None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "발주정보 마스터 파일 선택", str(app_base_dir()), "Excel Files (*.xlsx)"
        )
        return Path(path_str) if path_str else None

    # ---- 파일 추가/삭제 ----
    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "발주요청서 파일 선택", str(Path.home()), "Excel Files (*.xlsx *.xlsm *.xls)"
        )
        if paths:
            self._add_files([Path(p) for p in paths])

    def _add_files(self, paths: list[Path]) -> None:
        if self.catalog is None:
            QMessageBox.warning(self, "발주정보 없음", "발주정보 마스터 파일을 먼저 불러와야 합니다.")
            return

        added_any = False
        for path in paths:
            if self.dup_tracker.is_duplicate(path):
                self.status_label.setText(f"이미 추가된 발주요청서입니다: {path.name}")
                continue
            self.added_files.append(path)
            self.file_list.addItem(path.name)
            added_any = True

        if added_any:
            self._recalculate()

    def _clear_files(self) -> None:
        self.added_files.clear()
        self.file_list.clear()
        self.dup_tracker.reset()
        self.table.setRowCount(0)
        self.issues_box.clear()
        self.message_box.clear()
        self.total_label.setText("총 송금액: -")
        self.copy_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("")

    # ---- 계산/표시 ----
    def _recalculate(self) -> None:
        assert self.catalog is not None
        result = process_files(self.added_files, self.catalog, self.rules)
        self.last_result = result
        self._populate_table(result)
        self._populate_issues(result)

        if result.has_blocking_error:
            self.message_box.setPlainText("⚠ 오류가 있어 송금요청 메시지를 생성하지 않았습니다. 위 문제를 먼저 해결하세요.")
            self.copy_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
        else:
            message = build_remittance_message(result.supplier_results, self.rules)
            self.message_box.setPlainText(message)
            self.copy_btn.setEnabled(bool(message))
            self.save_btn.setEnabled(bool(message))

        self.total_label.setText(f"총 송금액: {result.total_amount:,.0f}원")

    def _populate_table(self, result: PipelineResult) -> None:
        rows = []
        for company, r in result.supplier_results.items():
            section = "나는농부" if r.source_sheet == SELF_SUPPLY_SHEET else "무무식탁"
            status = "정상" if r.is_valid else "오류"
            if not r.breakdown:
                rows.append((section, r.display_name, "-", "-", "-", "-", "-", status))
            for item in r.breakdown:
                qty = f"{item.quantity:g}"
                shipping = "-" if r.is_self_supply else (
                    f"{r.shipping_fee_per_shipment:,.0f}" if r.shipping_fee_per_shipment else "-"
                )
                ship_count = "-" if r.is_self_supply else str(r.shipment_count)
                rows.append(
                    (
                        section,
                        r.display_name,
                        item.product_name,
                        qty,
                        ship_count,
                        shipping,
                        f"{r.grand_total:,.0f}",
                        status,
                    )
                )

        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                cell = QTableWidgetItem(str(value))
                if col_idx == 7 and value == "오류":
                    cell.setForeground(Qt.red)
                self.table.setItem(row_idx, col_idx, cell)

    def _populate_issues(self, result: PipelineResult) -> None:
        lines = []
        for issue in result.top_level_issues:
            lines.append(f"[{issue.severity.upper()}] {issue.message}")
        for r in result.supplier_results.values():
            for issue in r.issues:
                lines.append(f"[{issue.severity.upper()}] ({r.display_name}) {issue.message}")
        self.issues_box.setPlainText("\n".join(lines) if lines else "문제 없음")

    # ---- 결과 사용 ----
    def _copy_message(self) -> None:
        text = self.message_box.toPlainText()
        clipboard: QClipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.status_label.setText("송금 요청문을 복사했습니다.")

    def _save_message(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(self, "TXT로 저장", "송금요청.txt", "Text Files (*.txt)")
        if path_str:
            Path(path_str).write_text(self.message_box.toPlainText(), encoding="utf-8")
            self.status_label.setText(f"저장했습니다: {path_str}")


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
