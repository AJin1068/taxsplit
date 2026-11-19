"""세액공제: 근로소득세액공제와 한도, 자녀세액공제, 표준세액공제."""

from taxsplit.engine.models import ChildCredit, EarnedIncomeCredit, WorkerInput
from taxsplit.engine.money import bracket_amount, segment_limit
from taxsplit.engine.personal import age_in_year, basic_eligibility
from taxsplit.engine.rulebook import Rulebook, RuleValueError

EARNED_CREDIT = "base.earned_income_tax_credit"
EARNED_CREDIT_LIMIT = "base.earned_income_tax_credit.limit"
CHILD_BASE = "child.credit.base"
CHILD_BIRTH = "child.credit.birth"
STANDARD = "base.standard_tax_credit"


def earned_income_tax_credit(
    computed_tax: int, gross_salary: int, book: Rulebook
) -> EarnedIncomeCredit:
    """근로소득세액공제 = min(산출세액 구간표 값, 총급여 구간별 한도) (소법 §59, p162)."""
    stage = "earned_income_credit"
    rate = book.value(EARNED_CREDIT, stage)
    seg = book.value(EARNED_CREDIT_LIMIT, stage)
    before = book.floor(bracket_amount(computed_tax, rate["brackets"]), stage)
    limit = book.floor(segment_limit(gross_salary, seg["segments"]), stage)
    return EarnedIncomeCredit(before_limit=before, limit=limit, amount=min(before, limit))


def _age8plus_amount(count: int, v: dict) -> int:
    # 1명 25만, 2명 55만, 3명 이상 55만 + 2명 넘는 1명당 40만(소법 §59의2 ①, p164)
    if count <= 0:
        return 0
    if count == 1:
        return v["one"]
    return v["two"] + (count - 2) * v["extra_per_child_over_two"]


def _birth_amount(order: int, v: dict) -> int:
    # 그 해 출산·입양: 첫째 30만, 둘째 50만, 셋째 이상 70만(p164)
    if order == 1:
        return v["first"]
    if order == 2:
        return v["second"]
    return v["third_or_more"]


def child_tax_credit(worker: WorkerInput, book: Rulebook) -> ChildCredit:
    """기본공제 대상인 자녀만 센다. 8세 이상분과 출산·입양분을 따로 낸다."""
    stage = "child_credit"
    base = book.value(CHILD_BASE, stage)
    birth = book.value(CHILD_BIRTH, stage)
    children = [
        d
        for d in worker.dependents
        if d.relation == "child" and basic_eligibility(d, book, stage)[0]
    ]
    age8 = [d for d in children if age_in_year(d.birth_year, book, stage) >= base["min_age"]]
    born = [d for d in children if d.birth_or_adoption_order is not None]
    age8_amount = _age8plus_amount(len(age8), base)
    birth_amount = sum(_birth_amount(d.birth_or_adoption_order or 0, birth) for d in born)
    return ChildCredit(
        age8plus_count=len(age8),
        age8plus=age8_amount,
        birth_count=len(born),
        birth=birth_amount,
        total=age8_amount + birth_amount,
    )


def standard_credit_rule(book: Rulebook) -> tuple[int, frozenset[str]]:
    """표준세액공제 금액과, 받으면 표준세액공제를 못 받는 공제 범주(소법 §59의4 ⑨, p170)."""
    v = book.value(STANDARD, "standard_tax_credit")
    # 부부 각자 따로 고른다. 엔진은 한 사람씩 계산하므로 이 방식만 안다
    if v["per_person_choose_larger"] is not True:
        raise RuleValueError(f"{book.full_id(STANDARD)}: per_person_choose_larger가 true가 아님")
    return v["amount"], frozenset(v["applies_when_none_of"])
