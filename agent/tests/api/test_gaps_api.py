"""채팅 API: 질문 카드 답(answer)을 구조화된 메시지로 받고, gaps 이벤트를 SSE로 보낸다."""

from fastapi.testclient import TestClient

from taxsplit.agent.events import parse_sse
from taxsplit.api.deps import get_chat_service, get_conversation_repo
from taxsplit.llm.base import ToolUseBlock
from taxsplit.llm.fake import ScriptedLLMClient
from taxsplit.main import create_app
from taxsplit.repositories.memory import (
    InMemoryAsyncToolCallRepository,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from taxsplit.rules.loader import load_rules
from taxsplit.services.chat_service import ChatService

RULES = load_rules(2025)
ANSWER = {"gap_id": "gap.parent_living_apart", "choice": "우리 부모님"}


async def no_evidence(rule_ids):
    return {}


def client(steps):
    repos = (
        InMemoryConversationRepository(),
        InMemoryMessageRepository(),
        InMemoryAsyncToolCallRepository(),
    )
    app = create_app()
    service = ChatService(*repos, ScriptedLLMClient(steps), RULES, no_evidence)
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[get_conversation_repo] = lambda: repos[0]
    return TestClient(app)


def test_card_answer_is_saved_and_gaps_event_sent():
    find = ToolUseBlock(id="g", name="find_missing_deductions", input={"family": {}})
    c = client([find, "부모님 태어난 해를 알려 주세요."])
    cid = c.post("/conversations", json={"title": "우리 집"}).json()["id"]
    res = c.post(f"/conversations/{cid}/messages", json={"content": "네", "answer": ANSWER})
    events = parse_sse(res.text)
    names = [e.name for e in events]
    assert names[-2:] == ["gaps", "done"]
    assert names.index("gaps") > max(i for i, n in enumerate(names) if n == "delta")
    assert events[-2].data["cards"][0]["id"] == "gap.parent_living_apart"
    saved = c.get(f"/conversations/{cid}/messages").json()[0]["content"]
    assert saved == "네\n[카드 답] gap.parent_living_apart: 우리 부모님"


def test_message_without_answer_unchanged():
    c = client(["안녕하세요."])
    cid = c.post("/conversations", json={"title": "t"}).json()["id"]
    events = parse_sse(c.post(f"/conversations/{cid}/messages", json={"content": "안녕"}).text)
    assert [e.name for e in events] == ["status", "delta", "done"]
    assert c.get(f"/conversations/{cid}/messages").json()[0]["content"] == "안녕"


def test_bad_card_answer_is_422():
    c = client([])
    cid = c.post("/conversations", json={"title": "t"}).json()["id"]
    bad = {"content": "네", "answer": {"gap_id": "2025.medical.x", "choice": "예"}}
    assert c.post(f"/conversations/{cid}/messages", json=bad).status_code == 422
