"""파일 목록 -> 파싱 -> 계산까지 한 번에 묶는 진입점 (GUI/CLI 공용)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import SupplierRules, load_supplier_rules
from .engine import calculate
from .filename_hint import extract_company_hint
from .master import MasterCatalog, load_master_catalog
from .models import OrderLine, SupplierResult, ValidationIssue
from .parsers.base import file_hash
from .parsers.detect import parse_order_file


@dataclass
class PipelineResult:
    supplier_results: dict[str, SupplierResult] = field(default_factory=dict)
    top_level_issues: list[ValidationIssue] = field(default_factory=list)
    parsed_line_count: int = 0

    @property
    def has_blocking_error(self) -> bool:
        if self.top_level_issues and any(i.severity == "error" for i in self.top_level_issues):
            return True
        return any(r.errors for r in self.supplier_results.values())

    @property
    def total_amount(self) -> float:
        return sum(r.grand_total for r in self.supplier_results.values() if r.is_valid)


class DuplicateFileTracker:
    def __init__(self) -> None:
        self._hashes: set[str] = set()

    def is_duplicate(self, path: Path) -> bool:
        h = file_hash(path)
        if h in self._hashes:
            return True
        self._hashes.add(h)
        return False

    def reset(self) -> None:
        self._hashes.clear()


def load_master(master_path: Path, rules: SupplierRules) -> MasterCatalog:
    return load_master_catalog(master_path, rules)


def process_files(
    file_paths: list[Path], catalog: MasterCatalog, rules: SupplierRules
) -> PipelineResult:
    all_lines: list[OrderLine] = []
    top_level_issues: list[ValidationIssue] = []

    for path in file_paths:
        hint = extract_company_hint(path.name, rules)
        parse_result = parse_order_file(path)
        top_level_issues.extend(parse_result.issues)
        for line in parse_result.lines:
            line.company_hint = hint
        all_lines.extend(parse_result.lines)

    results, calc_top_level_issues = calculate(all_lines, catalog, rules)
    top_level_issues.extend(calc_top_level_issues)

    return PipelineResult(
        supplier_results=results,
        top_level_issues=top_level_issues,
        parsed_line_count=len(all_lines),
    )


def default_rules_path(project_root: Path) -> Path:
    return project_root / "config" / "supplier_rules.json"
