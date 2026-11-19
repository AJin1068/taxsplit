"""인적공제: 기본공제 요건 판정과 추가공제(경로우대·장애인·부녀자·한부모).

이 엔진은 "이 근로자가 이 부양가족을 공제받는다"는 입력을 그대로 믿는다.
부부 사이 중복 검사와 배분은 PR 6에서 한다.
"""

from datetime import date, timedelta

from taxsplit.engine.models import Dependent, DependentResult, PersonalDeduction, WorkerInput
from taxsplit.engine.rulebook import Rulebook, RuleValueError

BASIC = "dependent.basic"
JUDGMENT = "dependent.judgment_date"
ELDERLY = "dependent.additional.elderly"
DISABLED = "dependent.additional.disabled"
WOMAN = "dependent.additional.woman"
SINGLE_PARENT = "dependent.additional.single_parent"
CLAIMANT = "dependent.additional.claimant"

STAGE = "personal_deduction"


def judgment_date(dep: Dependent, book: Rulebook, stage: str = STAGE) -> date:
    """공제대상 판정일: 12/31, 사망한 사람은 사망일 전날(소법 §53, p99~p100)."""
    v = book.value(JUDGMENT, stage)
    if v["deceased_or_cured"] != "day_before":
        raise RuleValueError(f"{book.full_id(JUDGMENT)}: 모르는 값 {v['deceased_or_cured']!r}")
    if dep.death_date is not None:
        return dep.death_date - timedelta(days=1)
    month, day = (int(x) for x in v["month_day"].split("-"))
    return date(book.year, month, day)


def age_in_year(birth_year: int, book: Rulebook, stage: str = STAGE) -> int:
    """나이요건은 연중 하루라도 해당하면 인정(p99). 귀속연도 − 출생연도로 본다."""
    v = book.value(JUDGMENT, stage)
    if v["age"] != "any_day_in_year":
        raise RuleValueError(f"{book.full_id(JUDGMENT)}: 모르는 age 방식 {v['age']!r}")
    return book.year - birth_year


def dependent_named(worker: WorkerInput, name: str) -> Dependent:
    """지출 대상 이름으로 부양가족을 찾는다. 의료비·교육비는 기본공제 요건과 따로 본다."""
    for dep in worker.dependents:
        if dep.name == name:
            return dep
    raise ValueError(f"부양가족 목록에 없는 지출 대상: {name!r}")


def income_within_limit(dep: Dependent, book: Rulebook, stage: str = STAGE) -> bool:
    """소득요건: 연 소득금액 100만원 이하, 근로소득만 있으면 총급여 500만원 이하(p95)."""
    v = book.value(BASIC, stage)
    if dep.wage_only_gross is not None:
        return dep.wage_only_gross <= v["wage_only_gross_limit"]
    return dep.income_amount <= v["income_limit"]


def is_spouse_with_income(dep: Dependent, book: Rulebook, stage: str = STAGE) -> bool:
    """소득이 있는 배우자 = 기본공제 소득요건을 넘는 배우자(p389 부록 4, p180)."""
    return dep.relation == "spouse" and not income_within_limit(dep, book, stage)


def _age_ok(dep: Dependent, age: int, v: dict) -> bool:
    # 나이요건(PDF 8쪽, p96). 장애인은 나이 제한 없음
    if dep.disabled and v["disabled_no_age_limit"]:
        return True
    match dep.relation:
        case "spouse":
            return True
        case "child":
            return age <= v["lineal_descendant_max_age"]
        case "lineal_ascendant":
            return age >= v["lineal_ascendant_min_age"]
        case "sibling":
            return age <= v["sibling_max_age"] or age >= v["sibling_min_age"]


def basic_eligibility(dep: Dependent, book: Rulebook, stage: str = STAGE) -> tuple[bool, str]:
    """기본공제 요건(관계·나이·소득)을 판정일 기준으로 본다. (가능 여부, 이유)."""
    v = book.value(BASIC, stage)
    when = judgment_date(dep, book, stage)
    if dep.relation_start is not None and dep.relation_start > when:
        return False, f"판정일({when})에 아직 관계가 없음"
    if not income_within_limit(dep, book, stage):
        return False, "소득요건 초과"
    if not _age_ok(dep, age_in_year(dep.birth_year, book, stage), v):
        return False, "나이요건 미충족"
    return True, "기본공제 대상"


