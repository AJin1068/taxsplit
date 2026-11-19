"""인자 검사: 잘못된 값 7종류가 칸 경로·한국어 이유와 함께 잡힌다. 가족 지문."""

import pytest

from taxsplit.allocation.models import Household
from taxsplit.tools.validation import family_fingerprint, validate_household
from tools.household_args import household_args


def _bad(path: list, value):
    """path 칸을 value로 바꾼 인자. value가 _DROP이면 칸을 지운다."""
    args = household_args()
    node = args
    for key in path[:-1]:
        node = node[key]
    if value is _DROP:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return args


_DROP = object()

# (종류, 바꿀 칸, 값, 기대 칸 경로)
# fmt: off
CASES = [
    ("not_integer", ["members", 0, "dependent", "income_amount"], "약 300만",
     "members[0].dependent.income_amount"),
    ("not_integer", ["husband", "gross_salary"], 1.5, "husband.gross_salary"),
    ("not_integer", ["medical", 0, "amount"], "250만원", "medical[0].amount"),
    ("negative", ["wife", "gross_salary"], -1, "wife.gross_salary"),
    ("negative", ["cards", 0, "credit"], -500_000, "cards[0].credit"),
    ("missing", ["husband", "gross_salary"], _DROP, "husband.gross_salary"),
    ("missing", ["members", 1, "dependent", "birth_year"], _DROP,
     "members[1].dependent.birth_year"),
    ("unknown_field", ["wife", "bonus"], 1_000_000, "wife.bonus"),
    ("unknown_field", ["members", 0, "dependent", "job"], "자영업", "members[0].dependent.job"),
    ("not_allowed", ["members", 0, "dependent", "relation"], "cousin",
     "members[0].dependent.relation"),
    ("not_allowed", ["education", 0, "level"], "high_school", "education[0].level"),
    ("income_missing", ["members", 0, "dependent", "income_amount"], _DROP,
     "members[0].dependent.income_amount"),
    ("income_missing", ["members", 1, "dependent", "wage_only_gross"], _DROP,
     "members[1].dependent.income_amount"),
    ("unknown_target", ["medical", 0, "for_whom"], "삼촌", "medical[0].for_whom"),
    ("unknown_target", ["cards", 1, "user"], "할머니", "cards[1].user"),
]
# fmt: on


@pytest.mark.parametrize(("kind", "path", "value", "where"), CASES)
def test_bad_args_caught_with_path(kind, path, value, where):
    household, errors = validate_household(_bad(path, value))
    assert household is None
    assert [(e.kind, e.path) for e in errors] == [(kind, where)]
    assert errors[0].message


def test_not_integer_message_quotes_value_and_asks_user():
    _, errors = validate_household(_bad(["members", 0, "dependent", "income_amount"], "약 300만"))
    msg = str(errors[0])
    assert msg.startswith("members[0].dependent.income_amount: 정수(원)여야 함")
    assert "'약 300만'" in msg and "사용자에게" in msg


def test_income_missing_message_names_dependent():
    _, errors = validate_household(_bad(["members", 0, "dependent", "income_amount"], _DROP))
    assert errors[0].message.startswith("어머니의 올해 소득을 사용자에게 물어 넣으세요")
    assert "추측하지" in errors[0].message


def test_not_a_dict():
    household, errors = validate_household(["husband"])
    assert household is None and errors[0].path == "(가구 전체)"


def test_valid_args_pass():
    household, errors = validate_household(household_args())
    assert errors == [] and isinstance(household, Household)


def test_fingerprint_ignores_spending_only():
    base, _ = validate_household(household_args())
    args = household_args()
    args["medical"][0]["amount"] = 9_000_000
    args["cards"][0]["credit"] = 1
    args["education"] = []
    spent, _ = validate_household(args)
    assert family_fingerprint(base) == family_fingerprint(spent)


def test_fingerprint_changes_with_family():
    base, _ = validate_household(household_args())
    args = household_args()
    args["members"][0]["dependent"]["income_amount"] = 5_000_000
    changed, _ = validate_household(args)
    assert family_fingerprint(base) != family_fingerprint(changed)
