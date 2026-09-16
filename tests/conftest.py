import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pytest

from farmmarket.config import load_supplier_rules
from farmmarket.master import load_master_catalog


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def rules(project_root):
    return load_supplier_rules(project_root / "config" / "supplier_rules.json")


@pytest.fixture(scope="session")
def catalog(project_root, rules):
    master_path = project_root / "data" / "master" / "💰팜마켓 발주정보.xlsx"
    if not master_path.exists():
        # 마스터 파일은 로그인정보가 들어있어 git에 올리지 않는다 (.gitignore 참고).
        # CI 등 이 파일이 없는 환경에서는 마스터가 필요한 테스트를 건너뛴다.
        pytest.skip("마스터 파일이 없어 건너뜀 (data/master/에 로컬로만 존재, git에는 커밋하지 않음)")
    return load_master_catalog(master_path, rules)


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
