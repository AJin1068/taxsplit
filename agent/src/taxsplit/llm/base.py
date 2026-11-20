from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Protocol


class CallKind(StrEnum):
    """호출 종류. 종류마다 모델을 따로 설정하고, 기록에서 종류별 비용·지연을 나눠 본다."""

    MAIN_AGENT = "main_agent"  # 메인 대화
    PDF_EXTRACT = "pdf_extract"  # PDF 추출
    SIM_USER = "sim_user"  # 평가 하네스의 가상 사용자
    VERIFIER = "verifier"  # 서비스 안 검증 에이전트
    JUDGE = "judge"  # 채점 (GPT, llm/openai_client.py)


@dataclass(frozen=True)
class ToolSpec:
    """AI에게 주는 도구 하나(이름, 설명, 입력 JSON 스키마)."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class TextBlock:
    text: str


@dataclass(frozen=True)
class ToolUseBlock:
    """AI가 보낸 도구 호출 하나. id는 결과(ToolResultBlock)를 짝지을 때 쓴다."""

    id: str
    name: str
    input: Any


@dataclass(frozen=True)
class ToolResultBlock:
    """도구 결과를 AI에게 돌려주는 블록. is_error면 AI가 실패로 읽는다."""

    tool_use_id: str
    content: str
    is_error: bool = False


type ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


@dataclass(frozen=True)
class Message:
    """대화 한 줄. 글만 있으면 str, 도구 호출·결과가 있으면 블록 목록."""

    role: Literal["user", "assistant"]
    content: str | tuple[ContentBlock, ...]


@dataclass(frozen=True)
class LLMRequest:
    """한 번의 호출 요청. model·max_tokens를 비우면 설정값으로 채운다."""

    kind: CallKind
    messages: Sequence[Message]
    system: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    tools: Sequence[ToolSpec] = ()
    # 이 이름의 도구를 꼭 부르게 한다(구조화 출력용, 예: 가상 사용자). None이면 AI가 고름
    tool_choice: str | None = None
    # 호출 기록(llm_calls)에 남길 대화 번호. 대화 밖 호출(추출·평가)은 None
    conversation_id: int | None = None


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0  # 캐시 쓰기 (5분 캐시)
    cache_read_input_tokens: int = 0  # 캐시 읽기


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    usage: Usage
    stop_reason: str | None
    request_id: str | None = None
    # AI가 이번 답에서 부른 도구들(없으면 빈 tuple)
    tool_uses: tuple[ToolUseBlock, ...] = ()


@dataclass(frozen=True)
class TextDelta:
    """스트리밍 중 받은 글자 조각."""

    text: str


@dataclass(frozen=True)
class StreamEnd:
    """스트리밍의 마지막 이벤트. 모은 답과 토큰 수가 들어 있다."""

    response: LLMResponse


type StreamEvent = TextDelta | StreamEnd


@dataclass
class LLMError(Exception):
    """LLM 호출 실패. usage는 실패 전까지 알게 된 토큰 수(스트리밍 도중 실패 등)."""

    message: str
    status_code: int | None = None
    request_id: str | None = None
    usage: Usage = field(default_factory=Usage)

    def __str__(self) -> str:
        return self.message


class LLMTimeoutError(LLMError):
    """시간 초과 (연결, 조각 사이 대기, 전체 마감 중 하나)."""


class LLMClient(Protocol):
    """LLM 호출 인터페이스. 공급자별 구현(fake, anthropic)과 기록 래퍼가 같은 모양이다."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """답을 한 번에 받는다."""
        ...

    def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        """답을 조각(TextDelta)으로 받고, 성공하면 마지막에 StreamEnd 하나를 받는다."""
        ...
