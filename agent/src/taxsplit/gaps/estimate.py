"""놓칠 금액: 새 계산을 만들지 않고 기존 배분 비교(allocation/compare.py)를 두 번 부른다.

고른 금액을 그 가족 의료비로 넣은 가구와 안 넣은 가구의 최적안 합계(부부 결정세액 합)를 뺀다.
기납부세액은 같아서 이 차이가 곧 부부 합산 환급 차이다. 금액은 엔진 출력 그대로(ADR-0003).
"""

from taxsplit.allocation.compare import compare_allocations
from taxsplit.allocation.models import Household, MedicalSpend, Who
from taxsplit.gaps.models import Estimate, Option, Question
from taxsplit.rules.loader import Rule

# 세 칸 금액은 세법 숫자도 통계도 아니고 사용자가 고르는 입력 예시다
# TODO(사람 확인): docs/assumptions.md A-061
ESTIMATE_OPTIONS = (
    Option(label="거의 안 다니심 · 연 30만 원쯤", amount=300_000),
    Option(label="보통 · 연 100만 원쯤", amount=1_000_000),
    Option(label="자주 · 연 300만 원쯤", amount=3_000_000),
)
OPTION_AMOUNTS = frozenset(o.amount for o in ESTIMATE_OPTIONS if o.amount is not None)
LABEL = "고르신 금액으로 계산한 예상"
NO_DIFFERENCE = "지금 자료로는 공제 차이가 없어요."


def estimate_question(person: str) -> Question:
    return Question(text=f"{person}께서 병원 자주 다니셨나요?", options=ESTIMATE_OPTIONS)


def default_payer(household: Household, person: str) -> Who:
    """낸 사람을 모르면 그 가족 쪽 배우자, 부부 공동 가족(자녀)이면 남편(입력의 첫 사람).

    TODO(사람 확인): docs/assumptions.md A-063
    """
    return household.member(person).family_of or "husband"


def with_medical(household: Household, person: str, amount: int, payer: Who) -> Household:
    """가구 사본에 그 가족 의료비 한 줄을 더한다."""
    row = MedicalSpend(payer=payer, for_whom=person, amount=amount)
    return household.model_copy(update={"medical": (*household.medical, row)})


def best_total(household: Household, rules: dict[str, Rule]) -> int:
    return compare_allocations(household, rules).best.total


def estimate_missing(
    household: Household,
    person: str,
    amount: int,
    rules: dict[str, Rule],
    payer: Who | None = None,
) -> Estimate:
    """안 넣었을 때 합계 − 넣었을 때 합계. 0원이면 금액 대신 "차이 없음"."""
    who = payer or default_payer(household, person)
    without = best_total(household, rules)
    with_ = best_total(with_medical(household, person, amount, who), rules)
    saving = without - with_
    if saving <= 0:
        # 더 쓰라는 말은 하지 않는다(Issue #126 하지 않을 것)
        return Estimate(
            label=LABEL,
            chosen_amount=amount,
            payer=who,
            saving=None,
            no_difference=True,
            message=NO_DIFFERENCE,
        )
    return Estimate(
        label=LABEL,
        chosen_amount=amount,
        payer=who,
        saving=saving,
        no_difference=False,
        message=f"{LABEL}: 이 병원비를 넣으면 부부 합산 {saving:,}원을 더 돌려받아요.",
    )


def payer_matters(household: Household, person: str, rules: dict[str, Rule]) -> bool:
    """그 가족 의료비·교육비를 낸 사람을 바꾸면 최적안 합계가 달라지나(계산 엔진으로 확인).

    의료비가 문턱보다 훨씬 적어 누가 냈든 결과가 같으면 False라 묻지 않는다(#109 원칙).
    """
    rows = [s for s in (*household.medical, *household.education) if s.for_whom == person]
    if not rows:
        return False
    flip = {"husband": "wife", "wife": "husband"}

    def flipped(spends):
        return tuple(
            s.model_copy(update={"payer": flip[s.payer]}) if s.for_whom == person else s
            for s in spends
        )

    other = household.model_copy(
        update={"medical": flipped(household.medical), "education": flipped(household.education)}
    )
    return best_total(household, rules) != best_total(other, rules)
