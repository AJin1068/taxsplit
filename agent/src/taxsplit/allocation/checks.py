"""중복공제·공제 안 됨 검사(FR-04).

입력은 "부부가 각자 신청하려는 것"(Claim 목록)이다. 잡는 것은 Issue #15의 다섯 가지뿐이다.
5번(기본공제 받지 않은 쪽이 낸 지출)은 의료비·교육비 둘 다다(Issue #15 정해진 결정 2026-11-19).
정상적으로 나눈 경우(자녀를 하나씩, 각자 카드, 배우자 의료비를 낸 사람이 공제)는 잡지 않는다.
근거: 「2025년 원천징수의무자를 위한 연말정산 신고안내」 인쇄 p389(PDF 407쪽) 부록 4, p100.
"""

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict

from taxsplit.allocation.assign import STAGE, spouse_has_income
from taxsplit.allocation.candidates import candidates
from taxsplit.allocation.models import WHO, AllocWarning, Household, Who, Won, other
from taxsplit.engine import Rulebook
from taxsplit.rules.loader import Rule

DOUBLE_CLAIM = "dependent.double_claim"
BASIC = "dependent.basic"
CLAIMANT = "dependent.additional.claimant"
CHILD_CREDIT = "child.credit.base"
COUPLE_RULE = "medical.couple_rule"
EDU_COUPLE = "education.couple_rule"

ClaimKind = Literal["basic", "child_credit", "additional", "medical", "education", "card"]
_NAMES = {"husband": "남편", "wife": "아내"}


class Claim(BaseModel):
    """한 사람이 연말정산에 넣으려는 것 한 줄. target = "husband" | "wife" | 부양가족 이름."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    who: Who
    kind: ClaimKind
    target: str
    # 의료비·교육비·카드면 금액(같은 지출을 둘 다 넣었는지 볼 때 쓴다)
    amount: Won = 0


def check_claims(
    household: Household, claims: tuple[Claim, ...], rules: dict[str, Rule]
) -> tuple[AllocWarning, ...]:
    book = Rulebook(rules)
    ids = {name: book.full_id(name) for name in (DOUBLE_CLAIM, BASIC, CLAIMANT, CHILD_CREDIT)}
    ids |= {name: book.full_id(name) for name in (COUPLE_RULE, EDU_COUPLE)}
    for name in ids:
        book.value(name, STAGE)  # 규칙표에 없으면 여기서 멈춘다
    basic = {w: {c.target for c in claims if c.who == w and c.kind == "basic"} for w in WHO}
    # 기본공제 받을 수 있는 가족(후보가 있는 가족). 아무도 못 받는 가족의 지출은 낸 사람이 공제
    can_claim = {name for name, who in candidates(household, book).items() if who}
    out: list[AllocWarning] = []

    # 1) 같은 부양가족을 부부가 둘 다 기본공제(소령 §106: 한 사람만)
    for name in sorted(basic["husband"] & basic["wife"] - set(WHO)):
        out.append(_w("double_basic", f"{name}을(를) 부부가 둘 다 기본공제함", ids[DOUBLE_CLAIM]))

    # 2) 맞벌이(소득이 있는) 배우자를 상대가 기본공제
    for who in WHO:
        if other(who) in basic[who] and spouse_has_income(household, who, book):
            msg = f"{_NAMES[who]}이(가) 소득이 있는 배우자를 기본공제함"
            out.append(_w("spouse_basic", msg, ids[BASIC]))

    # 3) 같은 의료비·교육비를 부부가 둘 다 입력.
    #    한계: 입력에 지출 ID·영수증 구분이 없어 (종류, 대상, 금액)이 같으면 같은 지출로 본다.
    #    부부가 같은 자녀에게 우연히 같은 금액을 따로 낸 정상 입력도 경고된다(Issue #15 [검증] 메모)
    spends = Counter(
        (c.kind, c.target, c.amount) for c in set(claims) if c.kind in ("medical", "education")
    )
    for (kind, target, amount), n in sorted(spends.items()):
        if n > 1:
            msg = f"{target}의 {_KIND[kind]} {amount:,}원을 부부가 둘 다 넣음"
            out.append(_w("double_expense", msg, ids[DOUBLE_CLAIM]))

    for c in claims:
        if c.target in WHO or c.target in basic[c.who]:
            continue
        # 4) 자녀세액공제·추가공제는 그 부양가족을 기본공제 받은 쪽만(p389)
        if c.kind in ("child_credit", "additional"):
            rule_ids = (ids[CLAIMANT],)
            if c.kind == "child_credit":
                rule_ids += (ids[CHILD_CREDIT],)
            msg = f"{_NAMES[c.who]}이(가) 기본공제 받지 않은 {c.target}의 {_KIND[c.kind]}을 넣음"
            out.append(AllocWarning(code="credit_without_basic", message=msg, rule_ids=rule_ids))
        # 5) 기본공제 받지 않은 쪽이 낸 부양가족 의료비·교육비는 공제 안 됨(홈택스는 그대로
        #    공제해 버린다). 아무도 기본공제 받을 수 없는 가족이면 낸 사람이 공제하므로 경고 없음
        elif c.kind in ("medical", "education") and c.target in can_claim:
            msg = f"{_NAMES[c.who]}이(가) 낸 {c.target} {_KIND[c.kind]} {c.amount:,}원은 공제 안 됨"
            rule = ids[COUPLE_RULE if c.kind == "medical" else EDU_COUPLE]
            out.append(_w(f"{c.kind}_not_claimant", msg, rule))
    return tuple(out)


def scope_warnings(household: Household, book: Rulebook) -> tuple[AllocWarning, ...]:
    """배우자가 기본공제 소득요건 이하면 맞벌이가 아니라 범위 밖(사람 결정 2026-11-18).

    계산은 하되 배우자 공제는 안에 넣지 않는다([계획] 정할 것 1).
    """
    out = []
    for who in WHO:
        if not spouse_has_income(household, who, book):
            msg = f"{_NAMES[other(who)]} 소득이 기본공제 소득요건 이하: 맞벌이 아님, 범위 밖"
            out.append(_w("not_dual_income", msg, book.full_id(BASIC)))
    return tuple(out)


_KIND = {
    "medical": "의료비",
    "education": "교육비",
    "child_credit": "자녀세액공제",
    "additional": "추가공제",
}


def _w(code: str, message: str, rule_id: str) -> AllocWarning:
    return AllocWarning(code=code, message=message, rule_ids=(rule_id,))
