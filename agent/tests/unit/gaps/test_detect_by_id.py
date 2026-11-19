"""빈 곳 찾기를 항목 ID별로: 알림이 나가야 하는 가구와 나가면 안 되는 가구를 하나씩.

pytest 이름 끝이 `[gap.항목-fires]` / `[gap.항목-quiet]`라 결과가 항목 ID별로 보인다.
"""

import pytest

from gaps.helpers import doc, fam, household, item, m, of, parent
from taxsplit.gaps import DETECTORS, find_gaps
from taxsplit.gaps.family import FIRST_IDS
from taxsplit.rules.loader import load_rules

RULES = load_rules(2025)
MOM = m("엄마", "parent", 1955, family_of="wife")
MED = item("medical", "남편", "일반", 500_000)

# 항목 ID → (알림이 나가야 하는 경우, 나가면 안 되는 경우). 경우 = find_gaps에 넘길 인자
CASES = {
    "gap.parent_living_apart": ({"family": fam(answered=())}, {"family": fam()}),
    "gap.adult_no_consent": (
        {"family": fam(MOM)},
        {"family": fam(MOM), "documents": [doc(item("medical", "엄마"))]},
    ),
    "gap.child_turned_adult": (
        {"family": fam(m("큰애", "child", 2005))},
        {"family": fam(m("큰애", "child", 2007))},
    ),
    "gap.parent_claimed_by_sibling": (
        {"family": fam(MOM)},
        {"family": fam(MOM.model_copy(update={"claimed_by_sibling": False}))},
    ),
    "gap.severe_illness": ({"family": fam()}, {"family": fam(answered=())}),
    "gap.over_income_family": (
        {"family": fam(MOM.model_copy(update={"listed_over_income": True}))},
        {"family": fam(MOM)},
    ),
    "gap.died_this_year": (
        {"family": fam()},
        {"family": fam(answered=(*FIRST_IDS, "gap.died_this_year"))},
    ),
    "gap.other_household_family": (
        {"family": fam(answered=("gap.parent_living_apart",))},
        {"family": fam()},
    ),
    "gap.infertility": ({"family": fam(), "documents": [doc(MED)]}, {"family": fam()}),
    "gap.glasses": (
        {"family": fam(), "documents": [doc(MED)]},
        {"family": fam(), "documents": [doc(item("medical", "남편", "안경"))]},
    ),
    "gap.school_uniform": (
        {"family": fam(m("둘째", "child", 2010))},
        {"family": fam(m("둘째", "child", 2016))},
    ),
    "gap.field_trip": (
        {"family": fam(m("둘째", "child", 2016))},
        {"family": fam(m("둘째", "child", 2021))},
    ),
    "gap.preschool_academy": (
        {"family": fam(m("막내", "child", 2021))},
        {"family": fam(m("막내", "child", 2016))},
    ),
    "gap.overseas_education": ({"family": fam(m("막내", "child", 2021))}, {"family": fam(MOM)}),
    "gap.payer_of_medical_education": (
        {
            "family": fam(MOM),
            "household": household(
                members=[parent()],
                medical=[{"payer": "wife", "for_whom": "엄마", "amount": 6_000_000}],
            ),
            "rules": RULES,
        },
        {
            "family": fam(MOM),
            "household": household(
                members=[parent()],
                medical=[{"payer": "wife", "for_whom": "엄마", "amount": 100_000}],
            ),
            "rules": RULES,
        },
    ),
    "gap.dependent_card_usage": (
        {"family": fam(MOM)},
        {"family": fam(m("동생", "sibling", 1995, lives_with=True))},
    ),
    "gap.missing_clinic": ({"family": fam(), "documents": [doc(MED)]}, {"family": fam()}),
    "gap.insurance_reimbursement": (
        {"family": fam(), "documents": [doc(MED)]},
        {"family": fam(), "documents": [doc(MED, item("medical", "남편", "실손의료보험금"))]},
    ),
    "gap.medical_device_special_ed": (
        {"family": fam(MOM.model_copy(update={"disabled_or_severe": True}))},
        {"family": fam(MOM)},
    ),
    "gap.birth_order": (
        {"family": fam(m("아기", "child", 2025))},
        {"family": fam(m("아기", "child", 2025, birth_order=1))},
    ),
    "gap.job_change": ({"family": fam()}, {"family": fam(answered=(*FIRST_IDS, "gap.job_change"))}),
}

PARAMS = [
    pytest.param(gap_id, case, fires, id=f"{gap_id}-{'fires' if fires else 'quiet'}")
    for gap_id, (fire, quiet) in sorted(CASES.items())
    for case, fires in ((fire, True), (quiet, False))
]


def test_cases_cover_every_item():
    assert set(CASES) == set(DETECTORS)


@pytest.mark.parametrize(("gap_id", "case", "fires"), PARAMS)
def test_gap_item(gap_id, case, fires):
    cards = of(find_gaps(**case), gap_id)
    assert bool(cards) is fires, [c.model_dump() for c in cards]


def test_card_fields_follow_event_contract():
    card = of(find_gaps(fam(MOM)), "gap.adult_no_consent")[0]
    data = card.model_dump(mode="json")
    assert set(data) >= {
        "id",
        "kind",
        "person",
        "title",
        "why",
        "todo",
        "source_pages",
        "question",
        "estimate",
    }
    assert data["person"] == "엄마" and data["kind"] == "나"
    assert data["estimate"] is None
    # 놓칠 금액 질문: 금액이 적힌 세 칸
    assert [o["amount"] for o in data["question"]["options"]] == [300_000, 1_000_000, 3_000_000]
    assert "엄마" in data["why"] and "{person}" not in data["why"]


def test_first_questions_ask_family_not_spending():
    from taxsplit.agent.money import extract_amounts
    from taxsplit.gaps import first_questions, parent_follow_ups

    first = first_questions()
    assert [c.id for c in first] == list(FIRST_IDS)
    assert [o.label for o in first[0].question.options] == [
        "우리 부모님",
        "배우자 부모님",
        "둘 다",
        "없음",
    ]
    # 지출 금액을 기억해 내라고 묻지 않는다
    assert extract_amounts(first[0].question.text) == []
    assert [c.person for c in parent_follow_ups((MOM, m("아이", "child", 2016)))] == ["엄마"]
