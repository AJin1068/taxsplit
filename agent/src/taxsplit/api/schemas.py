from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # 간소화 PDF 추출 결과(ExtractedDoc 형식) 0~2개. 검사는 서비스가 PR 12 검사로 한다
    documents: list[Any] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    role: Literal["user", "assistant"]
    content: str


class ConversationResponse(BaseModel):
    # dataclass 같은 일반 객체에서 속성을 읽어 응답을 만들 수 있게 함
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
