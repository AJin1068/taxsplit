"""도구 쓰기: 요청에 도구 정의·도구 결과를 넣고, 답(한 번에·스트리밍)에서 tool_use를 읽는다.

가짜 전송 계층으로 실제 SDK를 돌린다. 기록 래퍼가 대화 번호를 남기는지도 본다.
"""

import asyncio
import json

import httpx2

from taxsplit.core.config import Settings
from taxsplit.llm.anthropic_client import AnthropicLLMClient
from taxsplit.llm.base import (
    CallKind,
    LLMError,
    LLMRequest,
    Message,
    StreamEnd,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)
from taxsplit.llm.call_log import InMemoryLlmCallRepository
from taxsplit.llm.fake import ScriptedLLMClient
from taxsplit.llm.recording import RecordingLLMClient

TOOL = ToolSpec("check_eligibility", "요건 확인", {"type": "object", "properties": {}})
ARGS = {"members": [{"name": "봄"}]}
REQUEST = LLMRequest(
    CallKind.MAIN_AGENT,
    [
        Message("user", "가족 확인해 줘"),
        Message("assistant", (TextBlock("확인할게요"), ToolUseBlock("tu_1", TOOL.name, ARGS))),
        Message("user", (ToolResultBlock("tu_1", "결과", is_error=True),)),
    ],
    model="claude-sonnet-5-5",
    max_tokens=100,
    tools=[TOOL],
)
USAGE = {"input_tokens": 12, "output_tokens": 4}
TOOL_MESSAGE = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-5-5",
    "content": [
        {"type": "text", "text": "부를게요"},
        {"type": "tool_use", "id": "tu_2", "name": TOOL.name, "input": ARGS},
    ],
    "stop_reason": "tool_use",
    "stop_sequence": None,
    "usage": USAGE,
}


def sse(*events: dict) -> bytes:
    return "".join(
        f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events
    ).encode()


STREAM = [
    {"type": "message_start", "message": {**TOOL_MESSAGE, "content": [], "stop_reason": None}},
    {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "tool_use", "id": "tu_2", "name": TOOL.name, "input": {}},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "input_json_delta", "partial_json": '{"members": [{"na'},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "input_json_delta", "partial_json": 'me": "봄"}]}'},
    },
    {"type": "content_block_stop", "index": 0},
    {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use", "stop_sequence": None},
        "usage": {"output_tokens": 4},
    },
    {"type": "message_stop"},
]


def make_client(response: httpx2.Response):
    seen: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return response

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return AnthropicLLMClient(api_key="sk-ant-test", http_client=http), seen


def test_request_carries_tools_and_tool_blocks() -> None:
    client, seen = make_client(httpx2.Response(200, json=TOOL_MESSAGE))
    asyncio.run(client.complete(REQUEST))

    body = json.loads(seen[0].content)
    assert body["tools"] == [
        {"name": TOOL.name, "description": "요건 확인", "input_schema": TOOL.input_schema}
    ]
    assert body["messages"][1]["content"] == [
        {"type": "text", "text": "확인할게요"},
        {"type": "tool_use", "id": "tu_1", "name": TOOL.name, "input": ARGS},
    ]
    assert body["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "결과", "is_error": True}
    ]


def test_complete_reads_tool_use() -> None:
    client, _ = make_client(httpx2.Response(200, json=TOOL_MESSAGE))
    response = asyncio.run(client.complete(REQUEST))

    assert response.text == "부를게요"
    assert response.stop_reason == "tool_use"
    assert response.tool_uses == (ToolUseBlock("tu_2", TOOL.name, ARGS),)


def test_stream_collects_tool_use_from_json_pieces() -> None:
    headers = {"content-type": "text/event-stream"}
    client, _ = make_client(httpx2.Response(200, content=sse(*STREAM), headers=headers))

    async def go():
        return [e async for e in client.stream(REQUEST)]

    events = asyncio.run(go())
    end = events[-1]
    assert isinstance(end, StreamEnd)
    assert end.response.tool_uses == (ToolUseBlock("tu_2", TOOL.name, ARGS),)


def test_recording_keeps_conversation_id() -> None:
    repo = InMemoryLlmCallRepository()
    settings = Settings(database_url="sqlite://", llm_provider="fake")
    llm = RecordingLLMClient(ScriptedLLMClient(["안녕하세요"]), repo, settings)
    request = LLMRequest(CallKind.MAIN_AGENT, [Message("user", "안녕")], conversation_id=7)
    asyncio.run(llm.complete(request))

    assert repo.items[0].conversation_id == 7
    assert repo.items[0].kind == CallKind.MAIN_AGENT


def test_scripted_fake_plays_steps_in_order() -> None:
    use = ToolUseBlock("tu_9", TOOL.name, ARGS)
    fake = ScriptedLLMClient([use, "끝", LLMError("실패")])
    request = LLMRequest(CallKind.MAIN_AGENT, [Message("user", "x")])

    first = asyncio.run(fake.complete(request))
    second = asyncio.run(fake.complete(request))
    assert first.tool_uses == (use,) and first.stop_reason == "tool_use"
    assert second.text == "끝" and second.tool_uses == ()
    try:
        asyncio.run(fake.complete(request))
    except LLMError as e:
        assert str(e) == "실패"
    else:
        raise AssertionError("오류가 나야 한다")
