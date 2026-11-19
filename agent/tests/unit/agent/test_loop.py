"""한 턴의 끝나는 방식 4가지와 경계.

정상, 센서 다시 쓰기, 센서 멈춤, 검사기 멈춤, AI 실패, 한 턴 AI 호출 10번.
"""

from agent.fixtures import HOUSEHOLD, collect, make_service, run, use
from taxsplit.agent.events import GUARD_STOP_TEXT, SENSOR_STOP_TEXT
from taxsplit.llm.base import LLMError, ToolResultBlock
from taxsplit.tools.policy import ToolPolicy

CHECK, COMPARE = "check_eligibility", "compare_allocations"
WIDE = ToolPolicy(max_calls_per_turn=20)
GOOD = "봄 님은 아내 쪽에서 공제받으세요. 흔한 방식보다 329,000원 더 돌려받아요."


def turn(steps, text="가족 정보 알려 드렸어요", **kw):
    service, llm, repos = make_service(steps, **kw)
    conv = run(service.create("t"))
    events = run(collect(service, conv.id, text))
    return events, llm, repos, conv


def names(events):
    return [e.name for e in events]


def done(events):
    assert events[-1].name == "done"
    return events[-1].data


def text_of(events):
    return "".join(e.data["text"] for e in events if e.name == "delta")


def test_answered_with_tools_sends_allocation() -> None:
    events, llm, _, _ = turn([use(CHECK, id_="a"), use(COMPARE, id_="b"), GOOD])
    assert done(events)["ended"] == "answered"
    assert text_of(events) == GOOD
    assert names(events)[-3:] == ["allocation", "evidence", "done"]
    # 도구 결과가 다음 요청에 tool_result로 들어간다
    second = llm.requests[1].messages[-1]
    assert isinstance(second.content[0], ToolResultBlock)
    assert llm.requests[0].tools and llm.requests[0].conversation_id == 1


def test_sensor_fail_once_then_rewrite_passes() -> None:
    bad = "봄 님은 남편 쪽에서 공제받으세요."
    events, llm, _, _ = turn([use(CHECK, id_="a"), use(COMPARE, id_="b"), bad, GOOD])
    assert done(events)["ended"] == "answered"
    assert text_of(events) == GOOD
    # 다시 쓰기 요청에 떨어진 이유(어느 문장)가 들어간다
    assert "판정 센서" in llm.requests[3].messages[-1].content
    assert bad not in text_of(events)


def test_sensor_fail_twice_stops_with_fixed_text() -> None:
    bad = "50만 원 더 받아요."
    events, _, _, _ = turn([bad, bad])
    assert done(events)["ended"] == "sensor_stop"
    assert text_of(events) == SENSOR_STOP_TEXT
    assert "allocation" not in names(events)


def test_guard_stop_after_repeated_invalid_args() -> None:
    broken = {**HOUSEHOLD, "husband": {"gross_salary": "많이"}}
    steps = [use(CHECK, broken, id_=str(i)) for i in range(3)]
    events, _, repos, _ = turn(steps)
    d = done(events)
    assert d["ended"] == "guard_stop"
    assert text_of(events) == GUARD_STOP_TEXT
    assert [c["status"] for c in d["tool_calls"]] == ["invalid_args"] * 3
    assert d["tool_calls"][0]["errors"]
    # 멈춰도 도구 호출 기록은 저장된다
    assert len(run(repos[2].list_for(1))) == 3


def test_llm_error_sends_error_then_done() -> None:
    events, _, repos, _ = turn([use(CHECK, id_="a"), LLMError("연결 끊김")])
    assert names(events)[-2:] == ["error", "done"]
    assert done(events)["ended"] == "error"
    assert "delta" not in names(events)
    assert done(events)["message_id"] is None
    # 사용자 글은 저장, AI 답은 없음
    assert [m.role for m in run(repos[1].list_for(1))] == ["user"]


def test_ten_llm_calls_is_the_limit() -> None:
    # 요건 확인만 9번 부르고 10번째에 글로 답하면 통과(도구 8번 제한과 겹치지 않게 넓힌 정책)
    steps = [use(CHECK, id_=str(i)) for i in range(9)] + ["가족 확인을 마쳤어요. 더 알려 주세요."]
    events, llm, _, _ = turn(steps, policy=WIDE)
    assert done(events)["ended"] == "answered"
    assert len(llm.requests) == 10


def test_eleventh_llm_call_is_not_made() -> None:
    steps = [use(CHECK, id_=str(i)) for i in range(10)] + ["안 불려야 하는 답"]
    events, llm, _, _ = turn(steps, policy=WIDE)
    assert done(events)["ended"] == "guard_stop"
    assert len(llm.requests) == 10
    assert text_of(events) == GUARD_STOP_TEXT


def test_order_violation_is_reported_not_stopped() -> None:
    events, _, _, _ = turn(
        [use(COMPARE, id_="a"), "먼저 가족 정보를 확인할게요. 어머니 소득이 있으세요?"]
    )
    d = done(events)
    assert d["ended"] == "answered"
    assert d["tool_calls"][0]["status"] == "order_violation"
