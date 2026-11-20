"""가상 사용자(CallKind.SIM_USER): 시나리오의 persona·facts만 알고 에이전트 질문에 답한다.

답마다 구조화 출력(reply 도구 강제)으로 "보낼 말, 이번에 알려 준 사실 id, 끝났나"를 받는다.
기준 정답(gold)과 사실의 종류(must_ask 등)는 받지 않는다.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from taxsplit.llm.base import CallKind, LLMClient, LLMError, LLMRequest, Message, ToolSpec
from taxsplit.llm.pricing import cost_usd

PROMPT_PATH = Path(__file__).parent / "prompts" / "sim_user.md"
REPLY_TOOL = ToolSpec(
    name="reply",
    description="상담 AI에게 보낼 답",
    input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "상담 AI에게 보낼 말"},
            "revealed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "이번 답에 담은 사실 id",
            },
            "done": {"type": "boolean", "description": "배분안을 받았고 더 물을 것이 없나"},
        },
        "required": ["message", "revealed", "done"],
    },
)
SPEAKER = {"user": "나", "assistant": "상담 AI"}


@dataclass(frozen=True)
class SimReply:
    message: str
    revealed: list[str]
    done: bool
    cost_usd: Decimal | None


@cache
def _template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def system_prompt(scenario: dict[str, Any]) -> str:
    spouses = scenario.get("spouse_names") or {}
    names = (
        f"남편 {spouses.get('husband', '(이름 없음)')}, 아내 {spouses.get('wife', '(이름 없음)')}"
    )
    facts = "\n".join(f"- {f['id']}: {f['text']}" for f in scenario["facts"])
    return _template().format(persona=scenario["persona"], spouses=names, facts=facts)


def _transcript_text(transcript: list[dict[str, str]]) -> str:
    lines = [f"[{SPEAKER[t['role']]}] {t['text']}" for t in transcript]
    return "지금까지 대화:\n\n" + "\n\n".join(lines) + "\n\n상담 AI의 마지막 말에 답하세요."


def _parse(resp_input: Any, text: str) -> dict[str, Any]:
    data = resp_input
    if data is None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
    ok = (
        isinstance(data, dict)
        and isinstance(data.get("message"), str)
        and isinstance(data.get("revealed"), list)
        and isinstance(data.get("done"), bool)
    )
    if not ok:
        raise LLMError("가상 사용자 답 형식이 틀렸습니다(message·revealed·done)")
    return data


class SimUser:
    def __init__(self, llm: LLMClient, scenario: dict[str, Any]) -> None:
        self._llm = llm
        self._system = system_prompt(scenario)
        self._fact_ids = {f["id"] for f in scenario["facts"]}

    async def reply(self, transcript: list[dict[str, str]]) -> SimReply:
        """대화 기록(user=가상 사용자, assistant=에이전트)을 보고 다음 말을 낸다. 실패: LLMError."""
        # 역할을 뒤집지 않고 대화 전체를 글 하나로 넘긴다(첫 메시지는 늘 user여야 함)
        request = LLMRequest(
            kind=CallKind.SIM_USER,
            messages=[Message("user", _transcript_text(transcript))],
            system=self._system,
            tools=(REPLY_TOOL,),
            tool_choice=REPLY_TOOL.name,
        )
        resp = await self._llm.complete(request)
        provider = getattr(self._llm, "provider", "fake")
        cost = cost_usd(provider, resp.model, resp.usage)
        use = next((u for u in resp.tool_uses if u.name == REPLY_TOOL.name), None)
        data = _parse(use.input if use else None, resp.text)
        # 시나리오에 없는 사실 id는 버린다(가상 사용자가 지어낸 id를 세지 않게)
        revealed = [i for i in data["revealed"] if i in self._fact_ids]
        return SimReply(data["message"], revealed, data["done"], cost)
