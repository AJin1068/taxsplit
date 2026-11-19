"""가짜 LLM으로 추출기 흐름 보기: 재시도 한 번, 그 뒤 JSON 업로드로 대신하기."""

import asyncio
import copy
import json

from taxsplit.extract import DEFAULT_PDF_MODEL, LlmPdfExtractor, pdf_model
from taxsplit.llm.base import CallKind, LLMError
from taxsplit.llm.fake import FakeLLMClient

from .conftest import SequenceLLM, load_answer, load_pdf

PDF = load_pdf("doc1_2025")
GOOD = json.dumps(load_answer("doc1_2025"), ensure_ascii=False)


def _run(client, pdf=PDF):
    return asyncio.run(LlmPdfExtractor(client).extract(pdf))


def test_good_reply_passes_with_one_call():
    llm = SequenceLLM([GOOD])
    result = _run(llm)
    assert result.ok and result.fallback is None and len(llm.requests) == 1
    request = llm.requests[0]
    assert request.kind == CallKind.PDF_EXTRACT and request.model == DEFAULT_PDF_MODEL
    # AI에게는 PDF에서 뽑은 글자가 간다
    assert "근로자 성명" in request.messages[0].content


def test_broken_json_then_good_retries_once():
    llm = SequenceLLM(['{"tax_year": 2025, "items": [', GOOD])
    result = _run(llm)
    assert result.ok and len(llm.requests) == 2
    retry = llm.requests[1].messages
    assert [m.role for m in retry] == ["user", "assistant", "user"]
    assert "JSON 형식이 깨졌습니다" in retry[2].content


def test_broken_json_twice_falls_back_to_json_upload():
    llm = SequenceLLM(["not json", "still not json"])
    result = _run(llm)
    assert not result.ok and result.fallback == "json_upload" and len(llm.requests) == 2
    assert result.errors[0].startswith("(전체): JSON 형식이 깨졌습니다")


def test_total_mismatch_twice_falls_back_with_reason():
    bad = copy.deepcopy(load_answer("doc1_2025"))
    bad["items"] = [i for i in bad["items"] if i["group"] != "education"][:-1] + [
        i for i in bad["items"] if i["group"] == "education"
    ]  # 카드 줄 하나를 빠뜨린 답
    reply = json.dumps(bad, ensure_ascii=False)
    llm = SequenceLLM([reply, reply])
    result = _run(llm)
    assert not result.ok and result.fallback == "json_upload"
    assert any("카드 등 사용금액 합계가 맞지 않습니다" in e for e in result.errors)


def test_negative_amount_fails_with_field_reason():
    bad = copy.deepcopy(load_answer("doc1_2025"))
    bad["items"][3]["amount"] = -96_500
    reply = json.dumps(bad, ensure_ascii=False)
    result = _run(SequenceLLM([reply, reply]))
    assert not result.ok and result.errors == ["items[3].amount: 0 이상이어야 합니다"]


def test_llm_error_falls_back_without_retry():
    llm = FakeLLMClient(error=LLMError("서버 오류", status_code=529))
    result = _run(llm)
    assert not result.ok and result.fallback == "json_upload"
    assert result.errors == ["AI 호출 실패: 서버 오류"] and len(llm.requests) == 1


def test_unreadable_pdf_falls_back_without_calling_ai():
    llm = SequenceLLM([])
    result = _run(llm, pdf=b"%PDF-broken")
    assert not result.ok and result.fallback == "json_upload" and llm.requests == []
    assert result.errors[0].startswith("PDF를 열 수 없습니다")


def test_pdf_model_comes_from_settings_or_haiku():
    class S:
        llm_model_pdf_extract = ""

    assert pdf_model(S()) == DEFAULT_PDF_MODEL
    S.llm_model_pdf_extract = "claude-sonnet-5-5"
    assert pdf_model(S()) == "claude-sonnet-5-5"
