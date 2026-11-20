"""평가 하네스 테스트용 가짜: 돈이 들지 않게 메인 에이전트·가상 사용자·채점을 모두 대신한다."""

import argparse
from dataclasses import replace
from typing import Any

import httpx2

from taxsplit.api.deps import get_chat_service
from taxsplit.harness.run import HarnessDeps
from taxsplit.harness.scoring import DEFAULT_SCENARIOS
from taxsplit.llm.base import LLMError, LLMRequest, LLMResponse, ToolUseBlock
from taxsplit.llm.fake import ScriptedLLMClient
from taxsplit.main import create_app
from taxsplit.repositories.memory import (
    InMemoryAsyncToolCallRepository,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from taxsplit.rules.loader import load_rules
from taxsplit.services.chat_service import ChatService
from taxsplit.services.evidence_service import EvidenceService

RULES = load_rules(2025)
EVIDENCE = EvidenceService(RULES, "keyword")
QUESTION = "가족 이름과 출생연도, 올해 소득을 알려 주실래요?"
ANSWER = "배분 비교를 마쳤어요. 화면의 결과를 확인해 주세요."


class Priced(ScriptedLLMClient):
    """단가표에 있는 모델 이름으로 답하는 차례 지정 가짜(비용 계산을 시험하려고)."""

    provider = "anthropic"

    def _next(self, request: LLMRequest) -> LLMResponse:
        return super()._next(replace(request, model="claude-haiku-5-5"))


def tool_input(household: dict[str, Any]) -> dict[str, Any]:
    """시나리오 가구는 기본값 칸(소득 0)을 뺀다. 도구는 소득을 꼭 받으므로 0을 채운다."""
    members = [
        {**m, "dependent": {"income_amount": 0, **m["dependent"]}}
        for m in household.get("members", [])
    ]
    return {**household, "members": members}


def main_steps(household: dict[str, Any]) -> list:
    """대화 하나: 질문 → (다음 턴) 요건 확인 → 배분 비교 → 답."""
    household = tool_input(household)
    return [
        QUESTION,
        ToolUseBlock(id="c", name="check_eligibility", input=household),
        ToolUseBlock(id="a", name="compare_allocations", input=household),
        ANSWER,
    ]


def sim_reply(message: str, revealed: list[str], done: bool) -> ToolUseBlock:
    return ToolUseBlock(
        id="r", name="reply", input={"message": message, "revealed": revealed, "done": done}
    )


def sim_steps(scenario: dict[str, Any], reveal: bool = True) -> list:
    must = [f["id"] for f in scenario["facts"] if f["kind"] == "must_ask"] if reveal else []
    return [sim_reply("말씀드릴게요", must, False), sim_reply("고마워요", [], True)]


def make_client(main: ScriptedLLMClient, max_llm_calls: int = 10) -> httpx2.AsyncClient:
    """앱을 같은 프로세스에 띄우고 메인 에이전트만 가짜로 바꾼 HTTP 클라이언트."""
    app = create_app()
    service = ChatService(
        InMemoryConversationRepository(),
        InMemoryMessageRepository(),
        InMemoryAsyncToolCallRepository(),
        main,
        RULES,
        EVIDENCE,
        max_llm_calls=max_llm_calls,
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test")


def deps_for(main: list, sim: list, judge: list | None = None, **kw) -> HarnessDeps:
    return HarnessDeps(
        client=make_client(Priced(main), **kw),
        sim_llm=Priced(sim),
        judge_llm=Priced(judge) if judge is not None else None,
        models={"main_agent": "fake", "sim_user": "fake", "judge": None},
    )


def factory(deps: HarnessDeps):
    def build(args: argparse.Namespace) -> HarnessDeps:
        return deps

    return build


__all__ = ["DEFAULT_SCENARIOS", "LLMError"]
