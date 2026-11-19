"""confirmed 사례를 읽어 단계마다 비교 줄을 만든다(비교 / 범위 밖 / 입력으로 씀 / 제외 / 입력 부족).

PR 5부터 결정세액까지 비교한다. 5그룹 밖 단계 값은 엔진 입력으로 옮겨 "입력으로 씀"으로,
환급·납부세액처럼 이번 범위 밖 단계는 "범위 밖"으로 센다(Issue #14).
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cases.case_convert import nts_runs
from cases.case_convert_hometax import hometax_runs
from cases.case_convert_items import OUT_OF_SCOPE_STAGES as MOVED_TO_INPUT
from cases.case_run import Run
from cases.case_stages import ITEM_STAGES, OUT_OF_SCOPE_STAGES, TARGET_STAGES, TOTAL_STAGES
from taxsplit.engine import Rulebook, compute_tax
from taxsplit.engine.card import card_deduction
from taxsplit.engine.credits import earned_income_tax_credit
from taxsplit.engine.education import education_credit
from taxsplit.engine.medical import medical_credit
from taxsplit.rules.loader import load_rules

CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "cases"
SOURCES = {"nts-2025": "국세청 사례", "hometax-2025": "홈택스"}

INPUT_STAGES = {"total_pay", "nontaxable_total", *MOVED_TO_INPUT}
ITEM_FUNCS = {"medical": medical_credit, "education": education_credit, "card": card_deduction}


@dataclass(frozen=True)
class Row:
    source: str
    case: str
    stage: str
    group: str
    kind: str  # compare | out_of_scope | input | excluded | missing_input
    expected: Any = None
    actual: Any = None

    @property
    def ok(self) -> bool:
        return self.kind == "compare" and self.expected == self.actual


def group_of(stage: str) -> str:
    if stage.startswith("child_credit"):
        return "자녀"
    if stage.startswith(
        ("basic_deduction", "additional_deduction", "personal_deduction", "spouse")
    ):
        return "부양가족"
    for prefix, name in (("medical", "의료비"), ("education", "교육비"), ("card", "카드")):
        if stage.startswith(prefix):
            return name
    if stage.startswith("comprehensive_limit") or stage == "other_income_deduction":
        return "카드"
    return "기본 흐름"


def _item_result(run: Run, rules) -> SimpleNamespace:
    """항목 사례: 그 항목 계산만 불러 r.medical / r.education / r.card 모양으로 돌려준다."""
    return SimpleNamespace(**{run.item: ITEM_FUNCS[run.item](run.worker, Rulebook(rules))})


def _rows(source: str, run: Run, rules) -> list[Row]:
    result = None
    if run.worker and run.item:
        result = _item_result(run, rules)
    elif run.worker:
        result = compute_tax(run.worker, rules)
    target = None
    if result and run.target:
        target = next(d for d in result.personal.dependents if d.name == run.target)
    credit = None
    if run.credit_inputs:
        credit = earned_income_tax_credit(*run.credit_inputs, Rulebook(rules))
    rows = []
    for e in run.expected:
        stage, value = e["stage"], e["value"]
        actual, kind = None, "unknown"
        if stage in OUT_OF_SCOPE_STAGES:
            kind = "out_of_scope"
        elif stage in INPUT_STAGES or (stage == "gross_salary" and run.gross_is_input):
            kind = "input"
        elif credit and stage.startswith("earned_income_credit"):
            kind = "compare"
            actual = {
                "earned_income_credit_before_limit": credit.before_limit,
                "earned_income_credit_limit": credit.limit,
                "earned_income_credit": credit.amount,
            }[stage]
        elif target and stage in TARGET_STAGES:
            kind, actual = "compare", TARGET_STAGES[stage](target)
        elif result and run.item and stage in ITEM_STAGES:
            kind, actual = "compare", ITEM_STAGES[stage](result)
        elif result and not run.item and stage in TOTAL_STAGES:
            kind, actual = "compare", TOTAL_STAGES[stage](result)
        rows.append(Row(source, run.label, stage, group_of(stage), kind, value, actual))
    for kind, extra in (("excluded", run.excluded), ("missing_input", run.missing)):
        for e in extra:
            rows.append(Row(source, run.label, e["stage"], group_of(e["stage"]), kind, e["value"]))
    return rows


@cache
def load_cases() -> tuple[tuple[str, dict], ...]:
    """confirmed 사례만 읽는다. draft는 채점·비교에 쓰지 않는다."""
    out = []
    for folder in SOURCES:
        for path in sorted((CASES_DIR / folder).glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            if case["status"] == "confirmed":
                out.append((folder, case))
    return tuple(out)


@cache
def all_runs() -> tuple[tuple[str, Run], ...]:
    out = []
    for folder, case in load_cases():
        runs = nts_runs(case) if folder == "nts-2025" else hometax_runs(case)
        out.extend((SOURCES[folder], run) for run in runs)
    return tuple(out)


@cache
def all_rows() -> tuple[Row, ...]:
    rules = load_rules(2025)
    return tuple(row for source, run in all_runs() for row in _rows(source, run, rules))
