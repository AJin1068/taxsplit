"""가족 먼저 묻기: 대화 첫 질문 묶음과, 태어난 해로 정해지는 것(나이·성년·학년) 계산.

지출을 기억해 내라고 묻지 않고 가족과 사건을 묻는다(Issue #126 "정해진 결정").
날짜로 정해지는 것은 묻지 않고 태어난 해로 코드가 계산한다(Issue #109 원칙).
"""

from taxsplit.gaps.loader import GapQuestion, load_questions
from taxsplit.gaps.models import FamilyMember, GapCard, Option, Question

YEAR = 2025
# 인쇄 368쪽: "19세('06.12.31. 이전 출생)가 넘어 성년이 된 자녀"는 자녀가 직접 동의해야 한다
ADULT_AGE = 19
# 학제(세법 숫자가 아님). 연 나이(귀속연도 − 태어난 해)로 본다. synth/ranges.py와 같은 경계
PRESCHOOL_MAX_AGE = 6
ELEMENTARY_MIN_AGE = 7
MIDDLE_MIN_AGE = 13
SCHOOL_MAX_AGE = 18

# 첫 질문 묶음: 부모님 → 같이 사는 그 밖의 가족. 답이 오면 부모님별 후속 질문(다른 형제 공제)
FIRST_IDS = ("gap.parent_living_apart", "gap.other_household_family")
PARENT_FOLLOW_UP = "gap.parent_claimed_by_sibling"


def age_in(birth_year: int, year: int = YEAR) -> int:
    """연 나이(귀속연도 − 태어난 해)."""
    return year - birth_year


def is_adult(m: FamilyMember, year: int = YEAR) -> bool:
    """성년(동의가 필요한 나이)인가. 2025년이면 2006년 이전 출생."""
    return age_in(m.birth_year, year) >= ADULT_AGE


def is_preschool(m: FamilyMember, year: int = YEAR) -> bool:
    return m.relation == "child" and 0 <= age_in(m.birth_year, year) <= PRESCHOOL_MAX_AGE


def in_school(m: FamilyMember, year: int = YEAR) -> bool:
    """초중고 자녀."""
    return m.relation == "child" and ELEMENTARY_MIN_AGE <= age_in(m.birth_year, year) <= (
        SCHOOL_MAX_AGE
    )


def in_middle_or_high(m: FamilyMember, year: int = YEAR) -> bool:
    return m.relation == "child" and MIDDLE_MIN_AGE <= age_in(m.birth_year, year) <= (
        SCHOOL_MAX_AGE
    )


def born_this_year(m: FamilyMember, year: int = YEAR) -> bool:
    return m.relation == "child" and m.birth_year == year


def fill(text: str, person: str | None) -> str:
    """질문 표 글의 {person}을 가족 이름으로 바꾼다."""
    return text.replace("{person}", person or "가족")


def card(
    q: GapQuestion,
    person: str | None = None,
    *,
    ask: bool = True,
    relation: str | None = None,
    birth_year: int | None = None,
) -> GapCard:
    """질문 표 한 줄 → 카드. ask=False면 질문 없이 안내만. 가구 전체 질문은 person 없이 부른다."""
    question = None
    if ask and q.question:
        question = Question(
            text=fill(q.question, person), options=tuple(Option(label=o) for o in q.options)
        )
    return GapCard(
        id=q.id,
        kind=q.kind,
        person=person,
        title=q.title,
        why=fill(q.why, person),
        todo=fill(q.todo, person),
        source_pages=q.pages,
        question=question,
        relation=relation,
        birth_year=birth_year,
    )


def member_card(q: GapQuestion, m: FamilyMember, *, ask: bool = True) -> GapCard:
    """가족 한 명의 카드. 카드 주인(관계·태어난 해)을 가족 정보에서 그대로 채운다."""
    return card(q, m.name, ask=ask, relation=m.relation, birth_year=m.birth_year)


def first_questions(year: int = YEAR) -> list[GapCard]:
    """대화를 시작할 때 묻는 가족 질문 묶음(지출이 아니라 가족을 묻는다)."""
    table = load_questions(year)
    return [card(table[i]) for i in FIRST_IDS]


def parent_follow_ups(members: tuple[FamilyMember, ...], year: int = YEAR) -> list[GapCard]:
    """부모님이 있다고 하면 부모님마다 다른 형제 공제 여부를 묻는다(연세는 태어난 해로 받음)."""
    q = load_questions(year)[PARENT_FOLLOW_UP]
    return [
        member_card(q, m)
        for m in members
        if m.relation == "parent" and m.claimed_by_sibling is None
    ]
