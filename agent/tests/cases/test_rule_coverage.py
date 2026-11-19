"""규칙 커버리지(rule_coverage.py)가 PR 무게 (라)에 쓸 만한지 확인한다."""

from cases.case_compare import all_rows
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
    # 산출세액(세율)은 아직 어떤 사례도 비교하지 않는다(PR 5). 계산 중에 지나가도 0건이어야 한다
    compared = {r.stage for r in all_rows() if r.kind == "compare"}
    engine_stages = {s for c in compared for s in CASE_TO_ENGINE[c]}
    assert "computed_tax" not in engine_stages
    assert coverage()["2025.base.tax_rate"] == 0


def test_case_file_of_strips_sub_run():
    assert case_file_of("a-b#q1") == "a-b"
    assert case_file_of("a-b/husband") == "a-b"