def personal_deduction(
    worker: WorkerInput, comprehensive_income: int, book: Rulebook
) -> PersonalDeduction:
    """기본공제 + 추가공제. comprehensive_income은 부녀자공제 소득요건에 쓴다."""
    basic = book.value(BASIC, STAGE)
    elderly = book.value(ELDERLY, STAGE)
    disabled = book.value(DISABLED, STAGE)
    # 추가공제는 그 부양가족을 기본공제 받은 근로자가 받는다(p389)
    if book.value(CLAIMANT, STAGE)["eligible_claimant"] != "basic_deduction_claimant":
        raise RuleValueError(f"{book.full_id(CLAIMANT)}: 모르는 eligible_claimant")

    me = worker.person
    rows: list[DependentResult] = []
    for dep in worker.dependents:
        ok, reason = basic_eligibility(dep, book)
        age = age_in_year(dep.birth_year, book)
        rows.append(
            DependentResult(
                name=dep.name,
                eligible=ok,
                reason=reason,
                basic=basic["amount"] if ok else 0,
                elderly=elderly["amount"] if ok and age >= elderly["min_age"] else 0,
                disabled=disabled["amount"] if ok and dep.disabled else 0,
            )
        )
    eligible = [r for r in rows if r.eligible]
    # 본인도 경로우대·장애인 추가공제 대상이 될 수 있다
    self_elderly = age_in_year(me.birth_year, book) >= elderly["min_age"]
    elderly_count = sum(r.elderly > 0 for r in rows) + self_elderly
    disabled_count = sum(r.disabled > 0 for r in rows) + me.disabled

    woman = _woman(worker, comprehensive_income, bool(eligible), book)
    single_parent = _single_parent(worker, rows, book)
    if single_parent and book.value(SINGLE_PARENT, STAGE)["excludes"] == book.full_id(WOMAN):
        woman = 0  # 한부모공제와 겹치면 한부모 우선(p99)

    basic_count = 1 + len(eligible)
    basic_total = basic["amount"] * basic_count
    add_elderly = elderly["amount"] * elderly_count
    add_disabled = disabled["amount"] * disabled_count
    return PersonalDeduction(
        basic_count=basic_count,
        basic_self=basic["amount"],
        basic_dependents=basic["amount"] * len(eligible),
        basic_total=basic_total,
        elderly_count=elderly_count,
        elderly=add_elderly,
        disabled_count=disabled_count,
        disabled=add_disabled,
        woman=woman,
        single_parent=single_parent,
        total=basic_total + add_elderly + add_disabled + woman + single_parent,
        dependents=tuple(rows),
    )


def _woman(worker: WorkerInput, income: int, has_dependent: bool, book: Rulebook) -> int:
    """부녀자공제: 종합소득금액 3천만원 이하 여성 + 조건 중 하나(PDF 8쪽, p99 ①②)."""
    v = book.value(WOMAN, STAGE)
    me = worker.person
    conditions = {
        "has_spouse": me.has_spouse,
        "single_head_of_household_with_dependent": (
            not me.has_spouse and me.head_of_household and has_dependent
        ),
    }
    unknown = set(v["requires_any"]) - set(conditions)
    if unknown:
        raise RuleValueError(f"{book.full_id(WOMAN)}: 모르는 조건 {sorted(unknown)}")
    met = any(conditions[name] for name in v["requires_any"])
    if me.sex == "female" and income <= v["income_limit"] and met:
        return v["amount"]
    return 0


def _single_parent(worker: WorkerInput, rows: list[DependentResult], book: Rulebook) -> int:
    """한부모공제: 배우자 없이 기본공제대상 자녀(입양자 포함)가 있는 근로자(소법 §51 ①6호, p97)."""
    v = book.value(SINGLE_PARENT, STAGE)
    eligible_child = any(
        r.eligible and dep.relation == "child"
        for r, dep in zip(rows, worker.dependents, strict=True)
    )
    return v["amount"] if not worker.person.has_spouse and eligible_child else 0
