"""POST /extractions(UI-03): 가짜 LLM으로 PDF 한 개, JSON 한 개, 잘못된 파일 422."""

import base64
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from taxsplit.api.deps import get_extractor
from taxsplit.extract import LlmPdfExtractor
from taxsplit.llm.base import LLMRequest, LLMResponse
from taxsplit.llm.fake import FakeLLMClient
from taxsplit.main import create_app

# 추출 단위 테스트가 쓰는 가상 PDF와 그 추출 결과를 같이 쓴다
FIXTURES = Path(__file__).resolve().parents[1] / "unit" / "extract" / "fixtures"
PDF = (FIXTURES / "doc1_2025.pdf").read_bytes()
ANSWER = json.loads((FIXTURES / "doc1_2025.json").read_text(encoding="utf-8"))


class ReplyLLM(FakeLLMClient):
    """늘 같은 답(추출 JSON)을 돌려주는 가짜 LLM."""

    def __init__(self, reply: str) -> None:
        super().__init__()
        self.reply = reply

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.reply, model="fake", usage=self.usage, stop_reason="end_turn")


@pytest.fixture
def llm() -> ReplyLLM:
    return ReplyLLM(json.dumps(ANSWER, ensure_ascii=False))


@pytest.fixture
def client(llm: ReplyLLM) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_extractor] = lambda: LlmPdfExtractor(llm)
    yield TestClient(app)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_pdf_upload_returns_doc_and_check_result(client: TestClient, llm: ReplyLLM) -> None:
    res = client.post("/extractions", json={"filename": "남편.pdf", "pdf_base64": _b64(PDF)})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["errors"] == [] and body["fallback"] is None
    assert body["filename"] == "남편.pdf"
    assert body["doc"]["worker_name"] == ANSWER["worker_name"]
    assert len(body["doc"]["items"]) == len(ANSWER["items"])
    assert len(llm.requests) == 1


def test_pdf_with_data_url_prefix(client: TestClient) -> None:
    data_url = "data:application/pdf;base64," + _b64(PDF)
    assert client.post("/extractions", json={"pdf_base64": data_url}).json()["ok"] is True


def test_pdf_failing_check_twice_returns_fallback(llm: ReplyLLM, client: TestClient) -> None:
    llm.reply = "not json"
    body = client.post("/extractions", json={"pdf_base64": _b64(PDF)}).json()
    assert body["ok"] is False and body["fallback"] == "json_upload"
    assert body["errors"][0].startswith("(전체): JSON 형식이 깨졌습니다")


def test_json_upload_checked_without_llm(client: TestClient, llm: ReplyLLM) -> None:
    res = client.post("/extractions", json={"filename": "a.json", "json": ANSWER})
    assert res.status_code == 200 and res.json()["ok"] is True
    assert res.json()["doc"]["worker_name"] == ANSWER["worker_name"]
    assert llm.requests == []


def test_json_upload_with_bad_field_reports_path(client: TestClient) -> None:
    bad = {**ANSWER, "items": [{**ANSWER["items"][0], "amount": -1}]}
    body = client.post("/extractions", json={"json": bad}).json()
    assert body["ok"] is False
    assert any(e.startswith("items[0].amount") for e in body["errors"])


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"pdf_base64": ""}, "파일이 비어 있습니다"),
        ({"pdf_base64": "   "}, "파일이 비어 있습니다"),
        ({"pdf_base64": _b64(b"hello, not a pdf")}, "PDF 파일이 아닙니다"),
        ({"pdf_base64": "@@@not base64@@@"}, "base64 글자가 아닙니다"),
        ({}, "하나만 보내 주세요"),
        ({"pdf_base64": _b64(PDF), "json": ANSWER}, "하나만 보내 주세요"),
    ],
)
def test_bad_upload_is_422(client: TestClient, llm: ReplyLLM, payload: dict, reason: str) -> None:
    res = client.post("/extractions", json=payload)
    assert res.status_code == 422
    assert any(reason in line for line in res.json()["detail"])
    # 잘못된 파일은 AI를 부르지 않는다(돈이 드는 호출 없음)
    assert llm.requests == []
