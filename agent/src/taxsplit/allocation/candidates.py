"""배분안 만들기: 부양가족마다 공제받을 수 있는 쪽을 정하고, 가능한 안을 전부 늘어놓는다.

부양가족 n명이면 최대 2^n개다. v1 가구는 부양가족이 적어 전부 계산한다(Issue #15 "완전 탐색").
흔한 방식 A·B도 여기서 만든다.
"""

from itertools import product

from taxsplit.allocation.models import WHO, Assignment, Household, Who
from taxsplit.engine import Rulebook, basic_eligibility

STAGE = "allocation"
DOUBLE_CLAIM = "dependent.double_claim"


def candidates(household: Household, book: Rulebook) -> dict[str, tuple[Who, ...]]:
    """부양가족 이름 → 기본공제 받을 수 있는 쪽. 요건(관계·나이·소득)이 안 되면 빈 튜플.

    기본공제 요건은 공제받는 사람과 상관없이 같아서, 되면 부부 둘 다 후보다.
    """
    # 한 부양가족은 한 사람만 공제받는다(소령 §106, p100). 값이 1이 아니면 이 방식이 틀린다
    if book.value(DOUBLE_CLAIM, STAGE)["max_claimants"] != 1:
        raise ValueError(f"{book.full_id(DOUBLE_CLAIM)}: max_claimants가 1이 아님")
    out: dict[str, tuple[Who, ...]] = {}
    for m in household.members:
        ok, _ = basic_eligibility(m.dependent, book, STAGE)
        out[m.name] = WHO if ok else ()
    return out


def all_assignments(cands: dict[str, tuple[Who, ...]]) -> list[Assignment]:
    """후보가 있는 부양가족마다 남편·아내를 골라 만든 모든 안. 부양가족이 없으면 빈 안 1개."""
    names = [n for n, who in cands.items() if who]
    return [dict(zip(names, pick, strict=True)) for pick in product(*(cands[n] for n in names))]


def larger_earner(household: Household, taxable: dict[Who, int]) -> tuple[Who, bool]:
    """총급여가 큰 쪽. 같으면 과세표준이 큰 쪽, 그것도 같으면 남편(입력의 첫 사람).

    taxable = 부양가족 없이 계산한 각자의 과세표준(사람 결정 2026-11-18, [계획] 정할 것 2).
    두 번째 값은 "총급여 같음" 표시다.
    """
    h, w = household.husband.gross_salary, household.wife.gross_salary
    if h != w:
        return ("husband" if h > w else "wife"), False
    return ("wife" if taxable["wife"] > taxable["husband"] else "husband"), True


def _pick(prefer: Who, allowed: tuple[Who, ...]) -> Who:
    # 바라는 쪽이 요건상 안 되면 가능한 쪽으로 둔다
    return prefer if prefer in allowed else allowed[0]


def common_a(cands: dict[str, tuple[Who, ...]], larger: Who) -> Assignment:
    """흔한 방식 A: 부양가족 전부 총급여가 큰 쪽.

    근거: 「2025년 원천징수의무자를 위한 연말정산 신고안내」 인쇄 p389 부록 4
    "일반적인 경우 부부 중 종합소득 과세표준이 많은 쪽이 유리".
    """
    return {n: _pick(larger, who) for n, who in cands.items() if who}


def common_b(household: Household, cands: dict[str, tuple[Who, ...]], larger: Who) -> Assignment:
    """흔한 방식 B: 각자 자기 가족(부모 등)은 자기가, 자녀는 총급여가 큰 쪽."""
    out: Assignment = {}
    for name, who in cands.items():
        if not who:
            continue
        m = household.member(name)
        own = m.family_of if m.dependent.relation != "child" else None
        out[name] = _pick(own or larger, who)
    return out
