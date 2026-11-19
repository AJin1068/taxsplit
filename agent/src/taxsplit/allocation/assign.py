"""배분안 하나를 부부 각자의 엔진 입력(WorkerInput)으로 바꾼다.

규칙(「2025년 원천징수의무자를 위한 연말정산 신고안내」 인쇄 p389, PDF 407쪽 부록 4):
- 추가공제·자녀세액공제는 그 부양가족을 기본공제 받은 쪽이 받는다. 엔진이 그 사람의
  부양가족 목록으로 계산하므로, 기본공제 받은 쪽 목록에만 넣으면 따라간다.
- 부양가족 의료비·교육비는 기본공제 받은 쪽이 낸 것만 공제
  (2025.medical.couple_rule, 2025.education.couple_rule). 다른 쪽이 낸 것은 공제 안 됨.
- 아무도 기본공제 받지 않는 가족의 지출은 unclaimed.py(낸 사람, 카드는 고른 쪽).
- 소득이 있는 배우자를 위한 의료비는 낸 사람이 공제(2025.medical.spouse_expense),
  교육비는 공제 안 됨(2025.education.excluded_persons).
- 부양가족 카드는 기본공제 받은 쪽. 부부 각자의 카드는 쓴 사람 기준(2025.card.user_basis).
"""

from dataclasses import dataclass, field

from taxsplit.allocation import unclaimed as un
from taxsplit.allocation.models import WHO, Assignment, Dropped, Household, Who, other
from taxsplit.allocation.rows import drop_row, education_row, medical_row
from taxsplit.engine import (
    CardUsage,
    Dependent,
    EducationExpense,
    MedicalExpense,
    Rulebook,
    SelfInfo,
    WorkerInput,
    is_spouse_with_income,
)
from taxsplit.engine.models_items import SELF

STAGE = "allocation"
COUPLE_RULE = "medical.couple_rule"
EDU_COUPLE = "education.couple_rule"
SPOUSE_MEDICAL = "medical.spouse_expense"
EDU_EXCLUDED = "education.excluded_persons"
CARD_USER = "card.user_basis"
NOT_CLAIMANT = "기본공제 받지 않은 쪽이 냄"


@dataclass
class _Side:
    """한 사람 몫으로 모으는 엔진 입력 조각."""

    deps: list[Dependent] = field(default_factory=list)
    medical: list[MedicalExpense] = field(default_factory=list)
    education: list[EducationExpense] = field(default_factory=list)
    cards: list[CardUsage] = field(default_factory=list)


def spouse_as_dependent(household: Household, who: Who) -> Dependent:
    """who의 배우자를 엔진의 부양가족 모양으로. 근로소득만 있어 총급여로 소득요건을 본다."""
    e = household.earner(other(who))
    return Dependent(
        name=other(who),
        relation="spouse",
        birth_year=e.birth_year,
        wage_only_gross=e.gross_salary,
        disabled=e.disabled,
    )


