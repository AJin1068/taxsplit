from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from taxsplit.core.config import Settings, get_settings
from taxsplit.db.engine import make_engine
from taxsplit.db.repositories import SqlConversationRepository, SqlLlmCallRepository
from taxsplit.llm.call_log import InMemoryLlmCallRepository, LlmCallRepository
from taxsplit.llm.factory import build_llm_client
from taxsplit.llm.recording import RecordingLLMClient
from taxsplit.repositories.base import ConversationRepository
from taxsplit.repositories.memory import InMemoryConversationRepository
from taxsplit.services.conversation_service import ConversationService


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


SettingsDep = Annotated[Settings, Depends(get_settings)]
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
LLMClientDep = Annotated[RecordingLLMClient, Depends(get_llm_client)]
