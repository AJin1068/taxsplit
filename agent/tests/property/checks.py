"""성질 5개를 근로자 한 명씩 확인한다. 정답 값 없이 "절대 일어나면 안 되는 일"만 본다.

한도·비율은 사례가 아니라 규칙표에서 읽는다. 어긴 것은 시드·남편/아내·성질·단계와 함께
Violation으로 돌려준다. 시드로 make_household(seed)를 부르면 같은 가구가 다시 나온다.
"""

from dataclasses import dataclass

from taxsplit.engine import (
    CardUsage,
    Dependent,
    EducationExpense,
    MedicalExpense,
    Rulebook,
    TaxResult,
    WorkerInput,
    basic_eligibility,
    compute_tax,
)
from taxsplit.synth import SynthHousehold

PROPERTIES = {
    1: "결정세액은 0원 이상",
    2: "의료비·교육비·카드 하나만 늘리면 결정세액이 늘지 않음",
    3: "요건 맞는 부양가족 한 명을 더 공제받으면 결정세액이 늘지 않음",
    4: "단계 사이 관계와 규칙표 한도",
    5: "같은 입력 같은 결과, 규칙 ID는 모두 규칙표에 있음",
}
# 성질 2에서 늘려 보는 크기: 1만원, 100만원
BUMPS = (10_000, 1_000_000)
# 성질 3에서 같은 가구에 맞는 사람이 없을 때 붙여 보는 후보(요건 판정은 엔진이 한다)
EXTRA_CANDIDATES = (
    Dependent(name="추가자녀", relation="child", birth_year=2015),
    Dependent(name="추가부모", relation="lineal_ascendant", birth_year=1950),
)


@dataclass(frozen=True)
class Violation:
    seed: int
    who: str
    prop: int
    stage: str
    detail: str


def _bumped(worker: WorkerInput, kind: str, delta: int) -> WorkerInput:
    """의료비·교육비·카드 중 하나의 첫 줄을 delta만큼 늘린다(줄이 없으면 본인 줄을 더한다)."""
    if kind == "medical":
        lines = list(worker.medical) or [MedicalExpense(amount=0)]
    elif kind == "education":
        lines = list(worker.education) or [EducationExpense(level="university", amount=0)]
    else:
        first = worker.card_usage[0] if worker.card_usage else CardUsage()
        card = first.model_copy(update={"credit": first.credit + delta})
        return worker.model_copy(update={"card_usage": (card, *worker.card_usage[1:])})
    lines[0] = lines[0].model_copy(update={"amount": lines[0].amount + delta})
    return worker.model_copy(update={kind: tuple(lines)})


def check_nonnegative(res: TaxResult) -> list[tuple[str, str]]:
    bad = []
    if res.determined_tax < 0:
        bad.append(("determined_tax", f"결정세액 {res.determined_tax}"))
    if res.other_option_determined_tax < 0:
        bad.append(("other_option", f"다른 쪽 결정세액 {res.other_option_determined_tax}"))
    return bad


def check_spending(worker: WorkerInput, res: TaxResult, rules) -> list[tuple[str, str]]:
    bad = []
    for kind in ("medical", "education", "card"):
        for delta in BUMPS:
            after = compute_tax(_bumped(worker, kind, delta), rules).determined_tax
            if after > res.determined_tax:
                bad.append((kind, f"+{delta:,}원: {res.determined_tax:,} → {after:,}"))
    return bad


def check_dependent(hh: SynthHousehold, who: str, res: TaxResult, rules) -> list[tuple[str, str]]:
    """다른 배우자가 공제받던 사람 또는 후보 중 요건 맞는 첫 사람을 이 근로자에게 더한다."""
    worker = hh.worker(who)
    book = Rulebook(rules)
    others = [d for d, c in zip(hh.dependents, hh.claimants, strict=True) if c != who]
    for dep in (*others, *EXTRA_CANDIDATES):
        if basic_eligibility(dep, book)[0]:
            added = worker.model_copy(update={"dependents": (*worker.dependents, dep)})
            after = compute_tax(added, rules).determined_tax
            if after > res.determined_tax:
                return [("personal_deduction", f"{dep.name}: {res.determined_tax:,} → {after:,}")]
            return []
    return [("personal_deduction", "요건 맞는 후보가 없음")]


def check_stages(worker: WorkerInput, res: TaxResult, rules) -> list[tuple[str, str]]:
    """근로소득금액·결정세액 식, 공제액 ≤ 규칙표 한도."""
    v = {k.split(".", 1)[1]: r.value for k, r in rules.items()}  # 연도를 뗀 이름
    gross = worker.gross_salary
    card_split = v["card.limit"]["gross_split"]
    card_cap = (
        v["card.limit"]["at_or_below"] + v["card.additional_limit"]["at_or_below"]
        if gross <= card_split
        else v["card.limit"]["above"] + v["card.additional_limit"]["above"]
    )
    edu = v["education.limit"]
    edu_names = {e.for_name for e in worker.education if e.for_name != "self"}
    edu_cap = len(edu_names) * max(edu["preschool"], edu["school"], edu["university"])
    combined = v["base.combined_deduction_limit"]["limit"]
    checks = [
        ("earned_income_amount", res.earned_income_amount == gross - res.earned_income_deduction),
        ("determined_tax", res.determined_tax == max(0, res.computed_tax - res.tax_credit_total)),
        (
            "earned_income_deduction",
            res.earned_income_deduction <= v["base.earned_income_deduction"]["limit"],
        ),
        ("earned_income_deduction", res.earned_income_deduction <= gross),
        ("earned_income_credit", res.earned_income_credit.amount <= res.earned_income_credit.limit),
        ("card_deduction", res.card.amount <= res.card.limit <= card_cap),
        ("medical", res.medical.base_others <= v["medical.limit.others"]["limit"]),
        ("education", res.education.base - res.education.base_self <= edu_cap),
        (
            "combined_limit",
            res.combined_limit_excess == max(0, res.combined_limit_target - combined),
        ),
        ("taxable_income", res.taxable_income >= 0),
    ]
    return [(stage, "식 또는 한도 어긋남") for stage, ok in checks if not ok]


def check_repeatable(worker: WorkerInput, res: TaxResult, rules) -> list[tuple[str, str]]:
    bad = []
    if compute_tax(worker, rules) != res:
        bad.append(("compute_tax", "같은 입력인데 결과가 다름"))
    used = {rid for ids in res.rules_used.values() for rid in ids} | set(res.needs_check)
    unknown = used - set(rules)
    if unknown:
        bad.append(("rules_used", f"규칙표에 없는 ID {sorted(unknown)}"))
    return bad


def check_household(hh: SynthHousehold, rules) -> list[Violation]:
    """가구 하나의 부부 각자에게 성질 5개를 확인한다."""
    out = []
    for who in ("husband", "wife"):
        worker = hh.worker(who)
        res = compute_tax(worker, rules)
        found = {
            1: check_nonnegative(res),
            2: check_spending(worker, res, rules),
            3: check_dependent(hh, who, res, rules),
            4: check_stages(worker, res, rules),
            5: check_repeatable(worker, res, rules),
        }
        for prop, items in found.items():
            out += [Violation(hh.seed, who, prop, stage, detail) for stage, detail in items]
    return out
