"""가상 사용자: 구조화 출력, 사실 id 거르기, 형식 오류, 프롬프트에 정답 없음."""

import asyncio

import pytest

from harness.fakes import DEFAULT_SCENARIOS, Priced, sim_reply
from taxsplit.harness.scenarios import load_scenarios, public_view
from taxsplit.harness.sim_user import SimUser, system_prompt
from taxsplit.llm.base import LLMError

SCENARIO = public_view(load_scenarios(DEFAULT_SCENARIOS, ["v0-10"])[0])
TRANSCRIPT = [{"role": "user", "text": "안녕하세요"}, {"role": "assistant", "text": "소득은요?"}]


def test_reply_forces_tool_and_keeps_known_fact_ids() -> None:
    llm = Priced([sim_reply("100만 원 좀 넘어요", ["f3", "f99"], False)])
    reply = asyncio.run(SimUser(llm, SCENARIO).reply(TRANSCRIPT))
    assert reply.message == "100만 원 좀 넘어요"
    assert reply.revealed == ["f3"]  # 시나리오에 없는 id는 버림
    assert reply.done is False and reply.cost_usd > 0
    req = llm.requests[0]
    assert req.tool_choice == "reply" and req.kind == "sim_user"
    assert "[상담 AI] 소득은요?" in req.messages[0].content


def test_json_text_is_accepted_and_bad_shape_is_error() -> None:
    ok = Priced(['{"message": "네", "revealed": [], "done": true}'])
    assert asyncio.run(SimUser(ok, SCENARIO).reply(TRANSCRIPT)).done is True
    with pytest.raises(LLMError):
        asyncio.run(SimUser(Priced(["그냥 글"]), SCENARIO).reply(TRANSCRIPT))


def test_prompt_has_persona_and_facts_but_not_kinds() -> None:
    prompt = system_prompt(SCENARIO)
    assert SCENARIO["persona"] in prompt
    assert all(f["text"] in prompt for f in SCENARIO["facts"])
    assert "must_ask" not in prompt and "gold" not in SCENARIO


def test_prompt_has_exact_value_and_no_made_up_story_rules() -> None:
    # PR 11(#130) "다음에 할 것": 다시 물으면 사실의 값을 말하고, 없는 설명을 지어 붙이지 않는다
    prompt = system_prompt(SCENARIO)
    assert "정확한 값을 다시 물으면(말투와 상관없이)" in prompt
    assert "적힌 값을 그대로 말한다" in prompt
    assert "사실에 없는 설명(이유, 사정, 다른 가족 이야기, 날짜 등)을 지어 붙이지 않는다" in prompt
