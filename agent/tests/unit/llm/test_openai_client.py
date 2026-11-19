"""GPT 채점 클라이언트(OpenAI SDK 직접 호출): 요청 모양, 토큰·비용, 오류 바꾸기, 팩토리."""

import asyncio
from types import SimpleNamespace

import httpx2
import openai
import pytest

from taxsplit.core.config import Settings
from taxsplit.llm.base import CallKind, LLMError, LLMRequest, Message
from taxsplit.llm.factory import JUDGE_DEFAULT_MODEL, build_judge_client, judge_model
from taxsplit.llm.openai_client import OpenAILLMClient
from taxsplit.llm.pricing import cost_usd

REQUEST = LLMRequest(
    kind=CallKind.JUDGE, messages=[Message("user", "채점해 주세요")], system="규칙", max_tokens=99
)


class FakeResponses:
    def __init__(self, result=None, error=None) -> None:
        self.result, self.error, self.calls = result, error, []

    async def create(self, **params):
        self.calls.append(params)
        if self.error:
            raise self.error
        return self.result


def client_with(responses: FakeResponses) -> OpenAILLMClient:
    return OpenAILLMClient(
        api_key="x", model="gpt-6.2-sol", client=SimpleNamespace(responses=responses)
    )


def test_complete_sends_json_request_and_maps_usage() -> None:
    usage = SimpleNamespace(
        input_tokens=1000, output_tokens=50, input_tokens_details=SimpleNamespace(cached_tokens=200)
    )
    raw = SimpleNamespace(
        output_text='{"consistent": true}',
        model="gpt-6.2-sol",
        usage=usage,
        status="completed",
        id="r1",
    )
    responses = FakeResponses(raw)
    resp = asyncio.run(client_with(responses).complete(REQUEST))
    params = responses.calls[0]
    assert params["model"] == "gpt-6.2-sol" and params["store"] is False
    assert params["text"] == {"format": {"type": "json_object"}}
    assert params["instructions"] == "규칙" and params["max_output_tokens"] == 99
    assert params["input"] == [{"role": "user", "content": "채점해 주세요"}]
    assert resp.text == '{"consistent": true}'
    assert (resp.usage.input_tokens, resp.usage.cache_read_input_tokens) == (800, 200)
    # 단가표: 입력 2, 캐시 읽기 0.10, 출력 10 (USD/100만 토큰)
    assert float(cost_usd("openai", "gpt-6.2-sol", resp.usage)) == pytest.approx(0.00212)


def test_api_error_becomes_llm_error() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.RateLimitError("느림", response=httpx2.Response(429, request=request), body=None)
    with pytest.raises(LLMError) as info:
        asyncio.run(client_with(FakeResponses(error=error)).complete(REQUEST))
    assert info.value.status_code == 429


def test_factory_needs_key_and_gpt_model() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_judge_client(Settings(_env_file=None, database_url="x"))
    with pytest.raises(ValueError, match="GPT 모델 이름 필요"):
        build_judge_client(
            Settings(_env_file=None, database_url="x", openai_api_key="k", llm_model_judge="claude")
        )
    settings = Settings(_env_file=None, database_url="x", openai_api_key="k")
    assert judge_model(settings) == JUDGE_DEFAULT_MODEL
    assert isinstance(build_judge_client(settings), OpenAILLMClient)
