"""부부 누구도 기본공제 받지 않는 가족(나이·소득요건 미달)의 지출을 누가 공제하나.

Issue #15 정해진 결정(2026-11-19), PR 6 [기획 확인] 1번·덧붙임. 이런 가족의 지출을 버리지 않는다.
- 의료비: 낸 사람이 공제. 나이·소득 제한 없음(2025.medical.no_claimant_payer, p173).
- 교육비: 낸 사람이 공제. 나이 제한 없음, 소득요건 있음, 직계존속 제외
  (2025.education.no_claimant_payer, p178·p180·p181).
- 카드: 소득요건 안의 배우자·직계존비속이 쓴 것만(2025.card.no_claimant_family, p134).
  부부 중 누구에게 넣을지는 문서에 없어서, 배분 비교가 두 쪽을 모두 계산해 고른다(compare.py).
"""

from taxsplit.allocation.models import Assignment, Household
from taxsplit.engine import Dependent, Rulebook
from taxsplit.engine.personal import income_within_limit

STAGE = "allocation"
MEDICAL_PAYER = "medical.no_claimant_payer"
EDU_PAYER = "education.no_claimant_payer"
CARD_FAMILY = "card.no_claimant_family"
# 문서가 정하지 않은 해석이라는 표시(결과 설명에 그대로 쓴다)
CARD_NOTE = "문서가 정하지 않은 해석(인쇄 134쪽 '포함할 수 있음')"


def check_rule_values(book: Rulebook) -> None:
    """규칙 값이 이 코드가 아는 모양이 아니면 조용히 틀리지 않고 멈춘다."""
    expect = {
        MEDICAL_PAYER: {"claimant": "payer", "checks_age": False, "checks_income": False},
        EDU_PAYER: {"claimant": "payer", "checks_age": False, "checks_income": True},
        CARD_FAMILY: {"checks_age": False, "checks_income": True},
    }
    for name, want in expect.items():
        got = book.value(name, STAGE)
        for key, value in want.items():
            if got[key] != value:
                msg = f"{book.full_id(name)}: {key}={got[key]!r}, 이 코드는 {value!r}만 앎"
                raise ValueError(msg)


def is_unclaimed(name: str, plan: Assignment) -> bool:
    """배분안에서 이 가족을 기본공제 받는 사람이 없는가(요건이 안 돼 후보가 없는 가족)."""
    return name not in plan


def _relation_and_income_ok(rule: str, dep: Dependent, book: Rulebook) -> bool:
    v = book.value(rule, STAGE)
    return dep.relation in v["relations"] and income_within_limit(dep, book, STAGE)


def education_allowed(dep: Dependent, book: Rulebook) -> bool:
    """교육비 대상 관계(배우자·직계비속·형제자매)이고 소득요건 안인가."""
    return _relation_and_income_ok(EDU_PAYER, dep, book)


def card_allowed(dep: Dependent, book: Rulebook) -> bool:
    """카드 사용액을 넣을 수 있는 가족인가(배우자·직계존비속, 소득요건 안)."""
    return _relation_and_income_ok(CARD_FAMILY, dep, book)


def unclaimed_card_users(household: Household, plan: Assignment, book: Rulebook) -> list[str]:
    """이 배분안에서 남편·아내 어느 쪽에 넣을지 골라야 하는 카드 사용자(가족 이름, 입력 순서)."""
    out: list[str] = []
    for c in household.cards:
        if c.user in out or c.user in ("husband", "wife") or not is_unclaimed(c.user, plan):
            continue
        if card_allowed(household.member(c.user).dependent, book):
            out.append(c.user)
    return out
