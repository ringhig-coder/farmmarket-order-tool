"""GUI 실행 진입점. PyInstaller 빌드 대상도 이 파일이다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from farmmarket.gui import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
