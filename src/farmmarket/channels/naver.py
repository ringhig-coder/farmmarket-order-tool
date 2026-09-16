"""네이버 커머스 API 연동 (인증 + 신규주문 조회 + 발주확인 + 수취인정보 조회).

주의: confirm_orders()는 실제 거래에 영향을 주는 진짜 업무 처리다 (읽기 전용 조회가 아님).
한 번 호출하면 해당 주문의 배송 기한 타이머가 시작되는 등 되돌리기 어려운 절차가 진행된다.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import time
from dataclasses import dataclass
from pathlib import Path

import bcrypt
import requests

from ..models import OrderLine

_BASE = "https://api.commerce.naver.com/external"
KST = dt.timezone(dt.timedelta(hours=9))


@dataclass
class NaverCredentials:
    client_id: str
    client_secret: str

    @classmethod
    def load(cls, path: Path) -> "NaverCredentials":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(client_id=data["client_id"], client_secret=data["client_secret"])


def get_access_token(creds: NaverCredentials) -> str:
    timestamp = str(int((time.time() - 3) * 1000))
    password = f"{creds.client_id}_{timestamp}"
    hashed = bcrypt.hashpw(password.encode("utf-8"), creds.client_secret.encode("utf-8"))
    sign = base64.standard_b64encode(hashed).decode("utf-8")
    data = {
        "client_id": creds.client_id,
        "timestamp": timestamp,
        "client_secret_sign": sign,
        "grant_type": "client_credentials",
        "type": "SELF",
    }
    resp = requests.post(
        f"{_BASE}/v1/oauth2/token",
        data=data,
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def list_new_orders(token: str, since: dt.datetime) -> list[str]:
    """결제완료(PAYED) 상태인 주문의 productOrderId 목록을 가져온다 (발주확인 전 상태 포함).

    네이버 API는 from~to를 최대 24시간까지만 허용해서, 그보다 긴 기간이면 24시간 단위로 나눠 호출한다.
    """
    headers = {"Authorization": f"Bearer {token}"}
    now = dt.datetime.now(dt.timezone.utc)
    window = dt.timedelta(hours=24)

    product_order_ids: list[str] = []
    window_start = since
    while window_start < now:
        window_end = min(window_start + window, now)
        frm = window_start.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S.000+09:00")
        to = window_end.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S.000+09:00")

        page = 1
        while True:
            resp = requests.get(
                f"{_BASE}/v1/pay-order/seller/product-orders",
                headers=headers,
                params={"from": frm, "to": to, "rangeType": "PAYED_DATETIME", "page": page, "size": 300},
                timeout=15,
            )
            resp.raise_for_status()
            contents = resp.json()["data"]["contents"]
            for item in contents:
                status = item["content"]["productOrder"]["productOrderStatus"]
                if status == "PAYED":
                    product_order_ids.append(item["productOrderId"])
            if len(contents) < 300:
                break
            page += 1

        window_start = window_end

    return product_order_ids


def confirm_orders(token: str, product_order_ids: list[str]) -> dict:
    """⚠ 실제 발주확인 처리. 호출 전에 사용자 확인을 반드시 거칠 것."""
    if not product_order_ids:
        return {}
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    resp = requests.post(
        f"{_BASE}/v1/pay-order/seller/product-orders/confirm",
        headers=headers,
        json={"productOrderIds": product_order_ids},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_order_details(token: str, product_order_ids: list[str]) -> list[dict]:
    """발주확인된 주문의 상세정보(수취인 포함)를 가져온다. 확인 전이면 shippingAddress가 없을 수 있다."""
    if not product_order_ids:
        return []
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    resp = requests.post(
        f"{_BASE}/v1/pay-order/seller/product-orders/query",
        headers=headers,
        json={"productOrderIds": product_order_ids},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def order_details_to_lines(details: list[dict]) -> tuple[list[OrderLine], list[str]]:
    """네이버 주문 상세 목록 -> 내부 OrderLine 목록. 수취인 정보가 아직 없는(미확인) 주문은
    건너뛰고 productOrderId를 별도로 반환한다 (임의로 계산하지 않고 알려주기 위함)."""
    lines: list[OrderLine] = []
    pending: list[str] = []

    for detail in details:
        product_order = detail["productOrder"]
        shipping = product_order.get("shippingAddress")
        pid = product_order["productOrderId"]
        if not shipping:
            pending.append(pid)
            continue

        address = shipping.get("baseAddress", "")
        detailed = shipping.get("detailedAddress")
        full_address = f"{address} {detailed}".strip() if detailed else address

        lines.append(
            OrderLine(
                source_file=f"naver:{pid}",
                company_hint=None,
                recipient=shipping.get("name"),
                address=full_address,
                phone=shipping.get("tel1"),
                quantity=float(product_order["quantity"]),
                quantity_unit="unit",
                product_name_raw=product_order["productName"],
                note=None,
            )
        )
    return lines, pending