def to_workers(
    household: Household,
    plan: Assignment,
    book: Rulebook,
    card_sides: dict[str, Who] | None = None,
) -> tuple[dict[Who, WorkerInput], list[Dropped]]:
    """배분안 → (부부 각자의 엔진 입력, 이 안에서 공제되지 않는 지출).

    card_sides = 아무도 기본공제 받지 않는 가족의 카드를 넣을 쪽(un.unclaimed_card_users 전부).
    """
    _check_rule_values(book)
    card_sides = card_sides or {}
    sides: dict[Who, _Side] = {w: _Side() for w in WHO}
    dropped: list[Dropped] = []
    for name, who in plan.items():
        sides[who].deps.append(household.member(name).dependent)

    for s in household.medical:
        if s.for_whom == s.payer:
            sides[s.payer].medical.append(medical_row(s, SELF))
        elif s.for_whom in WHO:
            # 배우자 의료비는 낸 사람이 공제. 엔진이 대상을 찾도록 배우자를 부양가족 줄로 넣는다
            sides[s.payer].medical.append(medical_row(s, s.for_whom))
            book.value(SPOUSE_MEDICAL, STAGE)
        elif un.is_unclaimed(s.for_whom, plan):
            # 아무도 기본공제 받지 않는 가족: 낸 사람이 공제(나이·소득 제한 없음)
            sides[s.payer].medical.append(medical_row(s, s.for_whom))
            book.value(un.MEDICAL_PAYER, STAGE)
        elif plan[s.for_whom] == s.payer:
            sides[s.payer].medical.append(medical_row(s, s.for_whom))
            book.value(COUPLE_RULE, STAGE)
        else:
            dropped.append(drop_row("medical", s, COUPLE_RULE, NOT_CLAIMANT, book))

    for e in household.education:
        if e.for_whom == e.payer:
            sides[e.payer].education.append(education_row(e, SELF))
        elif e.for_whom in WHO:
            dropped.append(drop_row("education", e, EDU_EXCLUDED, "소득이 있는 배우자", book))
        elif un.is_unclaimed(e.for_whom, plan):
            if un.education_allowed(household.member(e.for_whom).dependent, book):
                sides[e.payer].education.append(education_row(e, e.for_whom))
            else:
                reason = "교육비 대상 관계·소득요건 아님"
                dropped.append(drop_row("education", e, un.EDU_PAYER, reason, book))
        elif plan[e.for_whom] == e.payer:
            sides[e.payer].education.append(education_row(e, e.for_whom))
            book.value(EDU_COUPLE, STAGE)
        else:
            dropped.append(drop_row("education", e, EDU_COUPLE, NOT_CLAIMANT, book))

    for c in household.cards:
        amounts = c.model_dump(exclude={"user", "payer"})
        if c.user in WHO:
            sides[c.user].cards.append(CardUsage(user="self", **amounts))
        elif c.user in plan or c.user in card_sides:
            relation = household.member(c.user).dependent.relation
            side = plan.get(c.user) or card_sides[c.user]
            sides[side].cards.append(CardUsage(user=relation, **amounts))
            if c.user in card_sides:
                book.value(un.CARD_FAMILY, STAGE)
        else:
            # 형제자매, 소득요건을 넘는 가족이 쓴 카드는 넣지 않는다(조특법 §126의2, p134)
            relation = household.member(c.user).dependent.relation
            if relation in book.value(CARD_USER, STAGE)["excluded_relations"]:
                rule, reason = CARD_USER, "형제자매 사용분은 제외"
            else:
                rule, reason = un.CARD_FAMILY, "카드 사용액 대상 가족 아님(소득요건 초과)"
            dropped.append(drop_row("card", c, rule, reason, book, sum(amounts.values())))
        book.value(CARD_USER, STAGE)

    workers = {w: _worker(household, w, sides[w]) for w in WHO}
    return workers, dropped


def _worker(household: Household, who: Who, side: _Side) -> WorkerInput:
    e = household.earner(who)
    deps = list(side.deps)
    # 엔진은 지출 대상을 부양가족 목록에서 찾는다. 배우자·아무도 기본공제 받지 않는 가족은
    # 요건이 안 되는 부양가족 줄로 넣는다(인적공제·자녀세액공제는 0)
    targets = [x.for_name for x in (*side.medical, *side.education)]
    for name in dict.fromkeys(targets):
        if name == SELF or any(d.name == name for d in deps):
            continue
        is_spouse = name in WHO
        deps.append(
            spouse_as_dependent(household, who) if is_spouse else household.member(name).dependent
        )
    return WorkerInput(
        gross_salary=e.gross_salary,
        person=SelfInfo(sex=e.sex, birth_year=e.birth_year, has_spouse=True, disabled=e.disabled),
        dependents=tuple(deps),
        national_pension=e.national_pension,
        health_insurance=e.health_insurance,
        employment_insurance=e.employment_insurance,
        long_term_care_insurance=e.long_term_care_insurance,
        medical=tuple(side.medical),
        education=tuple(side.education),
        card_usage=tuple(side.cards),
        out_of_scope=e.out_of_scope,
    )


def spouse_has_income(household: Household, who: Who, book: Rulebook) -> bool:
    """who의 배우자가 소득이 있는 배우자(기본공제 소득요건 초과)인가."""
    return is_spouse_with_income(spouse_as_dependent(household, who), book, STAGE)


def _check_rule_values(book: Rulebook) -> None:
    # 규칙 값이 이 코드가 아는 모양이 아니면 조용히 틀리지 않고 멈춘다
    expect = {
        COUPLE_RULE: ("eligible_payer", "basic_deduction_claimant"),
        EDU_COUPLE: ("eligible_payer", "basic_deduction_claimant"),
        SPOUSE_MEDICAL: ("income_spouse_expense_claimant", "payer"),
        CARD_USER: ("family_card_basis", "user"),
    }
    for name, (key, want) in expect.items():
        got = book.value(name, STAGE)[key]
        if got != want:
            raise ValueError(f"{book.full_id(name)}: {key}={got!r}, 이 코드는 {want!r}만 앎")
    if "spouse_with_income" not in book.value(EDU_EXCLUDED, STAGE)["excluded"]:
        raise ValueError(f"{book.full_id(EDU_EXCLUDED)}: spouse_with_income이 없음")
    un.check_rule_values(book)
