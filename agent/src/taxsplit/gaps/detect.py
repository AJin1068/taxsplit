"""빈 곳 찾기(순수 함수): 가족 목록 + 간소화 추출 결과 → 알림 카드 목록.

항목마다 "조건 → 카드" 함수를 하나씩 두고 질문 표 ID로 묶는다(DETECTORS). LLM을 부르지 않는다.
가구(Household)와 규칙표가 있으면 "누가 냈나"(15번)를 계산 엔진으로 판단한다.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from taxsplit.allocation.models import Household
from taxsplit.extract.models import ExtractedDoc
from taxsplit.gaps import family as F
from taxsplit.gaps.consent import consent_message
from taxsplit.gaps.docs import DocView, view
from taxsplit.gaps.estimate import estimate_question, payer_matters
from taxsplit.gaps.loader import GapQuestion, load_questions
from taxsplit.gaps.models import MUST_LIVE_TOGETHER, FamilyAnswer, FamilyMember, GapCard
from taxsplit.rules.loader import Rule


@dataclass(frozen=True)
class Ctx:
    family: FamilyAnswer
    docs: DocView
    household: Household | None
    rules: dict[str, Rule] | None
    year: int

    @property
    def members(self) -> tuple[FamilyMember, ...]:
        return self.family.members

    def answered(self, gap_id: str) -> bool:
        return gap_id in self.family.answered

    def after_family(self) -> bool:
        """가족 질문(첫 질문 묶음)에 답을 받은 뒤인가."""
        return all(self.answered(i) for i in F.FIRST_IDS)


Detector = Callable[[GapQuestion, Ctx], list[GapCard]]


def _once(q: GapQuestion, c: Ctx, cond: bool = True) -> list[GapCard]:
    """가구 전체에 한 번만 묻는 질문."""
    return [F.card(q)] if cond and not c.answered(q.id) else []


def _per(q: GapQuestion, c: Ctx, pick: Callable[[FamilyMember], bool]) -> list[GapCard]:
    """조건에 맞는 가족마다 카드 하나."""
    if c.answered(q.id):
        return []
    return [F.card(q, m.name) for m in c.members if pick(m)]


def needs_consent(m: FamilyMember, c: Ctx) -> bool:
    """공제 대상으로 보이는 성인 가족인데 그 사람 이름으로 된 지출이 한 줄도 없나.

    19세 미만 자녀는 동의 없이 조회된다(인쇄 378쪽). 형제자매·손주·위탁아동은 같이 살 때만,
    다른 형제가 공제받는 부모님·소득 초과 표시가 붙은 가족은 공제 대상으로 보지 않는다.
    """
    if not F.is_adult(m, c.year) or c.docs.has_rows(m.name):
        return False
    if m.claimed_by_sibling or m.listed_over_income:
        return False
    return m.relation not in MUST_LIVE_TOGETHER or m.lives_with is True


def _no_consent(q: GapQuestion, c: Ctx) -> list[GapCard]:
    out = []
    for m in c.members:
        if m.relation != "child" and needs_consent(m, c):
            base = F.card(q, m.name, ask=False)
            out.append(
                base.model_copy(
                    update={
                        "question": estimate_question(m.name),
                        "consent_message": consent_message(m.name),
                    }
                )
            )
    return out


def _adult_child(q: GapQuestion, c: Ctx) -> list[GapCard]:
    # 날짜로 정해지는 것이라 묻지 않고 안내만 한다(인쇄 368쪽)
    return [
        F.card(q, m.name, ask=False).model_copy(
            update={"consent_message": consent_message(m.name, adult_child=True)}
        )
        for m in c.members
        if m.relation == "child" and needs_consent(m, c)
    ]


def _dependent_card(q: GapQuestion, c: Ctx) -> list[GapCard]:
    # 동의 카드와 같이 나간다. 형제자매 카드 사용액은 공제되지 않아 뺀다(인쇄 42·134쪽)
    return [
        F.card(q, m.name, ask=False)
        for m in c.members
        if needs_consent(m, c) and m.relation != "sibling"
    ]


def _payer(q: GapQuestion, c: Ctx) -> list[GapCard]:
    if c.household is None or c.rules is None or c.answered(q.id):
        return []
    rules = c.rules
    household = c.household
    return [F.card(q, m.name) for m in household.members if payer_matters(household, m.name, rules)]


DETECTORS: dict[str, Detector] = {
    "gap.parent_living_apart": lambda q, c: _once(q, c),
    "gap.adult_no_consent": _no_consent,
    "gap.child_turned_adult": _adult_child,
    "gap.parent_claimed_by_sibling": lambda q, c: [
        F.card(q, m.name)
        for m in c.members
        if m.relation == "parent" and m.claimed_by_sibling is None
    ],
    "gap.severe_illness": lambda q, c: _once(q, c, c.after_family()),
    "gap.over_income_family": lambda q, c: _per(q, c, lambda m: m.listed_over_income),
    "gap.died_this_year": lambda q, c: _once(q, c, c.after_family()),
    "gap.other_household_family": lambda q, c: _once(q, c),
    "gap.infertility": lambda q, c: _once(q, c, c.docs.has_medical()),
    "gap.glasses": lambda q, c: _once(q, c, not c.docs.has_kind("medical", ("안경", "렌즈"))),
    "gap.school_uniform": lambda q, c: _per(
        q,
        c,
        lambda m: (
            F.in_middle_or_high(m, c.year) and not c.docs.has_kind("education", ("교복",), m.name)
        ),
    ),
    "gap.field_trip": lambda q, c: _per(
        q,
        c,
        lambda m: F.in_school(m, c.year) and not c.docs.has_kind("education", ("체험",), m.name),
    ),
    # TODO(사람 확인): docs/assumptions.md A-058
    "gap.preschool_academy": lambda q, c: _per(q, c, lambda m: F.is_preschool(m, c.year)),
    "gap.overseas_education": lambda q, c: _once(
        q, c, any(m.relation == "child" for m in c.members)
    ),
    "gap.payer_of_medical_education": _payer,
    "gap.dependent_card_usage": _dependent_card,
    "gap.missing_clinic": lambda q, c: _once(q, c, c.docs.has_medical()),
    "gap.insurance_reimbursement": lambda q, c: _once(
        q, c, c.docs.has_medical() and not c.docs.has_kind("medical", ("실손", "보험금"))
    ),
    "gap.medical_device_special_ed": lambda q, c: _per(q, c, lambda m: m.disabled_or_severe),
    "gap.birth_order": lambda q, c: _per(
        q, c, lambda m: F.born_this_year(m, c.year) and m.birth_order is None
    ),
    "gap.job_change": lambda q, c: _once(q, c),
}


def find_gaps(
    family: FamilyAnswer,
    documents: Iterable[ExtractedDoc | dict[str, Any]] = (),
    *,
    household: Household | None = None,
    rules: dict[str, Rule] | None = None,
    year: int = F.YEAR,
) -> list[GapCard]:
    """알림 카드 목록(질문 표 번호 순서). 표에 있는데 조건 함수가 없으면 오류로 알린다."""
    table = load_questions(year)
    missing = set(table) - set(DETECTORS)
    if missing:
        raise KeyError(f"조건 함수가 없는 질문: {sorted(missing)}")
    ctx = Ctx(family, view(documents), household, rules, year)
    cards: list[GapCard] = []
    for q in sorted(table.values(), key=lambda q: q.no):
        cards += DETECTORS[q.id](q, ctx)
    return cards
