"""의료비 세액공제(소법 §59의4 ②, 국세청 신고안내 인쇄 p173~p177).

의료비를 네 묶음으로 나눈다.
  ㉠ infertility          난임시술비 (30%)
  ㉡ premature_congenital 미숙아·선천성이상아 (20%)
  ㉢ special              본인·65세 이상·6세 이하·장애인·산정특례자 (15%, 한도 없음)
  ㉣ others              그 외 부양가족 (15%, 연 700만원 한도)
총급여 3% 문턱은 규칙 순서(㉣ → ㉢ → ㉡ → ㉠)대로 뺀다(p173 표 "가~라").
"""

from collections import defaultdict
from decimal import Decimal

from taxsplit.engine.models import WorkerInput
from taxsplit.engine.models_items import SELF, ZERO_MEDICAL, MedicalCredit, MedicalExpense
from taxsplit.engine.personal import age_in_year, dependent_named
from taxsplit.engine.rulebook import Rulebook, RuleValueError

THRESHOLD = "medical.threshold"
ORDER = "medical.threshold_order"
RATE = "medical.rate"
LIMIT = "medical.limit.others"
SUBLIMIT = "medical.sublimit"
STAGE = "medical_credit"

BUCKETS = ("others", "special", "premature_congenital", "infertility")
# 엔진이 "한도 없음"으로 다루는 대상. 규칙표 unlimited에 모두 있어야 한다
_UNLIMITED_NEEDED = {
    "self",
    "age_65_plus",
    "age_6_or_under",
    "disabled",
    "premature_congenital",
    "health_insurance_special_case",
    "infertility",
}


def _bucket(e: MedicalExpense, worker: WorkerInput, lim: dict, book: Rulebook) -> str:
    """지출 한 줄이 ㉠~㉣ 중 어디에 들어가는지 정한다."""
    if e.item in ("infertility", "premature_congenital"):
        return e.item
    if e.for_name == SELF or e.insurance_special_case:
        return "special"
    dep = dependent_named(worker, e.for_name)
    age = age_in_year(dep.birth_year, book, STAGE)
    if dep.disabled or age >= lim["age_65_plus_min_age"] or age <= lim["age_6_or_under_max_age"]:
        return "special"
    return "others"


def _capped_amounts(expenses: tuple[MedicalExpense, ...], book: Rulebook) -> list[int]:
    """세부 한도: 안경은 1인당 연 50만원, 산후조리원은 출산 1회(한 줄)당 200만원."""
    if not any(e.item in ("glasses", "postnatal_care") for e in expenses):
        return [e.amount for e in expenses]
    sub = book.value(SUBLIMIT, STAGE)
    glasses_left: dict[str, int] = defaultdict(lambda: sub["glasses_per_person"])
    out = []
    for e in expenses:
        amount = e.amount
        if e.item == "glasses":
            amount = min(amount, glasses_left[e.for_name])
            glasses_left[e.for_name] -= amount
        elif e.item == "postnatal_care":
            amount = min(amount, sub["postnatal_care_per_birth"])
        out.append(amount)
    return out


def medical_credit(worker: WorkerInput, book: Rulebook) -> MedicalCredit:
    """의료비 세액공제액과 묶음별 대상금액."""
    if not worker.medical:
        return ZERO_MEDICAL
    lim = book.value(LIMIT, STAGE)
    missing = _UNLIMITED_NEEDED - set(lim["unlimited"])
    if missing:
        raise RuleValueError(f"{book.full_id(LIMIT)}: unlimited에 없음 {sorted(missing)}")
    order = book.value(ORDER, STAGE)["order"]
    if sorted(order) != sorted(BUCKETS):
        raise RuleValueError(f"{book.full_id(ORDER)}: 모르는 순서 {order!r}")

    # 1) 묶음별 합계(세부 한도 적용 뒤)
    raw = dict.fromkeys(BUCKETS, 0)
    for e, amount in zip(worker.medical, _capped_amounts(worker.medical, book), strict=True):
        raw[_bucket(e, worker, lim, book)] += amount

    # 2) 총급여 3% 문턱을 규칙 순서대로 뺀다
    rate = Decimal(book.value(THRESHOLD, STAGE)["gross_rate"])
    threshold = book.floor(worker.gross_salary * rate, STAGE)
    left = threshold
    base = {}
    for name in order:
        taken = min(left, raw[name])
        base[name] = raw[name] - taken
        left -= taken
    # 3) 그 외 부양가족(㉣)만 문턱을 뺀 뒤 700만원 한도
    base["others"] = min(base["others"], lim["limit"])

    # 4) 공제액 = (㉢+㉣)×15% + ㉡×20% + ㉠×30%
    r = book.value(RATE, STAGE)
    credit = (
        (base["others"] + base["special"]) * Decimal(r["general"])
        + base["premature_congenital"] * Decimal(r["premature_congenital"])
        + base["infertility"] * Decimal(r["infertility"])
    )
    return MedicalCredit(
        threshold=threshold,
        base_others=base["others"],
        base_special=base["special"],
        base_premature=base["premature_congenital"],
        base_infertility=base["infertility"],
        base=sum(base.values()),
        amount=book.floor(credit, STAGE),
    )
