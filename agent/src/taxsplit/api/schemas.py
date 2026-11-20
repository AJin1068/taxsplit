from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from taxsplit.domain.models import SelfRole
from taxsplit.extract.models import ExtractedDoc
from taxsplit.gaps.models import CardAnswer

# FR-10 첫 화면 자녀 수 고르기 범위(0~5명)
MAX_CHILD_COUNT = 5


class CreateConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # 간소화 PDF 추출 결과(ExtractedDoc 형식) 0~2개. 검사는 서비스가 PR 12 검사로 한다
    documents: list[Any] = Field(default_factory=list)
    # FR-09·FR-10 첫 화면 설정. 고르지 않고 시작하면 둘 다 없음
    self_role: SelfRole | None = None
    child_count: int | None = Field(default=None, ge=0, le=MAX_CHILD_COUNT)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    # 질문 카드의 선택지를 눌렀으면 그 답(PR 24). 없으면 글만 보낸 것
    answer: CardAnswer | None = None


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
    self_role: SelfRole | None = None
    child_count: int | None = None


class ExtractionRequest(BaseModel):
    """PDF 한 개(base64) 또는 추출 형식 JSON 한 개. 둘 중 하나만 보낸다."""

    model_config = ConfigDict(populate_by_name=True)

    filename: str | None = Field(default=None, max_length=200)
    pdf_base64: str | None = None
    # 파이썬 json 모듈 이름과 겹치지 않게 속성 이름은 data, 요청 칸 이름은 json
    data: dict[str, Any] | None = Field(default=None, alias="json")


class ExtractionResponse(BaseModel):
    """추출 결과(doc)와 검사 결과(ok·errors). 실패면 fallback="json_upload"."""

    ok: bool
    doc: ExtractedDoc | None = None
    errors: list[str] = Field(default_factory=list)
    fallback: Literal["json_upload"] | None = None
    filename: str | None = None
