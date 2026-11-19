"""성질 테스트: 처음 보는 가상 가구 300개에서 "잡으면 안 되는 것" 6가지가 0건(Issue #126).

결과는 항목별 카드 건수와 위반 건수 표로 pytest 끝에 출력한다(property report).
"""

from collections import Counter

import pytest

from property import report
from property.gap_households import YEAR, make_case
from taxsplit.allocation.compare import compare_allocations
from taxsplit.gaps import find_gaps
from taxsplit.gaps.family import ADULT_AGE, in_middle_or_high, in_school, is_preschool
from taxsplit.synth import make_households

# 성질 테스트(PR 7)의 1,000개(시드 0~999)와 겹치지 않는 처음 보는 가구
N_HOUSEHOLDS = 300
BASE_SEED = 50_000
CONSENT = ("gap.adult_no_consent", "gap.child_turned_adult", "gap.dependent_card_usage")
SCHOOL = {"gap.school_uniform": in_middle_or_high, "gap.field_trip": in_school}
SELF_ONLY = ("국민연금", "건강보험", "연금저축", "퇴직연금", "주택자금", "대학원")

MUST_NOT = {
    1: "자료가 이미 있는 성인 가족에게 동의 알림",
    2: "19세 미만 자녀에게 동의 안내",
    3: "형제자매·손주에게 따로 살아도 공제 안내(또는 같이 안 사는데 동의 알림)",
    4: "본인 불입분만 공제되는 항목이 비었다고 알림",
    5: "누가 냈든 결과가 같은데 누가 냈는지 묻기",
    6: "해당 자녀가 없는데 교복·체험학습·취학 전 학원 질문",
}


def _text(c) -> str:
    return " ".join([c.why, c.todo, c.question.text if c.question else "", c.consent_message or ""])


def _flip_same(household, person, rules) -> bool:
    """테스트가 직접: 그 가족 지출을 낸 사람을 바꿔도 최적안 합계가 같은가."""
    swap = {"husband": "wife", "wife": "husband"}

    def flip(rows):
        return tuple(
            r.model_copy(update={"payer": swap[r.payer]}) if r.for_whom == person else r
            for r in rows
        )

    other = household.model_copy(
        update={"medical": flip(household.medical), "education": flip(household.education)}
    )
    best = compare_allocations(household, rules).best.total
    return best == compare_allocations(other, rules).best.total


def _violations(case, cards, rules) -> list[tuple[int, str]]:
    by_name = {m.name: m for m in case.family.members}
    has_rows = {
        i["person_name"] for d in case.documents for i in d["items"] if i["group"] != "insurance"
    }
    out = []
    for c in cards:
        m = by_name.get(c.person) if c.person else None
        if c.id in CONSENT and m is not None:
            if m.name in has_rows:
                out.append((1, f"{c.id} {m.name}"))
            if m.relation == "child" and YEAR - m.birth_year < ADULT_AGE:
                out.append((2, f"{c.id} {m.name}"))
            if m.relation in ("sibling", "grandchild", "foster_child") and (
                m.lives_with is not True
                or c.id == "gap.dependent_card_usage"
                and m.relation == "sibling"
            ):
                out.append((3, f"{c.id} {m.name}"))
        if m is not None and m.relation in ("sibling", "grandchild") and "따로" in _text(c):
            out.append((3, f"{c.id} {m.name} 따로"))
        if any(w in _text(c) for w in SELF_ONLY):
            out.append((4, c.id))
        if c.id == "gap.payer_of_medical_education" and _flip_same(case.household, c.person, rules):
            out.append((5, f"{c.person}"))
        check = SCHOOL.get(c.id) or (is_preschool if c.id == "gap.preschool_academy" else None)
        if check and (m is None or not check(m, YEAR)):
            out.append((6, f"{c.id} {c.person}"))
    return out


@pytest.fixture(scope="module")
def gap_results():
    from taxsplit.rules.loader import load_rules

    rules = load_rules(2025)
    cards_count: Counter[str] = Counter()
    found: list[tuple[int, int, str]] = []
    for hh in make_households(N_HOUSEHOLDS, BASE_SEED):
        case = make_case(hh)
        cards = find_gaps(case.family, case.documents, household=case.household, rules=rules)
        cards_count.update(c.id for c in cards)
        found += [(case.seed, n, d) for n, d in _violations(case, cards, rules)]
    bad = Counter(n for _, n, _ in found)
    report.LINES += [
        f"### 빈 곳 찾기 성질 테스트: 처음 보는 가구 {N_HOUSEHOLDS}개(시드 {BASE_SEED}~)",
        "",
        "| 잡으면 안 되는 것 | 위반 건수 |",
        "| --- | --- |",
        *[f"| {n}. {text} | {bad[n]} |" for n, text in MUST_NOT.items()],
        "",
        "| 항목 ID | 카드 건수 |",
        "| --- | --- |",
        *[f"| {gid} | {cards_count[gid]} |" for gid in sorted(cards_count)],
        "",
    ]
    return found, cards_count


@pytest.mark.parametrize("rule", sorted(MUST_NOT), ids=lambda n: f"must_not_{n}")
def test_must_not_zero(rule, gap_results):
    found, _ = gap_results
    bad = [f"seed={s} {d}" for s, n, d in found if n == rule]
    assert not bad, f"{MUST_NOT[rule]} {len(bad)}건\n" + "\n".join(bad[:20])


def test_detectors_actually_fire(gap_results):
    # 0건이 "아무것도 안 잡아서"가 아님을 보인다: 동의·누가 냈나·학교 질문이 실제로 나온다
    _, count = gap_results
    for gap_id in ("gap.adult_no_consent", "gap.payer_of_medical_education", "gap.field_trip"):
        assert count[gap_id] > 0, gap_id
