"""추출 테스트 공용: 가상 PDF·정답 JSON 읽기, 답을 차례로 돌려주는 가짜 LLM."""

import json
from pathlib import Path

import pytest

from taxsplit.llm.base import LLMRequest, LLMResponse
from taxsplit.llm.fake import FakeLLMClient

FIXTURES = Path(__file__).parent / "fixtures"
DOC_NAMES = ["doc1_2025", "doc2_2025_layout", "doc3_2024"]


def load_pdf(name: str) -> bytes:
    return (FIXTURES / f"{name}.pdf").read_bytes()


def load_answer(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class SequenceLLM(FakeLLMClient):
    """부를 때마다 replies의 다음 답을 돌려준다(재시도 테스트용)."""

    def __init__(self, replies: list[str]) -> None:
        super().__init__()
        self.replies = list(replies)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        text = self.replies.pop(0)
        return LLMResponse(
            text=text, model=request.model or "fake", usage=self.usage, stop_reason="end_turn"
        )


@pytest.fixture
def answers() -> dict[str, dict]:
    return {name: load_answer(name) for name in DOC_NAMES}
