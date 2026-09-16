"""네이버 스마트스토어 신규주문 -> 업체별 발주요청서 자동 생성.

기본은 안전하게 '무엇을 할지 미리보기만' 하는 모드다 (--confirm 없이 실행).
실제로 발주확인까지 자동으로 돌리려면 --confirm을 붙여야 한다.
이 스크립트는 사용자가 직접 자기 터미널에서 실행하는 용도다.

사용법:
    python automation/generate_orders_from_naver.py                # 미리보기만 (발주확인 안 함)
    python automation/generate_orders_from_naver.py --confirm      # 실제로 발주확인까지 자동 처리
    python automation/generate_orders_from_naver.py --since-hours 48
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from farmmarket.channels.naver import (  # noqa: E402
    NaverCredentials,
    confirm_orders,
    fetch_order_details,
    get_access_token,
    list_new_orders,
    order_details_to_lines,
)
from farmmarket.config import load_supplier_rules  # noqa: E402
from farmmarket.master import load_master_catalog  # noqa: E402
from farmmarket.order_generation import generate_supplier_orders  # noqa: E402
from farmmarket.order_writer import load_output_templates  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = PROJECT_ROOT / "data" / "master" / "💰팜마켓 발주정보.xlsx"
CREDS_PATH = PROJECT_ROOT / "secrets" / "naver_api.json"
LOG_PATH = PROJECT_ROOT / "automation" / "naver_confirm_log.txt"
PRODUCT_MAP_PATH = PROJECT_ROOT / "config" / "naver_product_map.json"


def load_product_map(path: Path) -> dict:
    import json

    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def log_confirmed(product_order_ids: list[str]) -> None:
    if not product_order_ids:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        for pid in product_order_ids:
            f.write(f"{timestamp}\t{pid}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-hours", type=int, default=24, help="이 시간(시간 단위) 이내 결제된 주문을 조회 (기본 24시간)")
    parser.add_argument("--confirm", action="store_true", help="실제로 발주확인까지 자동 처리 (기본은 미리보기만)")
    parser.add_argument("--out-dir", type=str, default=str(PROJECT_ROOT / "output"), help="발주서 저장 폴더")
    args = parser.parse_args()

    if not CREDS_PATH.exists():
        print(f"⚠ 네이버 API 인증정보가 없습니다: {CREDS_PATH}")
        return 1
    if not MASTER_PATH.exists():
        print(f"⚠ 발주정보 마스터 파일을 찾을 수 없습니다: {MASTER_PATH}")
        return 1

    creds = NaverCredentials.load(CREDS_PATH)
    rules = load_supplier_rules(PROJECT_ROOT / "config" / "supplier_rules.json")
    catalog = load_master_catalog(MASTER_PATH, rules)
    templates = load_output_templates(PROJECT_ROOT / "config" / "output_templates.json")

    token = get_access_token(creds)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.since_hours)
    pending_ids = list_new_orders(token, since)

    if not pending_ids:
        print("새로 결제된 주문이 없습니다.")
        return 0

    print(f"결제완료(PAYED) 상태 주문 {len(pending_ids)}건 발견.")

    if args.confirm:
        print("발주확인 처리 중...")
        confirm_orders(token, pending_ids)
        log_confirmed(pending_ids)
        print("발주확인 완료. 수취인 정보 반영 대기 중...")
        time.sleep(20)
    else:
        print("(--confirm 옵션이 없어서 발주확인은 하지 않았습니다. 이미 수동으로 확인된 주문만 처리합니다.)")

    details = fetch_order_details(token, pending_ids)
    product_map = load_product_map(PRODUCT_MAP_PATH)
    lines, still_pending = order_details_to_lines(details, product_map)

    if still_pending:
        print(f"\n⚠ 아직 발주확인이 안 되어 수취인 정보가 없는 주문 {len(still_pending)}건 (건너뜀):")
        for pid in still_pending:
            print(f"   {pid}")

    if not lines:
        print("\n처리할 주문이 없습니다.")
        return 0

    report = generate_supplier_orders(lines, catalog, rules, templates, Path(args.out_dir))

    print(f"\n생성된 발주서 파일 {len(report.files_written)}개:")
    for p in report.files_written:
        print(f"   {p}")

    if report.unmatched_products:
        print(f"\n⚠ 상품 매칭 실패 {len(report.unmatched_products)}건 (수동 확인 필요):")
        for issue in report.unmatched_products:
            print(f"   {issue.message}")

    if report.no_template_companies:
        print("\n⚠ 마스터에는 있지만 출력 양식이 없는 업체 (config/output_templates.json에 추가 필요):")
        for company, count in report.no_template_companies.items():
            print(f"   {company}: {count}건")

    return 1 if report.has_unhandled or still_pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
