"""에이전트 루프: 사용자 메시지 하나(= 턴 하나)를 처리한다.

AI 호출 → 도구 호출이 있으면 검사기로 검사·실행 → 결과를 AI에게 돌려줌 → … → AI가 글로 답하면
센서 3개로 검사 → 통과하면 조각으로 나눠 보낸다. 받는 대로 흘려보내지 않는 이유: 센서가 막기 전에
틀린 금액이 화면에 나가면 안 된다(FR-06). TODO(사람 확인): docs/assumptions.md A-033
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from taxsplit.agent.events import (
    GUARD_STOP_TEXT,
    SENSOR_STOP_TEXT,
    Ended,
    Event,
    text_chunks,
)
from taxsplit.agent.prompt import system_prompt, tool_specs
from taxsplit.agent.sensors import check_answer, feedback
from taxsplit.agent.state import ConversationState, members_of
from taxsplit.llm.base import (
    CallKind,
    LLMClient,
    LLMError,
    LLMRequest,
    Message,
    TextBlock,
    ToolResultBlock,
    Usage,
)
from taxsplit.llm.pricing import cost_usd
from taxsplit.rules.loader import Rule
from taxsplit.tools.definitions import COMPARE_ALLOCATIONS, FIND_MISSING_DEDUCTIONS
from taxsplit.tools.guard import ToolCallGuard
from taxsplit.tools.policy import ToolPolicy
from taxsplit.tools.records import InMemoryToolCallRepository, ToolCallRecord
from taxsplit.tools.status import ToolStatus

# 규칙 ID 목록 → {규칙 ID: [근거 dict, ...]}. 실패하면 빈 dict를 돌려줘야 한다
type EvidenceFinder = Callable[[list[str]], Awaitable[dict[str, list[dict[str, Any]]]]]

# 센서에 떨어진 답을 다시 쓰게 하는 횟수(운영값). 넘으면 정해진 문구로 끝낸다
MAX_REWRITES = 1


@dataclass
class TurnOutcome:
    """턴이 끝난 뒤 서비스가 저장·done 이벤트에 쓰는 값."""

    ended: Ended = "answered"
    text: str | None = None
    records: list[ToolCallRecord] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal | None = None

    def add_usage(self, provider: str, model: str, usage: Usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        cost = cost_usd(provider, model, usage)
        if cost is not None:
            self.cost_usd = (self.cost_usd or Decimal(0)) + cost


def _history(messages: list[Any], user_text: str) -> list[Message]:
    """저장된 글 기록 + 이번 사용자 글. 같은 역할이 이어지면(지난 턴 오류) 한 줄로 합친다."""
    out: list[Message] = []
    for role, content in [*((m.role, m.content) for m in messages), ("user", user_text)]:
        if out and out[-1].role == role:
            out[-1] = Message(role, f"{out[-1].content}\n\n{content}")
        else:
            out.append(Message(role, content))
    return out


class AgentTurn:
    def __init__(
        self,
        llm: LLMClient,
        rules: dict[str, Rule],
        find_evidence: EvidenceFinder,
        state: ConversationState,
        user_text: str,
        *,
        max_llm_calls: int = 10,
        policy: ToolPolicy | None = None,
    ) -> None:
        self._llm = llm
        self._find_evidence = find_evidence
        self._state = state
        self._user_text = user_text
        self._max_calls = max_llm_calls
        # 검사기 기록은 턴 동안 여기 모았다가, 턴이 끝나면 서비스가 한꺼번에 저장한다
        self._buffer = InMemoryToolCallRepository()
        self._guard = ToolCallGuard(
            rules,
            self._buffer,
            policy,
            state.conversation_id,
            turn=state.turn,
            checked=state.checked,
            documents=state.documents,
        )
        self.outcome = TurnOutcome()
        # 이번 턴에 성공한 배분 비교(마지막 것)
        self._compare: dict[str, Any] | None = None
        # 이번 턴에 성공한 빈 곳 찾기(마지막 것). 카드는 gaps 이벤트로 화면에 보낸다
        self._gaps: dict[str, Any] | None = None

    def _request(self, messages: list[Message]) -> LLMRequest:
        return LLMRequest(
            kind=CallKind.MAIN_AGENT,
            messages=list(messages),
            system=system_prompt(self._state),
            tools=tool_specs(),
            conversation_id=self._state.conversation_id,
        )

    async def run(self) -> AsyncIterator[Event]:
        """이벤트를 차례로 낸다(done은 서비스가 저장 뒤에 보낸다)."""
        self._state.add_user_text(self._user_text)
        messages = _history(self._state.history, self._user_text)
        provider = getattr(self._llm, "provider", "fake")
        calls = rewrites = 0
        model = ""  # 실패한 호출의 비용을 셀 때 쓸 마지막 모델 이름
        out = self.outcome
        yield Event("status", {"stage": "thinking"})
        try:
            while True:
                if calls >= self._max_calls:
                    out.ended, out.text = "guard_stop", GUARD_STOP_TEXT
                    break
                calls += 1
                try:
                    resp = await self._llm.complete(self._request(messages))
                except LLMError as e:
                    out.add_usage(provider, model, e.usage)
                    out.ended = "error"
                    yield Event("error", {"message": f"AI 호출 실패: {e}"})
                    return
                model = resp.model
                out.add_usage(provider, model, resp.usage)

                if resp.tool_uses:
                    blocks = (*([TextBlock(resp.text)] if resp.text else []), *resp.tool_uses)
                    messages.append(Message("assistant", tuple(blocks)))
                    results, stop = [], False
                    for use in resp.tool_uses:
                        g = self._guard.call(use.name, use.input)
                        self._state.absorb(g.record)
                        if g.status == ToolStatus.OK and use.name == COMPARE_ALLOCATIONS:
                            self._compare = g.result
                        if g.status == ToolStatus.OK and use.name == FIND_MISSING_DEDUCTIONS:
                            self._gaps = g.result
                        yield Event(
                            "status", {"stage": "tool", "tool": use.name, "status": g.status.value}
                        )
                        is_err = g.status != ToolStatus.OK
                        results.append(ToolResultBlock(use.id, g.message, is_error=is_err))
                        if g.stop:
                            stop = True
                            break
                    if stop:
                        out.ended, out.text = "guard_stop", GUARD_STOP_TEXT
                        break
                    messages.append(Message("user", tuple(results)))
                    continue

                failures = check_answer(resp.text, self._state.sensor)
                if not failures:
                    out.ended, out.text = "answered", resp.text
                    break
                if rewrites >= MAX_REWRITES:
                    out.ended, out.text = "sensor_stop", SENSOR_STOP_TEXT
                    break
                rewrites += 1
                messages.append(Message("assistant", resp.text or "(빈 답)"))
                messages.append(Message("user", feedback(failures)))
        finally:
            out.records = self._buffer.list()

        for chunk in text_chunks(out.text or ""):
            yield Event("delta", {"text": chunk})
        # 빈 곳 카드·배분 결과·근거는 센서를 통과한 정상 답일 때만 보낸다
        # TODO(사람 확인): docs/assumptions.md A-034
        if out.ended == "answered" and self._gaps is not None:
            yield Event("gaps", {"cards": self._gaps["cards"]})
        if out.ended == "answered" and self._compare is not None:
            async for event in self._allocation_events():
                yield event

    async def _allocation_events(self) -> AsyncIterator[Event]:
        compare = self._compare
        household = self._state.last_compare_household
        assert compare is not None and household is not None
        # 금액은 도구 결과 그대로. 새로 만들거나 바꾸지 않는다(ADR-0003)
        yield Event("allocation", {**compare, "members": members_of(household)})
        yield Event("evidence", await self._find_evidence(list(compare.get("rule_ids", []))))
