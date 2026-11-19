"""규칙 커버리지(rule_coverage.py)가 PR 무게 (라)에 쓸 만한지 확인한다."""

from cases.case_compare import all_rows, all_runs
from cases.rule_coverage import CASE_TO_ENGINE, case_file_of, coverage
from taxsplit.rules.loader import load_rules


def test_every_rule_id_has_a_count():
    result = coverage()
    assert set(result) == set(load_rules(2025))
    assert all(isinstance(n, int) and n >= 0 for n in result.values())


def test_every_compared_stage_is_mapped():
    # 비교 단계가 새로 생기면 CASE_TO_ENGINE에 엔진 단계를 적어야 한다(빠지면 규칙이 0건으로 보임)
    stages = {r.stage for r in all_rows() if r.kind == "compare"}
    assert stages <= set(CASE_TO_ENGINE), sorted(stages - set(CASE_TO_ENGINE))


def test_some_rules_are_covered_and_some_are_not():
    # 화면·문서만 바꾼 PR은 상관없고, 규칙을 바꾼 PR만 갈리려면 0건/1건 이상이 섞여 있어야 한다
    counts = coverage().values()
    assert any(n > 0 for n in counts)
    assert any(n == 0 for n in counts)


def test_rule_used_only_in_uncompared_stage_is_not_counted():
    # 근로소득공제만 비교하는 사례(국세청 인쇄 95쪽) 하나만 센다. 엔진은 끝까지 돌아 세율 규칙도
    # 지나가지만, 산출세액을 비교하지 않으므로 세율 규칙은 0건이어야 한다.
    # (PR 5부터 다른 사례가 산출세액을 비교하므로 전체 사례가 아니라 이 사례로 본다)
    label = next(run.label for _, run in all_runs() if "p095" in run.label)
    rows = [r for r in all_rows() if r.case == label]
    compared = {r.stage for r in rows if r.kind == "compare"}
    assert compared and "computed_tax" not in compared
    result = coverage(rows, [(s, run) for s, run in all_runs() if run.label == label])
    assert result["2025.base.earned_income_deduction"] == 1
    assert result["2025.base.tax_rate"] == 0


def test_case_file_of_strips_sub_run():
    assert case_file_of("a-b#q1") == "a-b"
    assert case_file_of("a-b/husband") == "a-b"
