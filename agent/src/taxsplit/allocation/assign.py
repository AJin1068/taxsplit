"""배분안 하나를 부부 각자의 엔진 입력(WorkerInput)으로 바꾼다.

규칙(「2025년 원천징수의무자를 위한 연말정산 신고안내」 인쇄 p389, PDF 407쪽 부록 4):
- 추가공제·자녀세액공제는 그 부양가족을 기본공제 받은 쪽이 받는다. 엔진이 그 사람의
  부양가족 목록으로 계산하므로, 기본공제 받은 쪽 목록에만 넣으면 따라간다.
- 부양가족 의료비는 기본공제 받은 쪽이 낸 것만 공제(2025.medical.couple_rule).
- 부양가족 교육비·카드는 기본공제 받은 쪽에 붙는다.
- 소득이 있는 배우자를 위한 의료비는 낸 사람이 공제(2025.medical.spouse_expense),
  교육비는 공제 안 됨(2025.education.excluded_persons).
- 부부 각자의 카드는 결제자가 아니라 쓴 사람 기준(2025.card.user_basis).
"""

from dataclasses import dataclass, field

from taxsplit.allocation.models import (
    WHO,
    Assignment,
    Dropped,
    Household,
    Who,
    other,
)
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
SPOUSE_MEDICAL = "medical.spouse_expense"
EDU_EXCLUDED = "education.excluded_persons"
CARD_USER = "card.user_basis"


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
    household: Household, plan: Assignment, book: Rulebook
) -> tuple[dict[Who, WorkerInput], list[Dropped]]:
    """배분안 → (부부 각자의 엔진 입력, 이 안에서 공제되지 않는 지출)."""
    _check_rule_values(book)
    sides: dict[Who, _Side] = {w: _Side() for w in WHO}
    dropped: list[Dropped] = []
    for name, who in plan.items():
        sides[who].deps.append(household.member(name).dependent)

    for s in household.medical:
        if s.for_whom == s.payer:
            sides[s.payer].medical.append(_medical(s, SELF))
        elif s.for_whom in WHO:
            # 배우자 의료비는 낸 사람이 공제. 엔진이 대상을 찾도록 배우자를 부양가족 줄로 넣는다
            sides[s.payer].medical.append(_medical(s, s.for_whom))
            book.value(SPOUSE_MEDICAL, STAGE)
        elif plan.get(s.for_whom) == s.payer:
            sides[s.payer].medical.append(_medical(s, s.for_whom))
            book.value(COUPLE_RULE, STAGE)
        else:
            # TODO(확인 필요): 아무도 기본공제 받을 수 없는 부양가족(나이요건 미달 부모 등)의
            # 의료비도 공제 0으로 둔다. 규칙표 문구("기본공제 받은 쪽이 지출한 것만")를 따랐다
            dropped.append(_drop("medical", s, COUPLE_RULE, "기본공제 받지 않은 쪽이 냄", book))

    for e in household.education:
        if e.for_whom == e.payer:
            sides[e.payer].education.append(_education(e, SELF))
        elif e.for_whom in WHO:
            dropped.append(_drop("education", e, EDU_EXCLUDED, "소득이 있는 배우자", book))
        elif e.for_whom in plan:
            sides[plan[e.for_whom]].education.append(_education(e, e.for_whom))
        else:
            dropped.append(_drop("education", e, EDU_EXCLUDED, "기본공제 대상 아님", book))

    for c in household.cards:
        amounts = c.model_dump(exclude={"user", "payer"})
        if c.user in WHO:
            sides[c.user].cards.append(CardUsage(user="self", **amounts))
        elif c.user in plan:
            relation = household.member(c.user).dependent.relation
            sides[plan[c.user]].cards.append(CardUsage(user=relation, **amounts))
        else:
            # 카드 공제는 본인과 기본공제대상자가 쓴 금액만 센다(조특법 §126의2, p134)
            amount = sum(amounts.values())
            dropped.append(
                Dropped(
                    kind="card",
                    for_whom=c.user,
                    payer=c.payer,
                    amount=amount,
                    rule_id=book.full_id(CARD_USER),
                    reason="기본공제 대상 아님",
                )
            )
        book.value(CARD_USER, STAGE)

    workers = {w: _worker(household, w, sides[w]) for w in WHO}
    return workers, dropped


def _worker(household: Household, who: Who, side: _Side) -> WorkerInput:
    e = household.earner(who)
    deps = list(side.deps)
    # 배우자 의료비가 있으면 배우자를 부양가족 줄로 넣는다. 소득요건을 넘어 인적공제는 0이다
    if any(m.for_name in WHO for m in side.medical):
        spouse = spouse_as_dependent(household, who)
        deps.append(spouse)
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
        SPOUSE_MEDICAL: ("income_spouse_expense_claimant", "payer"),
        CARD_USER: ("family_card_basis", "user"),
    }
    for name, (key, want) in expect.items():
        got = book.value(name, STAGE)[key]
        if got != want:
            raise ValueError(f"{book.full_id(name)}: {key}={got!r}, 이 코드는 {want!r}만 앎")
    if "spouse_with_income" not in book.value(EDU_EXCLUDED, STAGE)["excluded"]:
        raise ValueError(f"{book.full_id(EDU_EXCLUDED)}: spouse_with_income이 없음")


def _medical(s, for_name: str) -> MedicalExpense:
    return MedicalExpense(
        for_name=for_name,
        item=s.item,
        amount=s.amount,
        insurance_special_case=s.insurance_special_case,
    )


def _education(e, for_name: str) -> EducationExpense:
    return EducationExpense(for_name=for_name, level=e.level, item=e.item, amount=e.amount)


def _drop(kind, s, rule: str, reason: str, book: Rulebook) -> Dropped:
    book.value(rule, STAGE)
    return Dropped(
        kind=kind,
        for_whom=s.for_whom,
        payer=s.payer,
        amount=s.amount,
        rule_id=book.full_id(rule),
        reason=reason,
    )
