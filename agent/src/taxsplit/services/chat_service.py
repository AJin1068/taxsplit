"""채팅 서비스: 대화 만들기(추출 결과 검사), 메시지 목록, 메시지 보내기(턴 실행 + 저장).

FastAPI와 저장소 구현체를 import하지 않는다(ConversationService와 같은 규칙).
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from taxsplit.agent.events import Event
from taxsplit.agent.loop import AgentTurn, EvidenceFinder
from taxsplit.agent.state import build_state
from taxsplit.domain.models import (
    Conversation,
    ConversationNotFound,
    InvalidDocuments,
    Message,
)
from taxsplit.extract.validate import check_doc
from taxsplit.gaps.models import CardAnswer
from taxsplit.llm.base import LLMClient
from taxsplit.repositories.base import (
    AsyncToolCallRepository,
    ConversationRepository,
    MessageRepository,
)
from taxsplit.rules.loader import Rule
from taxsplit.tools.policy import ToolPolicy

logger = logging.getLogger("taxsplit.chat")

# 대화 하나에 받는 추출 결과 수(남편·아내 PDF 각 1부)
MAX_DOCUMENTS = 2


def check_documents(documents: list[Any]) -> list[dict[str, Any]]:
    """추출 결과 목록 검사(PR 12 JSON 업로드 검사 그대로). 실패하면 InvalidDocuments."""
    if len(documents) > MAX_DOCUMENTS:
        raise InvalidDocuments([f"documents: 최대 {MAX_DOCUMENTS}개까지 받습니다"])
    checked, errors = [], []
    for i, raw in enumerate(documents):
        doc, reasons = check_doc(raw)
        # 칸 경로 앞에 몇 번째 자료인지 붙인다: documents[0].items[2].amount
        errors += [_with_index(i, r) for r in reasons]
        if doc is not None:
            checked.append(doc.model_dump(mode="json"))
    if errors:
        raise InvalidDocuments(errors)
    return checked


def _with_index(i: int, reason: str) -> str:
    whole = "(전체)"
    if reason.startswith(whole):
        return f"documents[{i}]{reason[len(whole) :]}"
    return f"documents[{i}].{reason}"


class ChatService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        tool_calls: AsyncToolCallRepository,
        llm: LLMClient,
        rules: dict[str, Rule],
        find_evidence: EvidenceFinder,
        max_llm_calls: int = 10,
        policy: ToolPolicy | None = None,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._tool_calls = tool_calls
        self._llm = llm
        self._rules = rules
        self._find_evidence = find_evidence
        self._max_llm_calls = max_llm_calls
        # 도구 호출 운영값. 비우면 PR 9 정책 그대로
        self._policy = policy or ToolPolicy()

    async def create(self, title: str, documents: list[Any] | None = None) -> Conversation:
        docs = check_documents(documents or [])
        conversation = Conversation(
            title=title, created_at=datetime.now(UTC), documents=docs or None
        )
        return await self._conversations.save(conversation)

    async def _get(self, conversation_id: int) -> Conversation:
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFound(conversation_id)
        return conversation

    async def list_messages(self, conversation_id: int) -> list[Message]:
        await self._get(conversation_id)
        return await self._messages.list_for(conversation_id)

    async def start_turn(
        self, conversation_id: int, content: str, answer: CardAnswer | None = None
    ) -> AsyncIterator[Event]:
        """대화가 없으면 여기서 바로 ConversationNotFound(스트리밍 시작 전 404).

        질문 카드 답(answer)이 있으면 사용자 글 끝에 한 줄로 붙여 저장한다(대화 기록에 남게).
        가정: docs/assumptions.md A-067
        """
        conversation = await self._get(conversation_id)
        if answer is not None:
            content = f"{content}\n{answer.as_text()}"
        return self._run_turn(conversation, content)

    async def _run_turn(self, conversation: Conversation, content: str) -> AsyncIterator[Event]:
        assert conversation.id is not None
        cid = conversation.id
        # 턴 시작: 저장소에서 대화 상태를 다시 만든다(서버 메모리에 두지 않음)
        history = await self._messages.list_for(cid)
        records = await self._tool_calls.list_for(cid)
        state = build_state(conversation, history, records)
        seq = len(history) + 1
        await self._messages.add(_message(cid, seq, "user", content))

        turn = AgentTurn(
            self._llm,
            self._rules,
            self._find_evidence,
            state,
            content,
            max_llm_calls=self._max_llm_calls,
            policy=self._policy,
        )
        out = turn.outcome
        try:
            async for event in turn.run():
                yield event
        finally:
            # 멈춤·오류·연결 끊김이어도 도구 호출 기록은 남긴다. 저장 실패가 답을 막지는 않는다
            try:
                await self._tool_calls.add_many(out.records)
            except Exception:
                logger.exception("도구 호출 기록 저장 실패 (대화 %s, 턴 %s)", cid, state.turn)

        message_id = None
        if out.text is not None:
            saved = await self._messages.add(_message(cid, seq + 1, "assistant", out.text))
            message_id = saved.id
        yield Event(
            "done",
            {
                "message_id": message_id,
                "turn": state.turn,
                "ended": out.ended,
                "tool_calls": [
                    {"tool": r.tool, "status": r.status.value, "errors": r.errors}
                    for r in out.records
                ],
                "usage": {
                    "input_tokens": out.input_tokens,
                    "output_tokens": out.output_tokens,
                    "cost_usd": None if out.cost_usd is None else float(out.cost_usd),
                },
            },
        )


def _message(cid: int, seq: int, role: str, content: str) -> Message:
    return Message(
        conversation_id=cid, seq=seq, role=role, content=content, created_at=datetime.now(UTC)
    )  # type: ignore[arg-type]
