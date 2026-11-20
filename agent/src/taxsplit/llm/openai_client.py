"""GPT 채점 클라이언트: 공식 OpenAI SDK 직접 호출 (ADR-0006, LangChain 없음).

평가 하네스의 GPT 채점(--judge)만 쓴다. 채점 답은 늘 JSON 객체 하나라서 응답 형식을
JSON 객체로 고정한다. 스트리밍·도구 호출은 쓰지 않는다.
"""

from collections.abc import AsyncIterator
from typing import Any

import openai

from taxsplit.llm.base import (
    LLMError,
    LLMRequest,
    LLMResponse,
    LLMTimeoutError,
    StreamEnd,
    StreamEvent,
    TextBlock,
    Usage,
)


def usage_from(raw: Any) -> Usage:
    """OpenAI usage → 우리 Usage. 캐시에서 읽은 토큰은 입력에서 빼서 cache_read로 옮긴다."""
    if raw is None:
        return Usage()
    details = getattr(raw, "input_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    return Usage(
        input_tokens=(raw.input_tokens or 0) - cached,
        output_tokens=raw.output_tokens or 0,
        cache_read_input_tokens=cached,
    )


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.text for b in content if isinstance(b, TextBlock))


def _to_llm_error(exc: Exception) -> LLMError:
    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeoutError("채점 호출 시간 초과")
    if isinstance(exc, openai.APIStatusError):
        return LLMError(
            f"채점 API 오류 ({exc.status_code}, {type(exc).__name__})",
            status_code=exc.status_code,
            request_id=exc.request_id,
        )
    if isinstance(exc, openai.APIConnectionError):
        return LLMError("채점 API 연결 실패")
    return LLMError(f"채점 호출 실패 ({type(exc).__name__})")


class OpenAILLMClient:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        client: Any | None = None,
    ) -> None:
        self._model = model
        # SDK 자동 재시도는 끈다(Anthropic 클라이언트와 같은 정책)
        self._client = client or openai.AsyncOpenAI(api_key=api_key, max_retries=0, timeout=timeout)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._model
        params: dict[str, Any] = {
            "model": model,
            "input": [{"role": m.role, "content": _text_of(m.content)} for m in request.messages],
            "text": {"format": {"type": "json_object"}},
            # 채점 기록을 OpenAI 쪽에 남기지 않는다
            "store": False,
        }
        if request.system is not None:
            params["instructions"] = request.system
        if request.max_tokens is not None:
            params["max_output_tokens"] = request.max_tokens
        try:
            resp = await self._client.responses.create(**params)
        except openai.OpenAIError as e:
            raise _to_llm_error(e) from e
        return LLMResponse(
            text=resp.output_text,
            model=getattr(resp, "model", None) or model,
            usage=usage_from(getattr(resp, "usage", None)),
            stop_reason=getattr(resp, "status", None),
            request_id=getattr(resp, "id", None),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        # 채점은 스트리밍이 필요 없다. 같은 모양을 맞추려고 한 번에 받아 끝 이벤트로 보낸다
        yield StreamEnd(await self.complete(request))
