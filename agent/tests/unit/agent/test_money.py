"""금액 뽑기: 뽑는 모양 6가지와 금액이 아닌 숫자."""

import pytest

from taxsplit.agent.money import allowed_with_rounding, extract_amounts, ints_in


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("환급은 1,234,567원입니다", 1_234_567),
        ("환급은 1234567원입니다", 1_234_567),
        ("약 123만 원 더 받아요", 1_230_000),
        ("약 123만원 더 받아요", 1_230_000),
        ("총급여 1억 2,000만 원", 120_000_000),
        ("12만 3천 원 차이", 123_000),
    ],
)
def test_amount_shapes(text: str, value: int) -> None:
    assert [v for _, v in extract_amounts(text)] == [value]


@pytest.mark.parametrize(
    "text",
    [
        "2025년 귀속 연말정산입니다",
        "부양가족 2명을 봤어요",
        "모두 128가지 경우를 비교했어요",
        "총급여의 3%를 넘으면",
        "70세 이상이면",
        "2025년 원천징수 영수증",
    ],
)
def test_not_amounts(text: str) -> None:
    assert extract_amounts(text) == []


def test_several_amounts_in_order() -> None:
    found = extract_amounts("남편 4,200만 원, 아내 3,800만원, 차이 32만 9천 원")
    assert [v for _, v in found] == [42_000_000, 38_000_000, 329_000]


def test_ints_in_skips_bool_and_adds_abs() -> None:
    assert ints_in({"a": [1, True, {"b": -5}], "c": "7"}) == {1, -5, 5}


def test_man_rounding_down_and_up() -> None:
    allowed = allowed_with_rounding({472_150})
    assert {472_150, 470_000, 480_000, 0} <= allowed
    assert 500_000 not in allowed
