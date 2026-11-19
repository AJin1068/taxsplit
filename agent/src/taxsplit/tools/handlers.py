"""도구 실행. 검사를 통과한 가구를 배분 코드에 그대로 넘기고 결과를 dict로 돌려준다.

금액은 엔진이 낸 정수 그대로 담는다. 여기서 금액을 더하거나 반올림하지 않는다(ADR-0003).
"""

from collections.abc import Callable
from typing import Any

from taxsplit.allocation.candidates import STAGE, candidates
from taxsplit.allocation.compare import compare_allocations
from taxsplit.allocation.models import Household
from taxsplit.engine import Rulebook, basic_eligibility
from taxsplit.rules.loader import Rule
from taxsplit.tools.definitions import CHECK_ELIGIBILITY, COMPARE_ALLOCATIONS

Handler = Callable[[Household, dict[str, Rule]], dict[str, Any]]


def run_check_eligibility(household: Household, rules: dict[str, Rule]) -> dict[str, Any]:
    """부양가족마다 기본공제 받을 수 있는 쪽과 판정 이유. 판정은 배분 비교의 후보 함수 그대로."""
    book = Rulebook(rules)
    cands = candidates(household, book)
    rows = []
    for m in household.members:
        # 이유 글은 계산기의 요건 판정 결과를 그대로 옮긴다(새 세법 문구를 만들지 않음)
        _, reason = basic_eligibility(m.dependent, book, STAGE)
        rows.append(
            {
                "name": m.name,
                "relation": m.dependent.relation,
                "eligible": bool(cands[m.name]),
                "claimable_by": list(cands[m.name]),
                "reason": reason or "요건 미충족",
            }
        )
    ids = sorted({i for stage in book.rules_used().values() for i in stage})
    return {"dependents": rows, "rule_ids": ids}


def run_compare_allocations(household: Household, rules: dict[str, Rule]) -> dict[str, Any]:
    """최적안·흔한 방식 A·B·추가 환급액·경고·쓴 규칙 ID. 모든 안의 목록은 수만 돌려준다."""
    r = compare_allocations(household, rules)
    shown = (r.best, *(c.plan for c in r.common))
    return {
        "plan_count": r.plan_count,
        "best": r.best.model_dump(mode="json"),
        "best_assignments": [p.assignment for p in r.best_plans],
        "common": [c.model_dump(mode="json") for c in r.common],
        "headline_saving": r.headline_saving,
        "larger_earner": r.larger_earner,
        "equal_gross": r.equal_gross,
        "warnings": [w.model_dump(mode="json") for w in r.warnings],
        "rule_ids": sorted({i for p in shown for i in p.rule_ids}),
    }


HANDLERS: dict[str, Handler] = {
    CHECK_ELIGIBILITY: run_check_eligibility,
    COMPARE_ALLOCATIONS: run_compare_allocations,
}
