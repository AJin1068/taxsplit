"""대화 하나(시나리오 × 반복 1번)를 채팅 API로 돌려 실행 기록을 만든다.

화면과 같은 API를 부른다(docs/design.md 2장): 대화 만들기(documents) → 첫 메시지(opening) →
에이전트 답(SSE) → 가상 사용자 답 → … 실행 기록 모양은 eval/scoring/README.md.

끝 조건(Issue #20 정해진 결정, 운영값):
  answered   배분안(allocation 이벤트)을 받은 뒤 가상 사용자가 "끝났다"고 함
  stopped    에이전트 턴이 guard_stop·sensor_stop으로 끝남
  error      AI 호출 실패(에이전트·가상 사용자) 또는 API 오류
  max_turns  사용자 턴이 MAX_USER_TURNS를 넘김
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx2

from taxsplit.agent.events import parse_sse
from taxsplit.harness.sim_user import SimUser
from taxsplit.llm.base import LLMClient, LLMError

MAX_USER_TURNS = 12


@dataclass
class Conversation:
    """대화 하나 동안 모으는 값. record()가 실행 기록 dict로 바꾼다."""

    scenario_id: str
    repeat: int
    ended: str = "error"
    turns: int = 0
    transcript: list[dict[str, str]] = field(default_factory=list)
    revealed: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final: dict[str, Any] | None = None
    # 마지막 배분 비교 원본(allocation 이벤트)과 그때의 에이전트 답. GPT 채점이 쓴다
    allocation: dict[str, Any] | None = None
    answer_after_allocation: str | None = None
    # 대화 동안 화면에 낸 빈 곳 알림 카드(gaps 이벤트). 실행 기록 gaps 칸(id, member)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    main_usd: Decimal | None = Decimal(0)
    sim_usd: Decimal | None = Decimal(0)
    error: str | None = None

    def add_main(self, cost: float | None) -> None:
        # 모르는 비용이 하나라도 있으면 합계도 "알 수 없음"(None)
        self.main_usd = (
            None if cost is None or self.main_usd is None else self.main_usd + Decimal(str(cost))
        )

    def add_sim(self, cost: Decimal | None) -> None:
        self.sim_usd = None if cost is None or self.sim_usd is None else self.sim_usd + cost

    def record(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "repeat": self.repeat,
            "ended": self.ended,
            "turns": self.turns,
            "transcript": self.transcript,
            "revealed": self.revealed,
            "tool_calls": self.tool_calls,
            "final": self.final,
            "cost": {
                "main_agent_usd": _num(self.main_usd),
                "sim_user_usd": _num(self.sim_usd),
                "judge_usd": None,
            },
            "judge": None,
            "gaps": self.gaps,
            "error": self.error,
        }


def _num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def gap_member(card: dict[str, Any]) -> dict[str, Any] | None:
    """카드 주인(관계·태어난 해). 카드에 두 칸이 다 없으면(가구 전체 질문 등) None.

    이름으로 가족을 짐작하지 않는다(같은 이름이 둘일 수 있다). 카드에 실린 두 칸만 쓴다.
    """
    relation, birth_year = card.get("relation"), card.get("birth_year")
    if relation is None or birth_year is None:
        return None
    return {"relation": relation, "birth_year": birth_year}


async def _send(client: httpx2.AsyncClient, cid: int, text: str, conv: Conversation) -> str:
    """메시지 하나를 보내고 SSE를 읽어 conv에 모은다. 돌려주는 값은 에이전트 턴의 ended."""
    conv.turns += 1
    conv.transcript.append({"role": "user", "text": text})
    res = await client.post(f"/conversations/{cid}/messages", json={"content": text})
    if res.status_code != 200:
        conv.error = f"메시지 API {res.status_code}: {res.text[:200]}"
        return "error"
    answer, ended, allocation = "", "error", None
    for event in parse_sse(res.text):
        if event.name == "delta":
            answer += event.data.get("text", "")
        elif event.name == "gaps":
            # 카드는 턴마다 새로 나온다. 화면에 낸 카드를 모두 모으되, 같은 카드는 한 번만 남긴다
            for c in event.data.get("cards", []):
                shown = {"id": c.get("id"), "member": gap_member(c)}
                if shown not in conv.gaps:
                    conv.gaps.append(shown)
        elif event.name == "allocation":
            allocation = event.data
        elif event.name == "error":
            conv.error = event.data.get("message")
        elif event.name == "done":
            ended = event.data.get("ended", "error")
            conv.tool_calls += event.data.get("tool_calls", [])
            conv.add_main((event.data.get("usage") or {}).get("cost_usd"))
    if answer:
        conv.transcript.append({"role": "assistant", "text": answer})
    if allocation is not None:
        # 화면에 보여 준 최적안과 그 비교에 쓴 가족 전부(채점이 관계·출생연도로 짝지음)
        conv.final = {
            "assignment": allocation.get("best", {}).get("assignment", {}),
            "members": allocation.get("members", []),
        }
        conv.allocation, conv.answer_after_allocation = allocation, answer
    return ended


async def run_conversation(
    client: httpx2.AsyncClient,
    scenario: dict[str, Any],
    repeat: int,
    sim_llm: LLMClient,
    max_turns: int = MAX_USER_TURNS,
) -> Conversation:
    """scenario는 public_view(기준 정답 없음)여야 한다."""
    conv = Conversation(scenario["id"], repeat)
    res = await client.post(
        "/conversations",
        json={"title": "평가 하네스", "documents": scenario["documents"]},
    )
    if res.status_code != 201:
        conv.error = f"대화 만들기 API {res.status_code}: {res.text[:200]}"
        return conv
    cid = res.json()["id"]
    sim = SimUser(sim_llm, scenario)
    text = scenario["opening"]
    while True:
        ended = await _send(client, cid, text, conv)
        if ended in ("guard_stop", "sensor_stop"):
            conv.ended = "stopped"
            return conv
        if ended != "answered":
            conv.ended = "error"
            return conv
        try:
            reply = await sim.reply(conv.transcript)
        except LLMError as e:
            conv.ended, conv.error = "error", f"가상 사용자 호출 실패: {e}"
            return conv
        conv.add_sim(reply.cost_usd)
        conv.revealed += [i for i in reply.revealed if i not in conv.revealed]
        if conv.final is not None and reply.done:
            conv.ended = "answered"
            return conv
        if conv.turns >= max_turns:
            conv.ended = "max_turns"
            return conv
        text = reply.message
