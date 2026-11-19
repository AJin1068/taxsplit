"""잡으면 안 되는 것 6가지(알림이 나가면 틀린 것). Issue #126 "하지 않을 것"을 하나씩 따로 본다."""

from gaps.helpers import doc, fam, household, item, m, of, parent
from taxsplit.gaps import find_gaps
from taxsplit.gaps.models import GapCard
from taxsplit.rules.loader import load_rules

RULES = load_rules(2025)
CONSENT_IDS = ("gap.adult_no_consent", "gap.child_turned_adult", "gap.dependent_card_usage")
SELF_ONLY_WORDS = ("국민연금", "건강보험", "연금저축", "퇴직연금", "주택자금", "대학원")


def consent_cards(cards: list[GapCard], person: str) -> list[GapCard]:
    return [c for c in cards if c.id in CONSENT_IDS and c.person == person]


def texts(c: GapCard) -> str:
    q = c.question.text if c.question else ""
    return " ".join([c.why, c.todo, q, c.consent_message or ""])


def test_must_not_1_consent_alert_when_data_exists():
    # 어머니 이름으로 된 카드 사용액이 이미 있다 = 동의가 되어 있다
    family = fam(m("엄마", "parent", 1955), m("큰애", "child", 2003))
    docs = [doc(item("card", "엄마")), doc(item("education", "큰애"), worker="아내")]
    cards = find_gaps(family, docs)
    assert consent_cards(cards, "엄마") == []
    assert consent_cards(cards, "큰애") == []


def test_must_not_2_consent_for_minor_child():
    # 2007.1.1. 이후 출생 자녀는 동의 없이 조회된다(인쇄 378쪽)
    family = fam(m("고3", "child", 2007), m("중1", "child", 2012), m("아기", "child", 2025))
    cards = find_gaps(family)
    for name in ("고3", "중1", "아기"):
        assert consent_cards(cards, name) == []
    assert all(c.consent_message is None for c in cards)


def test_must_not_3_living_apart_for_sibling_or_grandchild():
    family = fam(
        m("동생", "sibling", 1990, lives_with=False),
        m("누나", "sibling", 1978, lives_with=True),
        m("손주", "grandchild", 2004, lives_with=None),
    )
    cards = find_gaps(family)
    # 따로 사는(또는 모르는) 형제자매·손주에게 동의 알림을 내지 않는다(같이 살아야 공제 대상)
    assert consent_cards(cards, "동생") == [] and consent_cards(cards, "손주") == []
    # 같이 사는 누나는 동의 알림은 나가도 카드 사용액 카드는 없다(형제자매 카드는 공제 안 됨)
    assert [c.id for c in consent_cards(cards, "누나")] == ["gap.adult_no_consent"]
    for c in cards:
        if c.person in ("동생", "누나", "손주"):
            assert "따로" not in texts(c)
    # "따로 살아도"는 부모님 질문에만 나온다
    assert all(c.id == "gap.parent_living_apart" for c in cards if "따로" in texts(c))


def test_must_not_4_self_only_items_of_consented_dependent():
    # 동의한 어머니: 의료비는 보이고 국민연금·건강보험료 줄은 없다(본인 불입분만 공제, 369쪽 Q3)
    family = fam(m("엄마", "parent", 1955))
    cards = find_gaps(family, [doc(item("medical", "엄마"), item("insurance", "남편", "건강보험"))])
    assert consent_cards(cards, "엄마") == []
    for c in cards:
        assert not any(w in texts(c) for w in SELF_ONLY_WORDS), c.id


def test_must_not_5_who_paid_when_result_is_same():
    # 어머니 병원비 10만 원: 누가 냈든 결과가 같아 "누가 내셨어요?"를 묻지 않는다
    hh = household(
        members=[parent()], medical=[{"payer": "wife", "for_whom": "엄마", "amount": 100_000}]
    )
    cards = find_gaps(fam(m("엄마", "parent", 1955)), household=hh, rules=RULES)
    assert of(cards, "gap.payer_of_medical_education") == []


def test_must_not_6_school_questions_without_such_child():
    family = fam(m("엄마", "parent", 1955), m("큰애", "child", 2001), m("동생", "sibling", 1990))
    ids = {c.id for c in find_gaps(family, [doc(item("medical", "엄마"))])}
    assert not ids & {"gap.school_uniform", "gap.field_trip", "gap.preschool_academy"}
