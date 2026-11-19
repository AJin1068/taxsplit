"""우리 요청·답 모양(llm/base.py) ↔ Anthropic API 모양 바꾸기. 도구 정의·호출·결과 블록 포함."""

import json
from typing import Any

from taxsplit.llm.base import (
    ContentBlock,
    LLMRequest,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
)


def usage_from(raw: object) -> Usage:
    return Usage(
        input_tokens=getattr(raw, "input_tokens", None) or 0,
        output_tokens=getattr(raw, "output_tokens", None) or 0,
        cache_creation_input_tokens=getattr(raw, "cache_creation_input_tokens", None) or 0,
        cache_read_input_tokens=getattr(raw, "cache_read_input_tokens", None) or 0,
    )


def _block(block: ContentBlock) -> dict[str, Any]:
    match block:
        case TextBlock(text=text):
            return {"type": "text", "text": text}
        case ToolUseBlock(id=id_, name=name, input=input_):
            return {"type": "tool_use", "id": id_, "name": name, "input": input_}
        case ToolResultBlock(tool_use_id=tid, content=content, is_error=is_error):
            return {
                "type": "tool_result",
                "tool_use_id": tid,
                "content": content,
                "is_error": is_error,
            }


def _message(m: Message) -> dict[str, Any]:
    if isinstance(m.content, str):
        return {"role": m.role, "content": m.content}
    return {"role": m.role, "content": [_block(b) for b in m.content]}


def request_params(request: LLMRequest) -> dict[str, Any]:
    """SDK messages.create에 넘길 인자."""
    if request.model is None or request.max_tokens is None:
        raise ValueError("model과 max_tokens가 채워진 요청이어야 한다 (RecordingLLMClient 경유)")
    params: dict[str, Any] = {
        "model": request.model,
        "max_tokens": request.max_tokens,
        "messages": [_message(m) for m in request.messages],
    }
    if request.system is not None:
        params["system"] = request.system
    if request.tools:
        params["tools"] = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in request.tools
        ]
    return params


def tool_uses_from(content: list[Any]) -> tuple[ToolUseBlock, ...]:
    """한 번에 받은 답의 content에서 tool_use 블록만 뽑는다."""
    return tuple(
        ToolUseBlock(id=b.id, name=b.name, input=b.input)
        for b in content
        if getattr(b, "type", None) == "tool_use"
    )


class ToolUseCollector:
    """스트리밍에서 tool_use 블록을 모은다. 입력은 JSON 조각(input_json_delta)으로 나뉘어 온다."""

    def __init__(self) -> None:
        self._open: dict[int, tuple[str, str, list[str]]] = {}
        self.done: list[ToolUseBlock] = []

    def start(self, index: int, block: Any) -> None:
        if getattr(block, "type", None) == "tool_use":
            self._open[index] = (block.id, block.name, [])

    def delta(self, index: int, partial_json: str) -> None:
        if index in self._open:
            self._open[index][2].append(partial_json)

    def stop(self, index: int) -> None:
        if index not in self._open:
            return
        id_, name, parts = self._open.pop(index)
        raw = "".join(parts)
        # 입력이 없는 도구는 빈 글자가 온다. 깨진 JSON은 글자 그대로 넘겨 검사기가 거절하게 한다
        try:
            value: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            value = raw
        self.done.append(ToolUseBlock(id=id_, name=name, input=value))
