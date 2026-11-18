"""엔진이 규칙표를 읽는 단 하나의 창구.

- 규칙을 꺼낼 때마다 "어느 단계에서 어떤 규칙 ID를 썼는지" 적는다(결과의 rules_used).
- todo 규칙(출처 확인 전)을 여기서 한 번에 처리한다.
  - 값이 있는 todo: 값을 쓰고 "확인 필요"(needs_check)에 규칙 ID를 넣는다.
  - 값이 빈 todo: 꺼내는 순간 RuleNotReadyError. 빈 값을 "처리 없음"으로 읽으면
    틀린 금액이 조용히 결과로 나가기 때문이다(Issue #13 정해진 결정).
"""

from decimal import ROUND_FLOOR, Decimal
from typing import Any

from taxsplit.rules.loader import Rule

# 엔진이 읽는 규칙(연도를 뺀 이름)과 그 value 키. 규칙표 키와 다르면 테스트가 깨진다
ENGINE_KEYS: dict[str, frozenset[str]] = {
    "base.earned_income_deduction": frozenset({"limit", "brackets"}),
    "base.tax_rate": frozenset({"brackets"}),
    "base.earned_income_tax_credit": frozenset({"brackets"}),
    "base.earned_income_tax_credit.limit": frozenset({"segments"}),
    "base.standard_tax_credit": frozenset(
        {"amount", "applies_when_none_of", "per_person_choose_larger"}
    ),
    "base.pension_insurance_deduction": frozenset({"payer", "excess_over"}),
    "base.insurance_premium_deduction": frozenset({"payer", "items"}),
    "base.rounding": frozenset({"unit", "mode"}),
    "dependent.basic": frozenset(
        {
            "amount",
            "income_limit",
            "wage_only_gross_limit",
            "lineal_ascendant_min_age",
            "lineal_descendant_max_age",
            "sibling_max_age",
            "sibling_min_age",
            "disabled_no_age_limit",
        }
    ),
    "dependent.additional.elderly": frozenset({"amount", "min_age"}),
    "dependent.additional.disabled": frozenset({"amount"}),
    "dependent.additional.woman": frozenset({"amount", "income_limit", "requires_any"}),
    "dependent.additional.single_parent": frozenset({"amount", "excludes"}),
    "dependent.additional.claimant": frozenset({"eligible_claimant"}),
    "dependent.judgment_date": frozenset({"month_day", "deceased_or_cured", "age"}),
    "child.credit.base": frozenset({"min_age", "one", "two", "extra_per_child_over_two"}),
    "child.credit.birth": frozenset({"first", "second", "third_or_more"}),
}

ROUNDING = "base.rounding"


class RuleNotReadyError(RuntimeError):
    """값이 비어 있는 todo 규칙을 엔진이 쓰려 했다."""


class RuleValueError(ValueError):
    """규칙 value가 엔진이 아는 모양과 다르다(키가 빠졌거나 모르는 값)."""


def _is_empty(node: Any) -> bool:
    """value 안의 모든 값이 빈 리스트·빈 글자·빈 dict면 '비었다'로 본다."""
    if isinstance(node, dict):
        return all(_is_empty(v) for v in node.values())
    if isinstance(node, (list, tuple, str)):
        return len(node) == 0
    return False


class Rulebook:
    """규칙표 한 귀속연도분을 감싼다. 계산 한 번마다 새로 만든다."""

    def __init__(self, rules: dict[str, Rule]):
        years = {r.year for r in rules.values()}
        if len(years) != 1:
            raise RuleValueError(f"규칙표는 한 귀속연도여야 함: {sorted(years)}")
        self.year: int = years.pop()
        self._rules = rules
        self.used: dict[str, list[str]] = {}
        self.needs_check: list[str] = []

    def full_id(self, name: str) -> str:
        return f"{self.year}.{name}"

    def value(self, name: str, stage: str) -> dict[str, Any]:
        """규칙 value를 꺼내고, 그 단계에서 이 규칙을 썼다고 적는다."""
        rule_id = self.full_id(name)
        rule = self._rules.get(rule_id)
        if rule is None:
            raise RuleValueError(f"규칙표에 없음: {rule_id}")
        if rule.status == "todo":
            if _is_empty(rule.value):
                raise RuleNotReadyError(f"{rule_id}: 값이 빈 todo 규칙. {rule.todo}")
            if rule_id not in self.needs_check:
                self.needs_check.append(rule_id)
        missing = ENGINE_KEYS.get(name, frozenset()) - set(rule.value)
        if missing:
            raise RuleValueError(f"{rule_id}: value에 키가 없음 {sorted(missing)}")
        ids = self.used.setdefault(stage, [])
        if rule_id not in ids:
            ids.append(rule_id)
        return rule.value

    def floor(self, amount: Decimal | int, stage: str) -> int:
        """단계 값의 끝수 처리(원 미만 버림, 인쇄 p242). 단위와 방식은 규칙표에서 읽는다."""
        v = self.value(ROUNDING, stage)
        if v["mode"] != "floor":
            raise RuleValueError(f"{self.full_id(ROUNDING)}: 모르는 mode {v['mode']!r}")
        unit = Decimal(v["unit"])
        return int((Decimal(amount) / unit).to_integral_value(ROUND_FLOOR) * unit)

    def rules_used(self) -> dict[str, tuple[str, ...]]:
        return {stage: tuple(ids) for stage, ids in self.used.items()}
