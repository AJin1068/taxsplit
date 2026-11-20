from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

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
    # 대화를 만들 때 받은 간소화 PDF 추출 결과(ExtractedDoc을 JSON으로 바꾼 것, 0~2개)
    documents: list[dict[str, Any]] | None = None
    # FR-10 첫 화면에서 고른 공제 대상 자녀 수(0~5). 고르지 않으면 None
    child_count: int | None = None


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


class InvalidDocuments(Exception):
    """대화 만들 때 받은 추출 결과가 검사에 떨어짐. errors는 '칸 경로: 이유' 한국어 줄."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class InvalidUpload(InvalidDocuments):
    """올린 파일 자체가 잘못됨(빈 값·PDF 아님 등). 같은 422 처리기를 쓴다."""


class ConversationNotFound(Exception):
    def __init__(self, conversation_id: int) -> None:
        super().__init__(f"conversation {conversation_id} not found")
        self.conversation_id = conversation_id
