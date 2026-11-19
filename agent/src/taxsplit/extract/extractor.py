"""추출기: PDF → 글자 뽑기 → AI 정리 → 검사 → 결과(또는 JSON 업로드로 대신).

추출 방법은 `Extractor` 인터페이스 뒤에 둔다. 시나리오③(PR 22)에서 다른 방법을
같은 인터페이스로 끼워 비교한다.
"""

from typing import Any, Protocol

from taxsplit.extract.models import ExtractionResult
from taxsplit.extract.prompt import build_retry_message, build_system_prompt, build_user_message
from taxsplit.extract.text import has_text, pdf_text, render_pages
from taxsplit.extract.validate import check_doc
from taxsplit.llm.base import CallKind, LLMClient, LLMError, LLMRequest, Message
from taxsplit.rules.loader import Rule

# PDF 추출 기본 모델은 Haiku(ADR-0006). 설정 llm_model_pdf_extract가 있으면 그것을 쓴다
DEFAULT_PDF_MODEL = "claude-haiku-5-5"
# 항목 수십 개의 JSON이 들어갈 만큼. 넘치면 JSON이 잘려 검사에 떨어진다
PDF_MAX_TOKENS = 8192


class Extractor(Protocol):
    """추출 방법 인터페이스. 성공이면 doc, 실패면 이유와 fallback="json_upload"."""

    async def extract(self, pdf_bytes: bytes) -> ExtractionResult: ...


def pdf_model(settings: Any) -> str:
    """설정에서 PDF 추출 모델을 고른다. 비어 있으면 Haiku."""
    specific = getattr(settings, "llm_model_pdf_extract", "") or ""
    return specific.strip() or DEFAULT_PDF_MODEL


class LlmPdfExtractor:
    """v1 추출기: pdfplumber로 글자를 뽑고 AI(Haiku)가 JSON으로 정리한다.

    검사에 떨어지면 실패 이유를 붙여 한 번만 다시 부른다. 또 떨어지면 JSON 업로드로 대신한다.
    """

    def __init__(
        self,
        client: LLMClient,
        *,
        model: str = DEFAULT_PDF_MODEL,
        rules: dict[str, Rule] | None = None,
        max_tokens: int = PDF_MAX_TOKENS,
    ) -> None:
        self._client = client
        self._model = model
        self._system = build_system_prompt(rules)
        self._max_tokens = max_tokens

    async def extract(self, pdf_bytes: bytes) -> ExtractionResult:
        # 1) 글자 뽑기. 못 열거나 글자가 없으면 AI를 부르지 않고 바로 대신하기
        try:
            pages = pdf_text(pdf_bytes)
        except ValueError as e:
            return ExtractionResult.failure([str(e)])
        if not has_text(pages):
            return ExtractionResult.failure(
                ["PDF에서 글자를 찾지 못했습니다(스캔한 이미지 PDF일 수 있습니다)"]
            )

        # 2) AI 정리 → 검사. 실패하면 이유를 붙여 한 번만 다시
        messages = [Message("user", build_user_message(render_pages(pages)))]
        errors: list[str] = []
        for attempt in range(2):
            try:
                response = await self._client.complete(self._request(messages))
            except LLMError as e:
                return ExtractionResult.failure([f"AI 호출 실패: {e}"])
            doc, errors = check_doc(response.text)
            if doc is not None:
                return ExtractionResult.success(doc)
            if attempt == 0:
                messages += [
                    Message("assistant", response.text or "(빈 답)"),
                    Message("user", build_retry_message(errors)),
                ]

        # 3) 두 번 다 떨어짐 → JSON 업로드로 대신
        return ExtractionResult.failure(errors)

    def _request(self, messages: list[Message]) -> LLMRequest:
        return LLMRequest(
            kind=CallKind.PDF_EXTRACT,
            messages=list(messages),
            system=self._system,
            model=self._model,
            max_tokens=self._max_tokens,
        )


def from_json_upload(data: str | bytes | dict[str, Any]) -> ExtractionResult:
    """JSON 업로드 길. AI 답과 같은 검사를 거친다. 실패면 어느 칸이 틀렸는지 이유에 적는다."""
    doc, errors = check_doc(data)
    if doc is None:
        return ExtractionResult.failure(errors)
    return ExtractionResult.success(doc)
