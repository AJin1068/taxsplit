"""교육비 세액공제(소법 §59의4 ③, 국세청 신고안내 인쇄 p178~p185).

순서: 공제 안 되는 사람·과정을 뺀다 → 항목별 세부 한도(체험학습·교복)
→ 사람·과정별 한도(취학 전·초중고 300만, 대학 900만, 본인·장애인특수교육비 한도 없음)
→ 합계 × 15%.
"""

from collections import defaultdict
from decimal import Decimal

from taxsplit.engine.models import WorkerInput
from taxsplit.engine.models_items import SELF, ZERO_EDUCATION, EducationCredit, EducationExpense
from taxsplit.engine.personal import dependent_named, is_spouse_with_income
from taxsplit.engine.rulebook import Rulebook, RuleValueError

RATE = "education.rate"
LIMIT = "education.limit"
SUBLIMIT = "education.sublimit"
EXCLUDED = "education.excluded_persons"
GRADUATE = "education.graduate_self_only"
STAGE = "education_credit"

_KNOWN_EXCLUDED = {"spouse_with_income", "lineal_ascendant"}
_SPECIAL_ED = "disabled_special_education"
_SUBLIMIT_KEY = {"field_trip": "field_trip_per_year", "uniform": "uniform_middle_high_per_year"}


def _check_rules(lim: dict, excl: dict, grad: dict, book: Rulebook) -> None:
    if set(excl["excluded"]) != _KNOWN_EXCLUDED:
        raise RuleValueError(f"{book.full_id(EXCLUDED)}: 모르는 제외 대상 {excl['excluded']!r}")
    if excl["lineal_ascendant_exception"] != [_SPECIAL_ED]:
        raise RuleValueError(f"{book.full_id(EXCLUDED)}: 모르는 예외")
    if grad["eligible"] != [SELF]:
        raise RuleValueError(f"{book.full_id(GRADUATE)}: 모르는 eligible {grad['eligible']!r}")
    if not {"self", "disabled_rehab"} <= set(lim["unlimited"]):
        raise RuleValueError(f"{book.full_id(LIMIT)}: unlimited에 self·disabled_rehab 필요")


def _relation(name: str, worker: WorkerInput) -> str:
    return SELF if name == SELF else dependent_named(worker, name).relation


def _is_excluded(e: EducationExpense, worker: WorkerInput, grad: dict, book: Rulebook) -> bool:
    """공제 안 되는 교육비: 소득이 있는 배우자, 직계존속(장애인특수교육비 예외), 남의 대학원."""
    if e.for_name == SELF:
        return False
    dep = dependent_named(worker, e.for_name)
    if dep.relation == "lineal_ascendant" and e.item != _SPECIAL_ED:
        return True
    if is_spouse_with_income(dep, book, STAGE):
        return True
    return e.level in grad["levels"]


def education_credit(worker: WorkerInput, book: Rulebook) -> EducationCredit:
    """교육비 세액공제액과 대상자 관계별 대상금액."""
    if not worker.education:
        return ZERO_EDUCATION
    lim = book.value(LIMIT, STAGE)
    excl = book.value(EXCLUDED, STAGE)
    grad = book.value(GRADUATE, STAGE)
    _check_rules(lim, excl, grad, book)
    kept = [e for e in worker.education if not _is_excluded(e, worker, grad, book)]

    # 1) 세부 한도: 체험학습·교복은 1인당 연 한도
    sub = None
    if any(e.item in _SUBLIMIT_KEY for e in kept):
        sub = book.value(SUBLIMIT, STAGE)
    sub_left: dict[tuple[str, str], int] = {}
    # 2) 사람·과정별로 모은다. 장애인특수교육비는 한도 없이 따로 더한다
    grouped: dict[tuple[str, str], int] = defaultdict(int)
    unlimited: dict[str, int] = defaultdict(int)
    for e in kept:
        amount = e.amount
        if sub is not None and e.item in _SUBLIMIT_KEY:
            key = (e.for_name, e.item)
            left = sub_left.setdefault(key, sub[_SUBLIMIT_KEY[e.item]])
            amount = min(amount, left)
            sub_left[key] = left - amount
        if e.item == _SPECIAL_ED or e.for_name == SELF:
            unlimited[e.for_name] += amount
        else:
            grouped[(e.for_name, e.level)] += amount

    # 3) 과정별 한도를 걸고 관계별로 더한다
    by_relation: dict[str, int] = defaultdict(int)
    for (name, level), amount in grouped.items():
        by_relation[_relation(name, worker)] += min(amount, lim[level])
    for name, amount in unlimited.items():
        by_relation[_relation(name, worker)] += amount

    base = sum(by_relation.values())
    rate = Decimal(book.value(RATE, STAGE)["rate"])
    known = by_relation[SELF] + by_relation["child"] + by_relation["sibling"]
    return EducationCredit(
        base_self=by_relation[SELF],
        base_children=by_relation["child"],
        base_siblings=by_relation["sibling"],
        base_others=base - known,
        base=base,
        amount=book.floor(base * rate, STAGE),
    )
