"""규칙 커버리지: 규칙표의 규칙 ID마다 "바깥 정답 사례가 몇 개 지나갔나"를 센다.

PR 무게 판정 (라)가 쓴다(CLAUDE.md "PR 무게"). 테스트 쪽에만 둔다(처리 코드는 사례를 모른다).

센 기준:
- confirmed 사례(국세청 사례·홈택스)를 엔진에 돌려 결과의 rules_used(단계별 규칙 ID)를 본다.
- 사례가 **실제로 비교한 단계**에서 쓴 규칙만 센다. 예: 기본공제만 비교하는 사례가 계산 중에
  지나간 세율 규칙은 세지 않는다(지나가기만 하고 확인받지 않았으므로).
- 셈 단위는 사례 파일 하나. 같은 사례의 부부·소문항은 한 번으로 센다.

사용법 (agent/에서):
    uv run python tests/cases/rule_coverage.py          # 표
    uv run python tests/cases/rule_coverage.py --json   # {규칙 ID: 사례 수}
"""

import json
import sys
from pathlib import Path

if __name__ == "__main__":  # 스크립트로 돌릴 때도 tests/ 아래 cases 패키지를 찾게 한다
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cases.case_compare import all_rows, all_runs
from taxsplit.engine import Rulebook, compute_tax
from taxsplit.engine.credits import earned_income_tax_credit
from taxsplit.rules.loader import load_rules

# 사례의 비교 단계 → 그 값을 낸 엔진 단계(rules_used의 키).
# 새 비교 단계가 생기면 여기 없어서 test_rule_coverage가 깨진다(PR 5에서 의료비 등을 넣을 때).
CASE_TO_ENGINE: dict[str, tuple[str, ...]] = {
    "gross_salary": (),  # 입력을 그대로 돌려주는 값이라 규칙이 없다
    "earned_income_deduction": ("earned_income_deduction",),
    "earned_income_amount": ("earned_income_deduction",),
    "pension_insurance_deduction": ("pension_insurance_deduction",),
    "insurance_premium_deduction": ("insurance_premium_deduction",),
    "earned_income_credit": ("earned_income_credit",),
    "earned_income_credit_before_limit": ("earned_income_credit",),
    "earned_income_credit_limit": ("earned_income_credit",),
    **{
        s: ("personal_deduction",)
        for s in (
            "basic_deduction_count",
            "basic_deduction_total",
            "basic_deduction_self",
            "basic_deduction_dependents_count",
            "basic_deduction_dependents",
            "basic_deduction_person",
            "additional_deduction_elderly_count",
            "additional_deduction_elderly",
            "additional_deduction_disabled_count",
            "additional_deduction_disabled",
            "additional_deduction_woman",
            "personal_deduction_total",
            "personal_deduction_person_total",
            "spouse_basic_deduction_eligible",
        )
    },
    **{
        s: ("child_credit",)
        for s in (
            "child_credit",
            "child_credit_age8plus_count",
            "child_credit_age8plus",
            "child_credit_birth_count",
            "child_credit_birth",
        )
    },
}


def case_file_of(label: str) -> str:
    """실행 이름("<사례>#q1", "<사례>/husband")에서 사례 파일 이름만 남긴다."""
    return label.split("#")[0].split("/")[0]


def _rules_used(run, rules) -> dict[str, tuple[str, ...]]:
    if run.worker is not None:
        return compute_tax(run.worker, rules).rules_used
    if run.credit_inputs:
        book = Rulebook(rules)
        earned_income_tax_credit(*run.credit_inputs, book)
        return book.rules_used()
    return {}


def coverage() -> dict[str, int]:
    """{규칙 ID: 그 규칙을 비교 단계에서 지나간 사례 파일 수}. 규칙표의 모든 ID가 들어간다."""
    rules = load_rules(2025)
    compared: dict[str, set[str]] = {}
    for row in all_rows():
        if row.kind == "compare":
            compared.setdefault(row.case, set()).add(row.stage)
    hits: dict[str, set[str]] = {rule_id: set() for rule_id in rules}
    for _, run in all_runs():
        stages = compared.get(run.label)
        if not stages:
            continue
        used = _rules_used(run, rules)
        for stage in stages:
            for engine_stage in CASE_TO_ENGINE[stage]:
                for rule_id in used.get(engine_stage, ()):
                    hits[rule_id].add(case_file_of(run.label))
    return {rule_id: len(cases) for rule_id, cases in sorted(hits.items())}


def main(argv: list[str]) -> None:
    result = coverage()
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("| 규칙 ID | 지나간 사례 수 |\n| --- | --- |")
    for rule_id, n in result.items():
        print(f"| {rule_id} | {n} |")


if __name__ == "__main__":
    main(sys.argv[1:])
