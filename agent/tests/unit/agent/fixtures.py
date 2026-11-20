"""에이전트 테스트용 가상 가구(손으로 만든 값, eval/ 사례와 무관)와 가짜 LLM 준비물."""

import asyncio
from typing import Any

from taxsplit.llm.base import ToolUseBlock

HOUSEHOLD: dict[str, Any] = {
    "husband": {"gross_salary": 62_000_000, "sex": "male", "birth_year": 1984},
    "wife": {"gross_salary": 38_000_000, "sex": "female", "birth_year": 1986},
    "members": [
        {
            "dependent": {
                "name": "하늘",
                "relation": "child",
                "birth_year": 2016,
                "income_amount": 0,
            }
        },
        {
            "dependent": {
                "name": "봄",
                "relation": "lineal_ascendant",
                "birth_year": 1954,
                "income_amount": 0,
            },
            "family_of": "husband",
        },
    ],
    "medical": [{"payer": "wife", "for_whom": "봄", "amount": 4_200_000}],
}


def use(tool: str, args: Any = None, id_: str = "t1") -> ToolUseBlock:
    return ToolUseBlock(id=id_, name=tool, input=HOUSEHOLD if args is None else args)


def run(coro):
    return asyncio.run(coro)


async def no_evidence(rule_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    return {rid: [] for rid in rule_ids}


def make_service(steps, *, max_llm_calls: int = 10, repos=None, policy=None):
    """가짜 LLM 대본으로 도는 ChatService와 메모리 저장소 묶음."""
    from taxsplit.llm.fake import ScriptedLLMClient
    from taxsplit.repositories.memory import (
        InMemoryAsyncToolCallRepository,
        InMemoryConversationRepository,
        InMemoryMessageRepository,
    )
    from taxsplit.rules.loader import load_rules
    from taxsplit.services.chat_service import ChatService

    if repos is None:
        repos = (
            InMemoryConversationRepository(),
            InMemoryMessageRepository(),
            InMemoryAsyncToolCallRepository(),
        )
    llm = ScriptedLLMClient(list(steps))
    service = ChatService(
        *repos, llm, load_rules(2025), no_evidence, max_llm_calls=max_llm_calls, policy=policy
    )
    return service, llm, repos


async def collect(service, conversation_id: int, text: str):
    events = await service.start_turn(conversation_id, text)
    return [e async for e in events]
