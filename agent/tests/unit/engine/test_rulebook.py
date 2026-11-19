"""todo 규칙 처리, 엔진이 읽는 value 키, 결과 규칙 ID가 규칙표에 있는지."""

import pytest

from taxsplit.engine import (
    CardUsage,
    Dependent,
    EducationExpense,
    MedicalExpense,
    Rulebook,
    RuleNotReadyError,
    compute_tax,
)
from taxsplit.engine.rulebook import ENGINE_KEYS

TODO = "TODO(확인 필요): 테스트용"


def _as_todo(rules, rule_id, value=None):
    """규칙 하나를 todo로 바꾼 가짜 규칙표."""
    old = rules[rule_id]
    new = old.model_copy(update={"status": "todo", "todo": TODO, "value": value or old.value})
    return {**rules, rule_id: new}


def test_engine_keys_match_rule_table(rules):
    # 엔진이 읽는 키와 규칙표 키가 하나라도 다르면 깨진다(Issue #13 todo 규칙 처리)
    for name, keys in ENGINE_KEYS.items():
        assert set(rules[f"2025.{name}"].value) == keys, name


def test_todo_with_value_goes_to_needs_check(rules, make_worker):
    fake = _as_todo(rules, "2025.base.tax_rate")
    r = compute_tax(make_worker(40_000_000), fake)
    assert r.needs_check == ("2025.base.tax_rate",)
    # 값은 그대로 쓴다
    assert r.computed_tax == compute_tax(make_worker(40_000_000), rules).computed_tax


def test_real_table_has_nothing_to_check_for_basic_flow(rules, make_worker):
    assert compute_tax(make_worker(40_000_000), rules).needs_check == ()


def test_empty_todo_raises_not_silently_skipped(rules, make_worker):
    fake = _as_todo(rules, "2025.base.rounding", value={"unit": [], "mode": ""})
    with pytest.raises(RuleNotReadyError, match="2025.base.rounding"):
        compute_tax(make_worker(40_000_000), fake)


def test_real_empty_todo_card_rounding_raises(rules, make_worker):
    # 카드 절사는 PR 5에서 sourced(원 미만 버림, p242)가 됐다. 실제 표는 그대로 읽히고,
    # 값이 빈 todo로 되돌리면 카드 계산이 조용히 넘어가지 않고 멈춘다
    assert Rulebook(rules).value("card.rounding", "card_deduction")["unit"] == 1
    fake = _as_todo(rules, "2025.card.rounding", value={"unit": [], "mode": "", "stages": []})
    w = make_worker(40_000_000, card_usage=(CardUsage(credit=20_000_000),))
    with pytest.raises(RuleNotReadyError, match="2025.card.rounding"):
        compute_tax(w, fake)


def _sample_workers(make_worker):
    deps = (
        Dependent(name="a", relation="child", birth_year=2015),
        Dependent(name="b", relation="child", birth_year=2025, birth_or_adoption_order=3),
        Dependent(name="c", relation="lineal_ascendant", birth_year=1950, disabled=True),
        Dependent(name="d", relation="spouse", birth_year=1985, income_amount=10**7),
    )
    # 의료비·교육비·카드(PR 5) 규칙 ID도 결과에 나오게 지출을 넣는다
    spend = {
        "medical": (
            MedicalExpense(for_name="c", amount=3_000_000),
            MedicalExpense(for_name="d", item="glasses", amount=600_000),
        ),
        "education": (EducationExpense(for_name="a", amount=4_000_000),),
        "card_usage": (CardUsage(credit=30_000_000, culture_credit=1_000_000, market=500_000),),
    }
    return [
        make_worker(g, dependents=deps, national_pension=g // 20, health_insurance=g // 30, **spend)
        for g in (0, 5_000_000, 33_000_001, 70_000_000, 150_000_000, 10**9)
    ]


def test_result_rule_ids_exist_in_table(rules, make_worker):
    for w in _sample_workers(make_worker):
        used = compute_tax(w, rules).rules_used
        ids = {i for stage in used.values() for i in stage}
        assert ids and ids <= set(rules), ids - set(rules)
