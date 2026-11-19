from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from taxsplit.core.config import Settings, get_settings
from taxsplit.db.engine import make_engine
from taxsplit.db.repositories import (
    SqlConversationRepository,
    SqlLlmCallRepository,
    SqlMessageRepository,
)
from taxsplit.db.tool_call_repository import SqlToolCallRepository
from taxsplit.llm.call_log import InMemoryLlmCallRepository, LlmCallRepository
from taxsplit.llm.factory import build_llm_client
from taxsplit.llm.recording import RecordingLLMClient
from taxsplit.repositories.base import (
    AsyncToolCallRepository,
    ConversationRepository,
    MessageRepository,
)
from taxsplit.repositories.memory import (
    InMemoryAsyncToolCallRepository,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from taxsplit.rules.loader import Rule, load_rules
from taxsplit.services.chat_service import ChatService
from taxsplit.services.conversation_service import ConversationService
from taxsplit.services.evidence_service import (
    TAX_YEAR,
    EvidenceService,
    default_method,
    embedder_for,
)


@lru_cache
def get_engine() -> AsyncEngine:
    # 앱 전체에 하나. 만들 때는 DB에 붙지 않고 첫 쿼리 때 붙는다
    return make_engine(get_settings().database_url)


@lru_cache
def get_conversation_repo() -> ConversationRepository:
    # 앱 전체에 하나 (싱글톤). 설정값 storage로 메모리/Postgres 구현을 고른다
    if get_settings().storage == "postgres":
        return SqlConversationRepository(get_engine())
    return InMemoryConversationRepository()


def get_conversation_service(
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationService:
    # 요청마다 새로 만듦. 가벼운 객체라 비용이 거의 없음
    return ConversationService(repo)


@lru_cache
def get_llm_call_repo() -> LlmCallRepository:
    if get_settings().storage == "postgres":
        return SqlLlmCallRepository(get_engine())
    return InMemoryLlmCallRepository()


@lru_cache
def get_llm_client() -> RecordingLLMClient:
    return build_llm_client(get_settings(), get_llm_call_repo())


@lru_cache
def get_message_repo() -> MessageRepository:
    if get_settings().storage == "postgres":
        return SqlMessageRepository(get_engine())
    return InMemoryMessageRepository()


@lru_cache
def get_tool_call_repo() -> AsyncToolCallRepository:
    if get_settings().storage == "postgres":
        return SqlToolCallRepository(get_engine())
    return InMemoryAsyncToolCallRepository()


@lru_cache
def get_rules() -> dict[str, Rule]:
    return load_rules(TAX_YEAR)


@lru_cache
def get_evidence_service() -> EvidenceService:
    # 원문 조각은 처음 근거를 찾을 때 올린다. 모델(hybrid·vector)도 그때 불러온다
    settings = get_settings()
    method = default_method(settings.rag_method)
    embedder = embedder_for(method, settings.rag_embedding_model)
    return EvidenceService(get_rules(), method, embedder=embedder)


def get_chat_service(
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    messages: Annotated[MessageRepository, Depends(get_message_repo)],
    tool_calls: Annotated[AsyncToolCallRepository, Depends(get_tool_call_repo)],
    llm: Annotated[RecordingLLMClient, Depends(get_llm_client)],
    evidence: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> ChatService:
    return ChatService(
        conversations,
        messages,
        tool_calls,
        llm,
        get_rules(),
        evidence,
        max_llm_calls=get_settings().agent_max_llm_calls_per_turn,
    )


SettingsDep = Annotated[Settings, Depends(get_settings)]
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
LLMClientDep = Annotated[RecordingLLMClient, Depends(get_llm_client)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
