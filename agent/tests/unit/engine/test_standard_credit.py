"""표준세액공제 선택: 특별공제가 없으면 13만원, 특별공제가 더 유리하면 13만원을 받지 않는다."""

from taxsplit.engine import EducationExpense, MedicalExpense, OutOfScopeItem, compute_tax


def _std(rules):
    return rules["2025.base.standard_tax_credit"].value["amount"]


def test_no_special_deduction_gets_standard_credit(rules, make_worker):
    r = compute_tax(make_worker(40_000_000), rules)
    assert r.standard_credit_chosen
    assert r.standard_tax_credit == _std(rules)
    assert r.determined_tax == r.other_option_determined_tax - _std(rules)


def test_special_deduction_better_skips_standard(rules, make_worker):
    w = make_worker(40_000_000, health_insurance=3_000_000, employment_insurance=500_000)
    r = compute_tax(w, rules)
    assert not r.standard_credit_chosen
    assert r.standard_tax_credit == 0
    assert r.insurance_premium_deduction == 3_500_000
    assert r.determined_tax < r.other_option_determined_tax


def test_small_special_deduction_loses_to_standard(rules, make_worker):
    # 보험료 10만원 × 세율 15%는 13만원보다 작다 → 표준세액공제
    r = compute_tax(make_worker(40_000_000, health_insurance=100_000), rules)
    assert r.standard_credit_chosen
    assert r.insurance_premium_deduction == 0


def test_out_of_scope_special_items_dropped_with_standard(rules, make_worker):
    items = (
        OutOfScopeItem(
            name="기부금", kind="tax_credit", category="special_tax_credit", amount=10_000
        ),
        OutOfScopeItem(name="연금계좌", kind="tax_credit", category="other", amount=50_000),
    )
    r = compute_tax(make_worker(40_000_000, out_of_scope=items), rules)
    assert r.standard_credit_chosen
    applied = {o.item.name: o.applied for o in r.out_of_scope}
    assert applied == {"기부금": False, "연금계좌": True}
    assert r.out_of_scope_tax_credit == 50_000
    assert all(o.note == "범위 밖, 입력값 그대로" for o in r.out_of_scope)


def test_chosen_side_is_recorded(rules, make_worker):
    r = compute_tax(make_worker(40_000_000), rules)
    assert r.rules_used["standard_tax_credit"] == ("2025.base.standard_tax_credit",)


def test_deductions_over_income_leave_zero_taxable(rules, make_worker):
    # 소득공제 합계가 근로소득금액을 넘는 부분은 없는 것으로 본다(p103)
    r = compute_tax(make_worker(3_000_000, national_pension=5_000_000), rules)
    assert r.taxable_income == 0
    assert r.deduction_excess > 0
    assert r.determined_tax == 0


def test_medical_and_education_count_as_special_credit(rules, make_worker):
    # 의료비·교육비(특별세액공제)가 13만원보다 크면 특별공제 쪽을 고른다(PR 5)
    w = make_worker(
        40_000_000,
        medical=(MedicalExpense(amount=3_000_000),),
        education=(EducationExpense(amount=1_000_000),),
    )
    r = compute_tax(w, rules)
    assert not r.standard_credit_chosen
    assert r.special_tax_credit_total == r.medical.amount + r.education.amount > _std(rules)
    assert r.tax_credit_total == (
        r.earned_income_credit.amount + r.child_credit.total + r.special_tax_credit_total
    )


def test_small_medical_loses_to_standard(rules, make_worker):
    # 문턱을 조금 넘는 의료비는 공제액이 13만원보다 작아 표준세액공제를 고른다
    w = make_worker(40_000_000, medical=(MedicalExpense(amount=1_300_000),))
    r = compute_tax(w, rules)
    assert r.standard_credit_chosen
    assert r.medical.amount == 0 and r.special_tax_credit_total == 0
    assert r.determined_tax < r.other_option_determined_tax
