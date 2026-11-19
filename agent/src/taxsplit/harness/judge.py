"""GPT 채점(CallKind.JUDGE, --judge일 때만): 코드로 못 재는 한 가지만 묻는다.

질문은 eval/scoring/rules.md "GPT 채점" 그대로다. 결과는 참고 숫자(설명 일치율)로만 쓴다.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from taxsplit.llm.base import CallKind, LLMClient, LLMError, LLMRequest, Message
from taxsplit.llm.pricing import cost_usd

QUESTION = "최종 답의 설명이 배분 비교 결과(누가 누구를 공제받는지, 흔한 방식 대비 차이)와 맞는가?"
SYSTEM = (
    "너는 연말정산 상담 AI의 답을 채점한다. 아래 질문 하나에만 답한다.\n"
    f"질문: {QUESTION}\n"
    "배분 비교 결과(JSON)가 정답이다. 금액·사람·쪽(husband=남편, wife=아내)이 다르면 틀림이다.\n"
    'JSON 객체 하나로만 답한다: {"consistent": true 또는 false, "reason": "한국어 한두 문장"}'
)


@dataclass(frozen=True)
class Verdict:
    consistent: bool | None
    reason: str
    cost_usd: Decimal | None


async def judge(llm: LLMClient, answer: str, allocation: dict[str, Any]) -> Verdict:
    """에이전트의 최종 설명과 배분 비교 결과를 비교한다. 실패하면 consistent=None."""
    body = (
        f"## 배분 비교 결과\n\n{json.dumps(allocation, ensure_ascii=False)}\n\n"
        f"## 상담 AI의 최종 답\n\n{answer}"
    )
    request = LLMRequest(
        kind=CallKind.JUDGE, messages=[Message("user", body)], system=SYSTEM, max_tokens=512
    )
    try:
        resp = await llm.complete(request)
    except LLMError as e:
        return Verdict(None, f"채점 호출 실패: {e}", None)
    cost = cost_usd(getattr(llm, "provider", "fake"), resp.model, resp.usage)
    try:
        data = json.loads(resp.text)
        consistent = data["consistent"]
        if not isinstance(consistent, bool):
            raise TypeError
        return Verdict(consistent, str(data.get("reason", "")), cost)
    except json.JSONDecodeError, KeyError, TypeError:
        return Verdict(None, f"채점 답 형식이 틀림: {resp.text[:200]}", cost)
