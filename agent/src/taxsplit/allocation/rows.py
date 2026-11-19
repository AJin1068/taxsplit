"""배분 코드가 쓰는 줄 만들기: 엔진 지출 입력 줄, 공제되지 않는 지출 줄(Dropped)."""

from taxsplit.allocation.models import Dropped
from taxsplit.engine import EducationExpense, MedicalExpense, Rulebook

STAGE = "allocation"


def medical_row(s, for_name: str) -> MedicalExpense:
    return MedicalExpense(
        for_name=for_name,
        item=s.item,
        amount=s.amount,
        insurance_special_case=s.insurance_special_case,
    )


def education_row(e, for_name: str) -> EducationExpense:
    return EducationExpense(for_name=for_name, level=e.level, item=e.item, amount=e.amount)


def drop_row(kind, s, rule: str, reason: str, book: Rulebook, amount: int | None = None) -> Dropped:
    book.value(rule, STAGE)  # 근거 규칙을 이 안에서 쓴 규칙으로 적는다
    return Dropped(
        kind=kind,
        for_whom=getattr(s, "for_whom", None) or s.user,
        payer=s.payer,
        amount=s.amount if amount is None else amount,
        rule_id=book.full_id(rule),
        reason=reason,
    )
