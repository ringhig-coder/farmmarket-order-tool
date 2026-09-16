"""GUI 없이 계산 엔진만 커맨드라인으로 확인하는 도구 (STEP 3용).

사용법:
    python cli.py 발주요청서1.xlsx 발주요청서2.xlsx ...
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from farmmarket.config import load_supplier_rules
from farmmarket.formatter import build_remittance_message
from farmmarket.pipeline import default_rules_path, load_master, process_files

PROJECT_ROOT = Path(__file__).resolve().parent
MASTER_PATH = PROJECT_ROOT / "data" / "master" / "💰팜마켓 발주정보.xlsx"


def main(argv: list[str]) -> int:
    if not argv:
        print("사용법: python cli.py 발주요청서1.xlsx [발주요청서2.xlsx ...]")
        return 1
    if not MASTER_PATH.exists():
        print(f"⚠ 발주정보 파일을 찾을 수 없습니다: {MASTER_PATH}")
        return 1

    rules = load_supplier_rules(default_rules_path(PROJECT_ROOT))
    catalog = load_master(MASTER_PATH, rules)

    files = [Path(p) for p in argv]
    result = process_files(files, catalog, rules)

    print(f"\n총 {result.parsed_line_count}개 주문 라인 파싱됨\n")

    for company, r in result.supplier_results.items():
        status = "정상" if r.is_valid else "오류"
        print(f"[{r.display_name}] 상태={status} 상품수={len(r.breakdown)} 배송지={r.shipment_count} 송금액={r.grand_total:,.0f}원")
        for issue in r.issues:
            print(f"   {issue.severity.upper()}: {issue.message}")

    if result.top_level_issues:
        print("\n=== 업체를 결정하지 못한 오류 ===")
        for issue in result.top_level_issues:
            print(f"   {issue.severity.upper()}: {issue.message} ({issue.source_file})")

    print("\n=== 송금 요청 메시지 ===\n")
    if result.has_blocking_error:
        print("⚠ 오류가 있어 송금요청 메시지를 생성하지 않았습니다. 위 오류를 먼저 해결하세요.")
    else:
        print(build_remittance_message(result.supplier_results, rules))
        print(f"\n(참고용) 총 송금액: {result.total_amount:,.0f}원")

    return 1 if result.has_blocking_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
