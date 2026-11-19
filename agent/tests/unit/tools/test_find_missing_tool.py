"""도구 find_missing_deductions가 호출 검사기(PR 9 방식)를 지나 실행된다."""

import pytest

from taxsplit.gaps import estimate_missing
from taxsplit.gaps.models import GapRequest
from taxsplit.tools import FIND_MISSING_DEDUCTIONS as FIND
from taxsplit.tools import InMemoryToolCallRepository, ToolCallGuard, ToolStatus

MOM = {"name": "엄마", "relation": "parent", "birth_year": 1955, "family_of": "husband"}
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


def args(**kw):
    return {"family": {"members": [MOM]}, **kw}


def ids(result):
    return [c["id"] for c in result["cards"]]


def test_family_only_call_passes_without_check_eligibility(guard):
    g = guard.call(FIND, {"family": {}})
    assert g.status == ToolStatus.OK
    # 가족을 아직 모르면 첫 질문 묶음(부모님, 같이 사는 가족)이 나온다
    assert ids(g.result)[:2] == ["gap.parent_living_apart", "gap.other_household_family"]
    assert g.record.tool == FIND and g.record.result == g.result


def test_server_documents_are_used(rules):
    no_docs = ToolCallGuard(rules, InMemoryToolCallRepository())
    assert "gap.adult_no_consent" in ids(no_docs.call(FIND, args()).result)
    doc = {**DOC, "items": [*DOC["items"], {**DOC["items"][0], "person_name": "엄마"}]}
    with_docs = ToolCallGuard(rules, InMemoryToolCallRepository(), documents=[doc])
    assert "gap.adult_no_consent" not in ids(with_docs.call(FIND, args()).result)


def test_pick_attaches_engine_estimate_to_consent_card(guard, rules):
    pick = {"person": "엄마", "amount": 1_000_000}
    g = guard.call(FIND, args(household=HOUSEHOLD, picks=[pick]))
    assert g.status == ToolStatus.OK, g.message
    card = next(c for c in g.result["cards"] if c["id"] == "gap.adult_no_consent")
    req = GapRequest.model_validate(args(household=HOUSEHOLD))
    direct = estimate_missing(req.household, "엄마", 1_000_000, rules)
    assert card["estimate"] == direct.model_dump(mode="json")
    assert card["estimate"]["saving"] == 150_000


@pytest.mark.parametrize(
    ("bad", "path"),
    [
        (
            args(household=HOUSEHOLD, picks=[{"person": "엄마", "amount": 2_000_000}]),
            "picks[0].amount",
        ),
        (args(picks=[{"person": "엄마", "amount": 1_000_000}]), "picks[0]"),
        (
            args(household=HOUSEHOLD, picks=[{"person": "삼촌", "amount": 300_000}]),
            "picks[0].person",
        ),
        (
            args(
                household={**HOUSEHOLD, "husband": {**HOUSEHOLD["husband"], "gross_salary": "많이"}}
            ),
            "household.husband.gross_salary",
        ),
        ({"family": {"members": [{**MOM, "birth_year": "모름"}]}}, "family.members[0].birth_year"),
    ],
    ids=[
        "amount_not_option",
        "pick_without_household",
        "unknown_person",
        "household_bad",
        "bad_year",
    ],
)
def test_invalid_args_are_rejected(guard, bad, path):
    g = guard.call(FIND, bad)
    assert g.status == ToolStatus.INVALID_ARGS
    assert any(e.startswith(path) for e in g.record.errors), g.record.errors


def test_household_needs_income_like_other_tools(guard):
    hh = {
        **HOUSEHOLD,
        "members": [
            {"dependent": {"name": "엄마", "relation": "lineal_ascendant", "birth_year": 1955}}
        ],
    }
    g = guard.call(FIND, args(household=hh))
    assert g.status == ToolStatus.INVALID_ARGS
    assert any("income_missing" in e or "소득" in e for e in g.record.errors)


def test_unknown_tool_lists_three_tools(guard):
    g = guard.call("guess", {})
    assert g.status == ToolStatus.UNKNOWN_TOOL and FIND in g.message
