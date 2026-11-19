"""끝 조건 4가지(answered, stopped, error, max_turns)와 비용 상한 멈춤."""

import asyncio
import json

from harness.fakes import (
    DEFAULT_SCENARIOS,
    QUESTION,
    LLMError,
    deps_for,
    factory,
    main_steps,
    sim_reply,
    sim_steps,
)
from taxsplit.harness.__main__ import main
from taxsplit.harness.runner import MAX_USER_TURNS, run_conversation
from taxsplit.harness.scenarios import load_scenarios, public_view
from taxsplit.llm.base import ToolUseBlock

SCENARIO = load_scenarios(DEFAULT_SCENARIOS, ["v0-02"])[0]


def run(main_s: list, sim_s: list, max_turns: int = MAX_USER_TURNS, **kw) -> dict:
    deps = deps_for(main_s, sim_s, **kw)

    async def go() -> dict:
        async with deps.client:
            conv = await run_conversation(
                deps.client, public_view(SCENARIO), 1, deps.sim_llm, max_turns
            )
        return conv.record()

    return asyncio.run(go())


def test_answered_needs_allocation_and_sim_done() -> None:
    rec = run(main_steps(SCENARIO["household"]), sim_steps(SCENARIO))
    assert rec["ended"] == "answered"
    assert rec["final"]["members"][0]["relation"] == "lineal_ascendant"
    assert rec["revealed"] == ["f3"]


def test_sim_done_without_allocation_keeps_going_until_max_turns() -> None:
    # 배분안을 받지 않았으면 가상 사용자가 끝났다고 해도 answered가 아니다
    rec = run([QUESTION] * 3, [sim_reply("네", [], True)] * 3, max_turns=3)
    assert rec["ended"] == "max_turns"
    assert rec["turns"] == 3
    assert rec["final"] is None


def test_max_turns_default_is_12() -> None:
    assert MAX_USER_TURNS == 12
    rec = run([QUESTION] * 12, [sim_reply("잘 모르겠어요", [], False)] * 12)
    assert rec["ended"] == "max_turns"
    assert rec["turns"] == 12


def test_guard_stop_is_stopped() -> None:
    # 한 턴 AI 호출 수 상한(1번)을 도구 호출로 넘기면 guard_stop
    use = ToolUseBlock(id="c", name="check_eligibility", input=SCENARIO["household"])
    rec = run([use], [], max_llm_calls=1)
    assert rec["ended"] == "stopped"


def test_main_agent_failure_is_error() -> None:
    rec = run([LLMError("가짜 실패")], [])
    assert rec["ended"] == "error"
    assert "AI 호출 실패" in rec["error"]


def test_sim_user_failure_is_error() -> None:
    rec = run([QUESTION], [LLMError("가짜 실패")])
    assert rec["ended"] == "error"
    assert "가상 사용자" in rec["error"]


def test_cost_cap_stops_before_new_conversation(tmp_path) -> None:
    steps = main_steps(SCENARIO["household"])
    deps = deps_for(steps * 3, sim_steps(SCENARIO) * 3)
    out = tmp_path / "r.json"
    code = main(
        ["run", "--only", "v0-02", "--max-cost-usd", "0.0000001", "--out", str(out)],
        factory(deps),
    )
    assert code == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["stopped_by_cost_cap"] is True
    # 첫 대화로 상한을 넘었으니 반복 2·3번째 대화는 시작하지 않는다
    assert len(result["records"]) == 1
    assert result["cost"]["total_usd"] > 0.0000001
