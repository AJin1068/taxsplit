"""PR 3g: 실제 규칙표의 "공제 대상이 아닌 지출" 목록과 교육비 맞벌이 규칙 예규 날짜."""

import pytest

from taxsplit.rules.loader import load_rules

# Issue #111 표의 항목. 원문에 없는 항목이 섞이거나 빠지면 깨진다
MEDICAL = [
    ("미용·성형수술 비용", "exclude"),
    ("건강증진을 위한 의약품(보약 등)", "exclude"),
    ("건강기능식품", "exclude"),
    ("진단서 발급비", "exclude"),
    ("외국 의료기관(의료법 제3조 밖)에 낸 비용", "exclude"),
    ("간병비", "exclude"),
    ("실손의료보험금으로 보전받은 금액", "subtract"),
    ("사내근로복지기금에서 받은 의료비 지원", "subtract"),
    ("국민건강보험공단 본인부담금상한제 사후환급금", "subtract"),
    ("공단 출산 전 진료비 지원금으로 낸 의료비", "subtract"),
    ("실제 부양하지 않는 직계존속, 생계를 같이하지 않는 형제자매를 위한 의료비", "condition"),
]
EDUCATION = [
    ("초·중·고등학생 학원비", "exclude"),
    ("본인 외 대학원 교육비", "exclude"),
    (
        "비과세 학자금·장학금(사내근로복지기금, 재학 중인 학교, 직장, 국외근로공무원 자녀, "
        "각종 단체)",
        "subtract",
    ),
    ("직계비속 등이 학자금 대출을 받아 낸 교육비", "exclude"),
]
# Issue 표 12줄. 자동차 줄은 종류가 둘이라 두 항목(구입비·리스료 exclude, 중고차 condition)
CARD = [
    ("사업 관련 비용, 비정상적 사용액", "exclude"),
    ("자동차 구입비, 자동차 리스료", "exclude"),
    ("중고차 구입비", "condition"),
    ("국민건강·장기요양·고용보험료, 연금보험료, 각종 보험료·공제료", "exclude"),
    ("학교(대학원 포함)·어린이집 수업료·입학금·보육비용 등 공납금", "exclude"),
    ("국세·지방세, 전기·수도·가스·전화·인터넷, 아파트관리비, TV 시청료, 도로통행료", "exclude"),
    ("상품권 등 유가증권", "exclude"),
    ("취득세·등록면허세가 붙는 재산(주택 등)", "exclude"),
    ("국가·지자체에 내는 사용료·수수료", "exclude"),
    ("금융·보험 수수료, 가상자산 거래 수수료", "exclude"),
    ("세액공제 받은 정치자금·고향사랑기부금, 기부금단체에 카드로 낸 기부금", "exclude"),
    ("월세 세액공제 받은 월세", "exclude"),
    ("면세점·선박·항공기 면세물품", "exclude"),
]
EXPECTED = {
    "2025.medical.excluded_spending": MEDICAL,
    "2025.education.excluded_spending": EDUCATION,
    "2025.card.excluded_spending": CARD,
}


@pytest.fixture(scope="module")
def rules():
    return load_rules(2025)


@pytest.mark.parametrize("rule_id", sorted(EXPECTED))
def test_items_match_issue_table(rules, rule_id):
    items = rules[rule_id].items
    assert [(i.name, i.kind) for i in items] == EXPECTED[rule_id]


def test_item_counts_by_group(rules):
    counts = {k: len(rules[k].items) for k in EXPECTED}
    assert counts == {
        "2025.medical.excluded_spending": 11,
        "2025.education.excluded_spending": 4,
        "2025.card.excluded_spending": 13,
    }


@pytest.mark.parametrize("rule_id", sorted(EXPECTED))
def test_every_item_has_page_inside_rule_pages(rules, rule_id):
    rule = rules[rule_id]
    assert rule.status == "sourced" and rule.statute
    for item in rule.items:
        assert item.pages, item.name
        assert set(item.pages) <= set(rule.pages), item.name


@pytest.mark.parametrize("rule_id", sorted(EXPECTED))
def test_read_by_input_stage_not_engine(rules, rule_id):
    rule = rules[rule_id]
    assert rule.value["used_by"] == "input_stage"
    assert "입력 단계(PDF 추출·도구)가 읽음" in rule.summary


def test_card_keeps_medical_spending(rules):
    rule = rules["2025.card.excluded_spending"]
    assert rule.value["includes_medical"] is True
    assert "의료비는 빼지 않는다" in rule.summary and "p137" in rule.pages


def test_medical_ambiguous_items_left_to_case_judgment(rules):
    assert "개별 판단" in rules["2025.medical.excluded_spending"].summary


def test_graduate_item_points_to_existing_rule(rules):
    items = {i.name: i for i in rules["2025.education.excluded_spending"].items}
    assert items["본인 외 대학원 교육비"].see == "2025.education.graduate_self_only"


def test_conditions_kept_in_notes(rules):
    edu = {i.name: i for i in rules["2025.education.excluded_spending"].items}
    card = {i.name: i for i in rules["2025.card.excluded_spending"].items}
    assert "1~2월분은 대상" in edu["초·중·고등학생 학원비"].note
    assert (
        "입소료는 포함" in card["학교(대학원 포함)·어린이집 수업료·입학금·보육비용 등 공납금"].note
    )
    assert "10%" in card["중고차 구입비"].note


def test_education_couple_rule_has_ruling_date(rules):
    # Issue #111 정해진 결정(2026-11-19): p181 예규 끝 "(원천-361, 2009.04.24.)"
    rule = rules["2025.education.couple_rule"]
    assert rule.statute == "원천-361 (2009.04.24.)"
    assert rule.pages == ("p181", "p389")
