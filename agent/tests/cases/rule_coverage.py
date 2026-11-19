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

from cases.case_compare import ITEM_FUNCS, all_rows, all_runs
from cases.case_stages import ITEM_STAGES
from taxsplit.engine import Rulebook, compute_tax
from taxsplit.engine.credits import earned_income_tax_credit
from taxsplit.rules.loader import load_rules

# 의료비·교육비·카드 단계 이름(case_stages.ITEM_STAGES 키를 앞 글자로 나눔)
_STAGE_NAMES = {
    g: tuple(s for s in ITEM_STAGES if s.startswith(g)) for g in ("medical", "education", "card")
}
# 합계 단계가 거쳐 온 엔진 단계. 합계가 맞으면 그 길의 규칙이 모두 확인받은 것으로 센다
_INCOME_DEDUCTIONS = (
    "personal_deduction",
    "pension_insurance_deduction",
    "insurance_premium_deduction",
)
_TAXABLE = (
    "earned_income_deduction",
    *_INCOME_DEDUCTIONS,
    "card_deduction",
    "combined_limit",
    "taxable_income",
)
_SPECIAL_CREDITS = ("medical_credit", "education_credit", "standard_tax_credit")
_DETERMINED = (*_TAXABLE, "computed_tax", "earned_income_credit", "child_credit", *_SPECIAL_CREDITS)

# 사례의 비교 단계 → 그 값을 낸 엔진 단계(rules_used의 키).
# 새 비교 단계가 생기면 여기 없어서 test_rule_coverage가 깨진다.
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
    # PR 5: 의료비·교육비·카드는 그 항목 계산, 합계·세액은 거쳐 온 단계 전부
    **{s: ("medical_credit",) for s in _STAGE_NAMES["medical"]},
    **{s: ("education_credit",) for s in _STAGE_NAMES["education"]},
    **{s: ("card_deduction",) for s in _STAGE_NAMES["card"]},
    "other_income_deduction": ("card_deduction", "combined_limit"),
    "comprehensive_limit_target": ("insurance_premium_deduction", "card_deduction"),
    "comprehensive_limit_excess": (
        "insurance_premium_deduction",
        "card_deduction",
        "combined_limit",
    ),
    "special_income_deduction_total": (
        "pension_insurance_deduction",
        "insurance_premium_deduction",
    ),
    "comprehensive_income_deduction": _INCOME_DEDUCTIONS,
    "income_deduction_total": _TAXABLE[1:-1],
    "income_after_deductions": _TAXABLE[:-1],
    "taxable_income": _TAXABLE,
    "computed_tax": (*_TAXABLE, "computed_tax"),
    "special_tax_credit_total": _SPECIAL_CREDITS,
    "tax_credit_total": ("earned_income_credit", "child_credit", *_SPECIAL_CREDITS),
    "determined_tax": _DETERMINED,
}


def case_file_of(label: str) -> str:
    """실행 이름("<사례>#q1", "<사례>/husband")에서 사례 파일 이름만 남긴다."""
    return label.split("#")[0].split("/")[0]


def _rules_used(run, rules) -> dict[str, tuple[str, ...]]:
    if run.worker is not None and run.item:
        # 항목 사례는 비교할 때처럼 그 항목 계산만 부른다
        book = Rulebook(rules)
        ITEM_FUNCS[run.item](run.worker, book)
        return book.rules_used()
    if run.worker is not None:
        return compute_tax(run.worker, rules).rules_used
    if run.credit_inputs:
        book = Rulebook(rules)
        earned_income_tax_credit(*run.credit_inputs, book)
        return book.rules_used()
    return {}


def coverage(rows=None, runs=None) -> dict[str, int]:
    """{규칙 ID: 그 규칙을 비교 단계에서 지나간 사례 파일 수}. 규칙표의 모든 ID가 들어간다.

    rows·runs를 주면 그 사례만 센다(테스트용). 안 주면 confirmed 사례 전부.
    """
    rules = load_rules(2025)
    compared: dict[str, set[str]] = {}
    for row in all_rows() if rows is None else rows:
        if row.kind == "compare":
            compared.setdefault(row.case, set()).add(row.stage)
    hits: dict[str, set[str]] = {rule_id: set() for rule_id in rules}
    for _, run in all_runs() if runs is None else runs:
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
