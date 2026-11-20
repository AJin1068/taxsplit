"""메인 에이전트 시스템 프롬프트와 도구 정의(LLM 요청 모양)."""

import json
from functools import cache
from pathlib import Path

from taxsplit.agent.state import ConversationState
from taxsplit.llm.base import ToolSpec
from taxsplit.tools.definitions import tool_definitions

PROMPT_PATH = Path(__file__).parent / "prompts" / "main.md"


@cache
def base_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def system_prompt(state: ConversationState) -> str:
    """기본 프롬프트 + 올린 자료 + 지금까지 확인한 가구 정보.

    지난 턴의 도구 호출·결과는 다시 보내지 않는다. 대신 가장 최근 성공한 도구 인자를 붙인다.
    지난 결과가 필요하면 AI가 같은 인자로 다시 부른다(같은 입력이면 같은 결과).
    """
    parts = [base_prompt()]
    if state.documents:
        # TODO(사람 확인): docs/assumptions.md A-032
        docs = json.dumps(state.documents, ensure_ascii=False)
        parts.append(f"## 사용자가 올린 간소화 자료(추출 결과)\n\n{docs}")
    if state.last_args is not None:
        args = json.dumps(state.last_args, ensure_ascii=False)
        parts.append(f"## 지금까지 확인한 가구 정보\n\n{args}")
    return "\n\n".join(parts)


@cache
def tool_specs() -> tuple[ToolSpec, ...]:
    return tuple(
        ToolSpec(name=d.name, description=d.description, input_schema=d.input_schema)
        for d in tool_definitions()
    )
