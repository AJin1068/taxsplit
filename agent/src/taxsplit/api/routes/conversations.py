from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from taxsplit.api.deps import ChatServiceDep, ConversationServiceDep
from taxsplit.api.schemas import (
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    SendMessageRequest,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest, service: ChatServiceDep
) -> ConversationResponse:
    # documents 검사에 떨어지면 InvalidDocuments → 422 (main.py)
    conversation = await service.create(body.title, body.documents)
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int, service: ConversationServiceDep
) -> ConversationResponse:
    conversation = await service.get(conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: int, body: SendMessageRequest, service: ChatServiceDep
) -> StreamingResponse:
    """답을 SSE(text/event-stream)로 보낸다. 이벤트 모양은 agent/events.py."""
    # 없는 대화면 스트리밍을 시작하기 전에 404가 난다
    events = await service.start_turn(conversation_id, body.content, body.answer)

    async def body_stream():
        async for event in events:
            yield event.to_sse()

    return StreamingResponse(
        body_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{conversation_id}/messages")
async def list_messages(conversation_id: int, service: ChatServiceDep) -> list[MessageResponse]:
    messages = await service.list_messages(conversation_id)
    return [MessageResponse.model_validate(m) for m in messages]
