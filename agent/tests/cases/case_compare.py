"""confirmed 사례를 읽어 단계마다 비교 줄을 만든다(비교 / PR 5로 미룸 / 입력으로 씀 / 제외).

비교 단계는 Issue #13 "사례 테스트"의 목록이다. 나머지(과세표준·산출세액·결정세액,
의료비·교육비·카드 등)는 지우지 않고 "PR 5에서 비교"로 센다.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from cases.case_convert import Run, hometax_runs, nts_runs
from taxsplit.engine import Rulebook, TaxResult, compute_tax
from taxsplit.engine.credits import earned_income_tax_credit
from taxsplit.rules.loader import load_rules

CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "cases"
SOURCES = {"nts-2025": "국세청 사례", "hometax-2025": "홈택스"}

Getter = Callable[[TaxResult], Any]
# 사람 전체 값을 읽는 단계
TOTAL_STAGES: dict[str, Getter] = {
    "gross_salary": lambda r: r.gross_salary,
    "earned_income_deduction": lambda r: r.earned_income_deduction,
    "earned_income_amount": lambda r: r.earned_income_amount,
    "basic_deduction_count": lambda r: r.personal.basic_count,
    "basic_deduction_total": lambda r: r.personal.basic_total,
    "basic_deduction_self": lambda r: r.personal.basic_self,
    "basic_deduction_dependents_count": lambda r: r.personal.basic_count - 1,
    "basic_deduction_dependents": lambda r: r.personal.basic_dependents,
    "additional_deduction_elderly_count": lambda r: r.personal.elderly_count,
    "additional_deduction_elderly": lambda r: r.personal.elderly,
    "additional_deduction_disabled_count": lambda r: r.personal.disabled_count,
    "additional_deduction_disabled": lambda r: r.personal.disabled,
    "additional_deduction_woman": lambda r: r.personal.woman,
    "personal_deduction_total": lambda r: r.personal.total,
    "pension_insurance_deduction": lambda r: r.pension_insurance_deduction,
    "insurance_premium_deduction": lambda r: r.insurance_premium_deduction,
    "earned_income_credit_limit": lambda r: r.earned_income_credit.limit,
    "child_credit_age8plus_count": lambda r: r.child_credit.age8plus_count,
    "child_credit_age8plus": lambda r: r.child_credit.age8plus,
    "child_credit_birth_count": lambda r: r.child_credit.birth_count,
    "child_credit_birth": lambda r: r.child_credit.birth,
    "child_credit": lambda r: r.child_credit.total,
}
# 부양가족 한 명의 값을 묻는 사례(p99·p100)에서 그 사람 값을 읽는 단계
TARGET_STAGES = {
    "basic_deduction_person": lambda d: d.basic,
    "additional_deduction_disabled": lambda d: d.disabled,
    "additional_deduction_elderly": lambda d: d.elderly,
    "personal_deduction_person_total": lambda d: d.basic + d.elderly + d.disabled,
    "spouse_basic_deduction_eligible": lambda d: d.eligible,
}
INPUT_STAGES = {"total_pay", "nontaxable_total"}


@dataclass(frozen=True)
class Row:
    source: str
    case: str
    stage: str
    group: str
    kind: str  # compare | deferred | input | excluded
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


def _rows(source: str, run: Run, rules) -> list[Row]:
    result = compute_tax(run.worker, rules) if run.worker else None
    target = None
    if result and run.target:
        target = next(d for d in result.personal.dependents if d.name == run.target)
    credit = None
    if run.credit_inputs:
        credit = earned_income_tax_credit(*run.credit_inputs, Rulebook(rules))
    rows = []
    for e in run.expected:
        stage, value = e["stage"], e["value"]
        actual, kind = None, "deferred"
        if stage in INPUT_STAGES or (stage == "gross_salary" and run.gross_is_input):
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
        elif result and stage in TOTAL_STAGES:
            kind, actual = "compare", TOTAL_STAGES[stage](result)
        rows.append(Row(source, run.label, stage, group_of(stage), kind, value, actual))
    for e in run.excluded:
        rows.append(
            Row(source, run.label, e["stage"], group_of(e["stage"]), "excluded", e["value"])
        )
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
