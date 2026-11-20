"""가짜 LLM 대화: 빈 곳 찾기 도구 → gaps 이벤트, 카드의 금액만 답에 나와 금액 센서를 통과한다."""

from agent.fixtures import collect, make_service, run
from taxsplit.llm.base import ToolUseBlock
from taxsplit.tools import FIND_MISSING_DEDUCTIONS as FIND

HOUSEHOLD = {
    "husband": {"gross_salary": 80_000_000, "sex": "male", "birth_year": 1980},
    "wife": {"gross_salary": 30_000_000, "sex": "female", "birth_year": 1982},
    "members": [
        {
            "dependent": {
                "name": "엄마",
                "relation": "lineal_ascendant",
                "birth_year": 1955,
                "income_amount": 0,
            },
            "family_of": "husband",
        }
    ],
    "medical": [{"payer": "husband", "for_whom": "husband", "amount": 5_000_000}],
}
DOC = {
    "tax_year": 2025,
    "worker_name": "남편",
    "items": [{"group": "medical", "kind": "일반", "person_name": "남편", "amount": 5_000_000}],
}
ARGS = {
    "family": {
        "members": [{"name": "엄마", "relation": "parent", "birth_year": 1955}],
        "answered": ["gap.parent_living_apart", "gap.other_household_family"],
    },
    "household": HOUSEHOLD,
    "picks": [{"person": "엄마", "amount": 1_000_000}],
}
# 카드 estimate의 saving(150,000원)을 만 원 단위로 줄여 옮긴 답
GOOD = (
    "엄마 자료가 간소화에 안 보여요. 고르신 금액으로 계산한 예상으로는 "
    "병원비를 넣으면 15만 원을 더 돌려받아요."
)
TEXT = "보통 · 연 100만 원쯤이요"


def turn(steps):
    service, llm, repos = make_service(steps)
    conv = run(service.create("t", [DOC]))
    return run(collect(service, conv.id, TEXT)), llm


def test_gaps_event_and_amount_sensor_pass():
    events, llm = turn([ToolUseBlock(id="g", name=FIND, input=ARGS), GOOD])
    names = [e.name for e in events]
    assert events[-1].data["ended"] == "answered"
    assert names[-2:] == ["gaps", "done"] and "allocation" not in names
    cards = events[-2].data["cards"]
    consent = next(c for c in cards if c["id"] == "gap.adult_no_consent")
    assert consent["estimate"]["saving"] == 150_000
    assert consent["consent_message"].endswith("자료가 함께 보여요.")
    assert "".join(e.data["text"] for e in events if e.name == "delta") == GOOD
    # 도구가 지침에 들어 있다
    assert FIND in llm.requests[0].system and FIND in {t.name for t in llm.requests[0].tools}


def test_amount_not_in_card_is_blocked():
    bad = "병원비를 넣으면 23만 원을 더 돌려받아요."
    events, llm = turn([ToolUseBlock(id="g", name=FIND, input=ARGS), bad, GOOD])
    assert events[-1].data["ended"] == "answered"
    # 첫 답은 센서에 걸려 다시 쓰게 했다
    assert "23만 원" in llm.requests[2].messages[-1].content
    assert "".join(e.data["text"] for e in events if e.name == "delta") == GOOD


def test_failed_find_call_sends_no_gaps_event():
    broken = {**ARGS, "picks": [{"person": "엄마", "amount": 2_000_000}]}
    events, _ = turn(
        [ToolUseBlock(id="g", name=FIND, input=broken), "어머니 병원비를 다시 골라 주세요."]
    )
    assert "gaps" not in [e.name for e in events]
    assert events[-1].data["tool_calls"][0]["status"] == "invalid_args"
