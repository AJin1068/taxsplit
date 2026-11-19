"""채팅 API를 가짜 LLM으로 끝까지.

SSE 이벤트 순서, 배분 금액 = 도구 직접 호출, 서버 다시 만들기, documents 검사.
"""

import json
from typing import Any

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
from taxsplit.services.evidence_service import EvidenceService
from taxsplit.tools.handlers import run_compare_allocations
from taxsplit.tools.validation import validate_household

RULES = load_rules(2025)
# 손으로 만든 가상 가구(eval/ 사례와 무관)
HOUSEHOLD: dict[str, Any] = {
    "husband": {"gross_salary": 62_000_000, "sex": "male", "birth_year": 1984},
    "wife": {"gross_salary": 38_000_000, "sex": "female", "birth_year": 1986},
    "members": [
        {
            "dependent": {
                "name": "하늘",
                "relation": "child",
                "birth_year": 2016,
                "income_amount": 0,
            }
        },
        {
            "dependent": {
                "name": "봄",
                "relation": "lineal_ascendant",
                "birth_year": 1954,
                "income_amount": 0,
            },
            "family_of": "husband",
        },
    ],
    "medical": [{"payer": "wife", "for_whom": "봄", "amount": 4_200_000}],
}
ANSWER = "봄 님은 아내 쪽에서 공제받으세요. 흔한 방식보다 329,000원 더 돌려받아요."
EVIDENCE = EvidenceService(RULES, "keyword")


def use(tool: str, id_: str) -> ToolUseBlock:
    return ToolUseBlock(id=id_, name=tool, input=HOUSEHOLD)


class Server:
    """앱 객체 하나. repos를 넘기면 같은 저장소로 '서버를 다시 켠' 것과 같다."""

    def __init__(self, steps: list, repos: tuple | None = None) -> None:
        self.repos = repos or (
            InMemoryConversationRepository(),
            InMemoryMessageRepository(),
            InMemoryAsyncToolCallRepository(),
        )
        self.llm = ScriptedLLMClient(steps)
        self.app = create_app()
        service = ChatService(*self.repos, self.llm, RULES, EVIDENCE)
        self.app.dependency_overrides[get_chat_service] = lambda: service
        self.app.dependency_overrides[get_conversation_repo] = lambda: self.repos[0]
        self.client = TestClient(self.app)

    def send(self, cid: int, content: str):
        res = self.client.post(f"/conversations/{cid}/messages", json={"content": content})
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        return parse_sse(res.text)


def test_full_conversation_event_order_and_amounts() -> None:
    question = "부양가족 이름과 출생연도, 올해 소득을 알려 주실래요?"
    server = Server(
        [question, use("check_eligibility", "a"), use("compare_allocations", "b"), ANSWER]
    )
    cid = server.client.post("/conversations", json={"title": "우리 집"}).json()["id"]

    first = server.send(cid, "맞벌이인데 공제를 어떻게 나눌까요?")
    assert [e.name for e in first] == ["status", "delta", "done"]

    events = server.send(cid, "아이 하늘(2016), 어머니 봄(1954), 둘 다 소득 없어요")
    order = [e.name for e in events]
    assert order == [
        "status",
        "status",
        "status",
        *["delta"] * (order.count("delta")),
        "allocation",
        "evidence",
        "done",
    ]
    assert [e.data.get("tool") for e in events[1:3]] == ["check_eligibility", "compare_allocations"]
    assert "".join(e.data["text"] for e in events if e.name == "delta") == ANSWER

    # allocation의 금액은 같은 가구로 도구를 직접 부른 결과와 모두 같다
    household, _ = validate_household(HOUSEHOLD)
    direct = run_compare_allocations(household, RULES)
    allocation = next(e.data for e in events if e.name == "allocation")
    members = allocation.pop("members")
    assert allocation == json.loads(json.dumps(direct, ensure_ascii=False))
    assert members == [
        {"name": "하늘", "relation": "child", "birth_year": 2016},
        {"name": "봄", "relation": "lineal_ascendant", "birth_year": 1954},
    ]

    evidence = next(e.data for e in events if e.name == "evidence")
    assert set(evidence) == set(direct["rule_ids"])
    assert any(evidence.values())  # 키워드 검색으로 근거가 하나 이상 나온다
    some = next(v for v in evidence.values() if v)[0]
    assert {"rule_id", "page", "snippet", "tax_year"} <= set(some)

    done = events[-1].data
    assert done["ended"] == "answered" and done["turn"] == 2
    assert [c["status"] for c in done["tool_calls"]] == ["ok", "ok"]
    assert done["usage"]["input_tokens"] == 30

    listed = server.client.get(f"/conversations/{cid}/messages").json()
    assert [(m["seq"], m["role"]) for m in listed] == [
        (1, "user"),
        (2, "assistant"),
        (3, "user"),
        (4, "assistant"),
    ]
    assert listed[3]["content"] == ANSWER


def test_restart_rebuilds_state_from_storage() -> None:
    first = Server([use("check_eligibility", "a"), "요건을 확인했어요. 의료비는 누가 냈나요?"])
    cid = first.client.post("/conversations", json={"title": "t"}).json()["id"]
    first.send(cid, "가족 정보예요")

    # 새 앱 객체 + 같은 저장소. 서버 메모리에는 아무것도 없다
    second = Server([use("compare_allocations", "b"), ANSWER], repos=first.repos)
    events = second.send(cid, "의료비는 아내가 냈어요")
    done = events[-1].data
    assert done["turn"] == 2
    assert done["tool_calls"] == [{"tool": "compare_allocations", "status": "ok", "errors": []}]
    assert done["ended"] == "answered"
    # 지난 턴의 가구 정보가 시스템 프롬프트에 붙고, 대화 기록은 글만 간다
    request = second.llm.requests[0]
    assert "지금까지 확인한 가구 정보" in request.system
    assert all(isinstance(m.content, str) for m in request.messages)


def test_missing_conversation_is_404() -> None:
    server = Server([])
    res = server.client.post("/conversations/999/messages", json={"content": "안녕"})
    assert res.status_code == 404
    assert server.client.get("/conversations/999/messages").status_code == 404
