"""AI가 보낸 것처럼 JSON 모양 dict로 만든 가구 인자."""

import copy

# 어머니(소득 0원 명시)·자녀(근로소득 총급여 0원 명시)가 있는 맞벌이 가구
BASE_ARGS = {
    "husband": {"gross_salary": 60_000_000, "sex": "male", "birth_year": 1980},
    "wife": {"gross_salary": 45_000_000, "sex": "female", "birth_year": 1982},
    "members": [
        {
            "dependent": {
                "name": "어머니",
                "relation": "lineal_ascendant",
                "birth_year": 1955,
                "income_amount": 0,
            },
            "family_of": "husband",
        },
        {
            "dependent": {
                "name": "아이",
                "relation": "child",
                "birth_year": 2016,
                "wage_only_gross": 0,
            }
        },
    ],
    "medical": [{"payer": "husband", "for_whom": "어머니", "amount": 2_500_000}],
    "education": [{"payer": "wife", "for_whom": "아이", "amount": 500_000}],
    "cards": [
        {"user": "husband", "credit": 20_000_000},
        {"user": "wife", "credit": 12_000_000},
    ],
}


def household_args() -> dict:
    """테스트마다 고쳐 써도 되게 깊은 복사본을 준다."""
    return copy.deepcopy(BASE_ARGS)
