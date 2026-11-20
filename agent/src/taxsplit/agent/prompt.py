"""메인 에이전트 시스템 프롬프트와 도구 정의(LLM 요청 모양)."""

import json
from functools import cache
from pathlib import Path

from taxsplit.agent.state import ConversationState
from taxsplit.llm.base import ToolSpec
from taxsplit.tools.definitions import tool_definitions

PROMPT_PATH = Path(__file__).parent / "prompts" / "main.md"
SETUP_PATH = Path(__file__).parent / "prompts" / "setup.md"
SIDE_WORDS = {"husband": "남편", "wife": "아내"}


@cache
def base_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@cache
def _setup_templates() -> dict[str, str]:
    """setup.md를 '## 이름' 단위로 나눈 글 조각(호칭·자녀 수)."""
    parts: dict[str, str] = {}
    for block in SETUP_PATH.read_text(encoding="utf-8").split("\n## ")[1:]:
        name, _, body = block.partition("\n")
        parts[name.strip()] = body.strip()
    return parts


def setup_prompt(state: ConversationState) -> str | None:
    """첫 화면 설정(FR-09·FR-10)을 프롬프트 조각으로. 아무것도 안 골랐으면 None(지금처럼)."""
    lines = []
    if state.self_role in SIDE_WORDS:
        me = SIDE_WORDS[state.self_role]
        other = SIDE_WORDS["wife" if state.self_role == "husband" else "husband"]
        lines.append(_setup_templates()["호칭"].format(me=me, other=other))
    if state.child_count is not None:
        lines.append(_setup_templates()["자녀 수"].format(count=state.child_count))
    if not lines:
        return None
    return "## 사용자가 첫 화면에서 고른 것\n\n" + "\n".join(lines)


def system_prompt(state: ConversationState) -> str:
    """기본 프롬프트 + 올린 자료 + 지금까지 확인한 가구 정보.

    지난 턴의 도구 호출·결과는 다시 보내지 않는다. 대신 가장 최근 성공한 도구 인자를 붙인다.
    지난 결과가 필요하면 AI가 같은 인자로 다시 부른다(같은 입력이면 같은 결과).
    """
    parts = [base_prompt()]
    setup = setup_prompt(state)
    if setup is not None:
        parts.append(setup)
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
