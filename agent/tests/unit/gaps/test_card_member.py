"""빈 곳 카드의 주인(relation·birth_year) 칸: 가족 정보에서 채우고, 기존 칸은 그대로(Issue #136)."""

from gaps.helpers import fam, household, m, of, parent
from taxsplit.gaps import find_gaps
from taxsplit.gaps.models import GapCard
from taxsplit.rules.loader import load_rules

RULES = load_rules(2025)
# PR 24가 정한 카드 칸(화면·SSE 약속). PR 11c는 이 칸을 바꾸지 않고 더하기만 한다
OLD_FIELDS = {
    "id",
    "kind",
    "person",
    "title",
    "why",
    "todo",
    "source_pages",
    "question",
    "estimate",
    "consent_message",
}


def test_card_fields_are_only_added() -> None:
    assert set(GapCard.model_fields) == OLD_FIELDS | {"relation", "birth_year"}
    # 새 칸은 빈 값을 허용한다(예전 모양 카드도 그대로 만들어진다)
    old = GapCard(id="gap.x", kind="k", person=None, title="t", why="w", todo="d", source_pages=())
    assert old.relation is None and old.birth_year is None


def test_member_cards_carry_relation_and_birth_year() -> None:
    cards = find_gaps(fam(m("엄마", "parent", 1955), m("큰애", "child", 2005)))
    (mom,) = of(cards, "gap.adult_no_consent")
    assert (mom.person, mom.relation, mom.birth_year) == ("엄마", "parent", 1955)
    assert mom.consent_message and mom.question  # 기존 칸은 그대로 채워진다
    (kid,) = of(cards, "gap.child_turned_adult")
    assert (kid.relation, kid.birth_year) == ("child", 2005)


def test_household_wide_cards_have_no_member() -> None:
    cards = find_gaps(fam(m("엄마", "parent", 1955), answered=()))
    (card,) = of(cards, "gap.parent_living_apart")
    assert card.person is None and card.relation is None and card.birth_year is None


def test_same_name_members_are_told_apart() -> None:
    # 이름이 같은 가족 둘: 카드마다 자기 관계·태어난 해가 붙는다(이름으로 짐작하지 않음)
    cards = find_gaps(fam(m("민지", "child", 2005), m("민지", "parent", 1950)))
    consent = of(cards, "gap.adult_no_consent") + of(cards, "gap.child_turned_adult")
    assert {(c.relation, c.birth_year) for c in consent} == {("parent", 1950), ("child", 2005)}


def test_payer_card_uses_household_member() -> None:
    # 가구(계산 엔진 모양)에서 온 카드는 엔진 관계 말 그대로 담는다
    hh = household(
        members=[parent()], medical=[{"payer": "wife", "for_whom": "엄마", "amount": 6_000_000}]
    )
    (card,) = of(find_gaps(fam(), household=hh, rules=RULES), "gap.payer_of_medical_education")
    assert (card.person, card.relation, card.birth_year) == ("엄마", "lineal_ascendant", 1950)


def test_card_json_has_new_fields() -> None:
    (card,) = of(find_gaps(fam(m("엄마", "parent", 1955))), "gap.adult_no_consent")
    data = card.model_dump(mode="json")
    assert data["relation"] == "parent" and data["birth_year"] == 1955
