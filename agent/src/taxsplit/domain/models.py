from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from taxsplit.allocation.models import Household

# FR-09 첫 화면 "저는 남편/아내"
type SelfRole = Literal["husband", "wife"]
type MessageRole = Literal["user", "assistant"]
# 가구 데이터를 어디서 받았나
type HouseholdSource = Literal["json", "pdf", "chat"]


@dataclass
class Conversation:
    title: str
    created_at: datetime
    # 저장 전에는 None, 저장소가 save할 때 채움 (JPA의 @GeneratedValue와 같은 아이디어)
    id: int | None = None
    household_id: int | None = None
    self_role: SelfRole | None = None


@dataclass
class Message:
    """대화 메시지 한 줄. seq는 대화 안 순번(같은 대화에서 겹치면 저장 실패)."""

    conversation_id: int
    seq: int
    role: MessageRole
    content: str
    created_at: datetime
    id: int | None = None


@dataclass
class StoredHousehold:
    """저장된 가구. data는 배분 비교 입력 그대로다."""

    tax_year: int
    data: Household
    source: HouseholdSource
    created_at: datetime
    updated_at: datetime
    id: int | None = None


class ConversationNotFound(Exception):
    def __init__(self, conversation_id: int) -> None:
        super().__init__(f"conversation {conversation_id} not found")
        self.conversation_id = conversation_id
