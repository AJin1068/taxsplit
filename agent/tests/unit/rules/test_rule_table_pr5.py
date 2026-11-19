"""PR 5에서 바뀌거나 새로 들어온 규칙: 카드 절사, 의료비 문턱 순서, 대학원은 본인만."""

import pytest

from taxsplit.rules.loader import load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules(2025)


def test_card_rounding_sourced_won_floor(rules):
    rule = rules["2025.card.rounding"]
    assert rule.status == "sourced" and rule.pages == ("p242",)
    assert rule.statute == "소득세법 시행규칙 별지 제24호서식(1) 작성방법 15"
    assert rule.value == {"unit": 1, "mode": "floor", "stages": ["all"]}


@pytest.mark.parametrize(
    ("rule_id", "page", "statute"),
    [
        ("2025.medical.threshold_order", "p173", "소법 §59의4 ②"),
        ("2025.education.graduate_self_only", "p185", "소법 §59의4 ③"),
    ],
)
def test_pr5_new_rules_have_page_and_statute(rules, rule_id, page, statute):
    rule = rules[rule_id]
    assert (rule.status, rule.statute) == ("sourced", statute)
    assert page in rule.pages


@pytest.mark.parametrize(
    ("rule_id", "pages"),
    [
        # PR 5 [기획 확인] 1번: 교육비 한도 표(p180) + 사례 풀이(p185)
        ("2025.education.graduate_self_only", ("p180", "p185")),
        # PR 5 [기획 확인] 2번: 의료비 공제대상 표(p173)가 나이 경계의 근거
        ("2025.medical.limit.others", ("p169", "p173")),
    ],
)
def test_pages_confirmed_by_planning(rules, rule_id, pages):
    assert rules[rule_id].pages == pages


def test_medical_threshold_order(rules):
    # ㉣ 그 외 부양가족 → ㉢ 본인 등 → ㉡ 미숙아 → ㉠ 난임 (Issue #14 정해진 결정)
    order = rules["2025.medical.threshold_order"].value["order"]
    assert order == ["others", "special", "premature_congenital", "infertility"]
