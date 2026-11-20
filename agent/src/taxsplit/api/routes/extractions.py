from fastapi import APIRouter

from taxsplit.api.deps import ExtractionServiceDep
from taxsplit.api.schemas import ExtractionRequest, ExtractionResponse

router = APIRouter(prefix="/extractions", tags=["extractions"])


@router.post("")
async def create_extraction(
    body: ExtractionRequest, service: ExtractionServiceDep
) -> ExtractionResponse:
    """간소화 PDF(base64) 또는 추출 형식 JSON 한 개 → 읽은 값과 검사 결과.

    잘못된 파일(빈 값·PDF 아님·둘 다/둘 다 없음)은 InvalidUpload → 422 (main.py).
    읽었지만 검사에 떨어지면 200에 ok=false·errors·fallback="json_upload"로 돌려준다.
    고친 값은 화면이 POST /conversations의 documents로 넘긴다.
    """
    result = await service.extract(body.pdf_base64, body.data)
    return ExtractionResponse(**result.model_dump(), filename=body.filename)
