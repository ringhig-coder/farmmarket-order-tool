from __future__ import annotations

import re
from pathlib import Path

from .config import SupplierRules

_IGNORE_TOKENS = {"무무식탁", "나는농부", "팜마켓", "발주요청서", "발주서", "발주정보"}


def extract_company_hint(filename: str, rules: SupplierRules) -> str | None:
    """파일명에서 업체명을 추정한다 (검증용 힌트일 뿐, 최종 판단은 상품명으로 한다 - 섹션 24)."""
    stem = Path(filename).stem
    tokens = [t for t in re.split(r"[_\-\s]+", stem) if t]
    candidates = []
    for tok in tokens:
        if tok in _IGNORE_TOKENS:
            continue
        if re.fullmatch(r"\d+(\.\d+)*", tok):  # 260916, 26.09.16 같은 날짜류
            continue
        candidates.append(tok)
    if not candidates:
        return None
    first = candidates[0]
    return rules.company_aliases.get(first, first)
