"""PDF 추출 결과 형식.

추출 방법(pdfplumber+AI, 나중에 다른 방법)이 바뀌어도 이 형식은 그대로 둔다.
JSON 업로드도 같은 형식을 받는다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

# 공제 5그룹 중 PDF로 오는 4그룹 + 5그룹 밖(기부금·연금저축 등)
ExtractGroup = Literal["medical", "education", "card", "insurance", "other"]
GROUP_LABELS: dict[str, str] = {
    "medical": "의료비",
    "education": "교육비",
    "card": "카드 등 사용금액",
    "insurance": "보험료(국민연금·건강보험 등)",
    "other": "5그룹 밖",
}
# none = 그대로, exclude = 공제 대상이 아닌 지출, subtract = 빼고 계산하는 금액
# 어떤 줄이 exclude/subtract인지는 규칙표(*.excluded_spending)가 정한다
Mark = Literal["none", "exclude", "subtract"]
Fallback = Literal["json_upload"]

# 금액: 원 단위 0 이상 정수. "1000"(글자)이나 1000.5는 받지 않는다
Won = Annotated[StrictInt, Field(ge=0)]
NonBlank = Annotated[str, Field(min_length=1)]

PRIOR_YEAR_NOTE = "작년 자료: 올해 달라진 값은 대화로 고칩니다"


class _Base(BaseModel):
    # 모르는 칸은 받지 않고, 앞뒤 공백은 지워서 "빈 이름"을 잡는다
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExtractedItem(_Base):
    """PDF 한 줄 = 항목 하나. 같은 대상자·같은 금액 줄이 둘이면 둘 다 남긴다."""

    group: ExtractGroup
    kind: NonBlank = Field(description="세부 종류. 예: 신용카드, 현금영수증, 안경, 대학")
    person_name: NonBlank = Field(description="대상자 이름")
    person_birth: str | None = Field(
        default=None, description="생년 또는 생년월일 앞 6자리. PDF에 없으면 null"
    )
    amount: Won = Field(description="금액(원, 0 이상 정수)")
    source_text: str = Field(default="", description="이 항목을 뽑은 PDF 줄 글자")
    mark: Mark = Field(default="none", description="none / exclude / subtract")


class GroupTotal(_Base):
    """PDF에 적힌 그룹 합계. PDF에 합계가 없으면 넣지 않는다."""

    group: ExtractGroup
    amount: Won


class ExtractedDoc(_Base):
    """간소화 PDF 한 부의 추출 결과."""

    tax_year: StrictInt = Field(ge=2000, le=2100, description="PDF의 귀속연도")
    worker_name: NonBlank = Field(description="근로자 이름")
    items: list[ExtractedItem]
    totals: list[GroupTotal] = Field(default_factory=list)
    # 코드가 채운다(AI가 쓴 값은 덮어씀): 귀속연도가 서비스 연도와 다르면 True
    prior_year: bool = False
    notes: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """추출기 결과. 성공이면 doc, 실패면 errors와 fallback="json_upload"."""

    ok: bool
    doc: ExtractedDoc | None = None
    errors: list[str] = Field(default_factory=list)
    fallback: Fallback | None = None

    @classmethod
    def success(cls, doc: ExtractedDoc) -> ExtractionResult:
        return cls(ok=True, doc=doc)

    @classmethod
    def failure(cls, errors: list[str]) -> ExtractionResult:
        return cls(ok=False, errors=errors, fallback="json_upload")
