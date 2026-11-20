"""추출 서비스(UI-03, FR-01): 올린 PDF 한 개 또는 추출 형식 JSON 한 개를 읽어 검사 결과와 돌려준다.

PDF는 추출기(`Extractor`, 기본은 PR 12 `LlmPdfExtractor`)가 읽는다. 추출기는 밖에서 넣어 주므로
테스트는 가짜 LLM 추출기로 바꿔 끼운다. FastAPI와 저장소 구현체를 import하지 않는다.
"""

import base64
import binascii
from typing import Any

from taxsplit.domain.models import InvalidUpload
from taxsplit.extract import ExtractionResult, Extractor, from_json_upload

# 간소화 PDF 한 부는 몇백 KB다. 너무 큰 파일은 AI에 보내기 전에 막는다
# 가정: 개발 판단(PR 14b "개발이 정한 것"), 10MB
MAX_PDF_BYTES = 10 * 1024 * 1024
# PDF 파일은 늘 이 글자로 시작한다
PDF_MAGIC = b"%PDF-"


def decode_pdf(pdf_base64: str) -> bytes:
    """base64 글자 → PDF 바이트. 빈 값·base64 아님·PDF 아님·너무 큼이면 InvalidUpload."""
    text = pdf_base64.strip()
    # 브라우저 FileReader가 붙이는 "data:application/pdf;base64," 앞머리는 떼고 읽는다
    if text.startswith("data:") and "," in text:
        text = text.split(",", 1)[1]
    if not text:
        raise InvalidUpload(["pdf_base64: 파일이 비어 있습니다"])
    try:
        data = base64.b64decode(text, validate=True)
    except binascii.Error, ValueError:
        raise InvalidUpload(["pdf_base64: base64 글자가 아닙니다"]) from None
    if not data:
        raise InvalidUpload(["pdf_base64: 파일이 비어 있습니다"])
    if len(data) > MAX_PDF_BYTES:
        raise InvalidUpload([f"pdf_base64: 파일이 너무 큽니다(최대 {MAX_PDF_BYTES:,}바이트)"])
    if not data.startswith(PDF_MAGIC):
        raise InvalidUpload(["pdf_base64: PDF 파일이 아닙니다"])
    return data


class ExtractionService:
    def __init__(self, extractor: Extractor) -> None:
        self._extractor = extractor

    async def extract(
        self, pdf_base64: str | None = None, data: dict[str, Any] | None = None
    ) -> ExtractionResult:
        """PDF와 JSON 중 정확히 하나만 받는다. 검사에 떨어진 추출 결과는 ok=False로 돌려준다."""
        if (pdf_base64 is None) == (data is None):
            raise InvalidUpload(["(전체): pdf_base64와 json 중 하나만 보내 주세요"])
        if data is not None:
            # JSON 올리기: AI를 부르지 않고 같은 검사만 거친다
            return from_json_upload(data)
        assert pdf_base64 is not None
        return await self._extractor.extract(decode_pdf(pdf_base64))
