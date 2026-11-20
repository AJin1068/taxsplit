"""find_missing_deductions 실행: 빈 곳 찾기 + (고른 칸이 있으면) 놓칠 금액.

간소화 추출 결과는 AI 인자가 아니라 대화에 저장된 자료를 서버가 넣는다(AI가 옮겨 적다 틀리지 않게).
금액은 계산 엔진(배분 비교 두 번)이 낸 정수 그대로 담는다(ADR-0003).
"""

from collections.abc import Sequence
from typing import Any

from taxsplit.gaps.detect import find_gaps
from taxsplit.gaps.estimate import estimate_missing
from taxsplit.gaps.models import GapCard, GapRequest
from taxsplit.rules.loader import Rule

# 한 번에 사용자에게 묻는 카드 수(운영값). 결과에는 전부 담고, 앞에서부터 이만큼 물으라고 알린다
ASK_AT_ONCE = 3
_CONSENT_IDS = ("gap.adult_no_consent", "gap.child_turned_adult")


def run_find_missing(
    req: GapRequest, rules: dict[str, Rule], documents: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    cards = find_gaps(req.family, documents, household=req.household, rules=rules)
    estimates = {}
    for p in req.picks:
        assert req.household is not None  # 인자 검사가 막는다
        estimates[p.person] = estimate_missing(req.household, p.person, p.amount, rules, p.payer)
    out: list[GapCard] = []
    for c in cards:
        if c.id in _CONSENT_IDS and c.person in estimates:
            c = c.model_copy(update={"estimate": estimates.pop(c.person)})
        out.append(c)
    return {
        "cards": [c.model_dump(mode="json") for c in out],
        # 동의 카드가 없는 가족(예: 이미 자료가 있음)에 대한 계산도 버리지 않고 돌려준다
        "estimates": {k: v.model_dump(mode="json") for k, v in estimates.items()},
        "ask_at_once": ASK_AT_ONCE,
    }
