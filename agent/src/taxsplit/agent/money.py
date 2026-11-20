"""글에서 금액 뽑기와 허용 금액 비교(금액 센서용).

금액으로 보는 것: 끝에 "원"이 붙은 숫자 표현만.
  1,234,567원 / 1234567원 / 123만 원 / 123만원 / 1억 2,000만 원 / 12만 3천 원
금액이 아닌 것: "원"이 붙지 않은 숫자(2025년, 2명, 128가지, 3%, 70세).
"""

import re
from collections.abc import Iterable
from typing import Any

_UNITS = {"억": 100_000_000, "천만": 10_000_000, "백만": 1_000_000, "만": 10_000, "천": 1_000}
_NUM = r"\d[\d,]*(?:\.\d+)?"
_UNIT = r"(?:억|천만|백만|만|천)"
# 단위가 붙은 조각 0개 이상 + (단위 없는 숫자) + "원".
# 앞에 숫자가 이어지면 잘린 조각이라 보지 않는다
_AMOUNT = re.compile(rf"(?<![\d.,])((?:{_NUM}\s*{_UNIT}\s*)*(?:{_NUM})?)\s*원")
_PART = re.compile(rf"({_NUM})\s*({_UNIT})?")

MAN = 10_000


def _value(expr: str) -> int | None:
    total = 0.0
    found = False
    for number, unit in _PART.findall(expr):
        digits = number.replace(",", "")
        if not digits or digits == ".":
            continue
        total += float(digits) * _UNITS.get(unit, 1)
        found = True
    return round(total) if found else None


def extract_amounts(text: str) -> list[tuple[str, int]]:
    """글에서 (원래 글자, 원 단위 금액) 목록. 나온 순서대로."""
    out = []
    for m in _AMOUNT.finditer(text):
        expr = m.group(1).strip()
        if not expr:
            continue
        value = _value(expr)
        if value is not None:
            out.append((m.group(0).strip(), value))
    return out


def ints_in(value: Any) -> set[int]:
    """JSON 모양 값(dict·list) 안의 모든 정수. 참/거짓은 빼고, 음수는 크기(절댓값)도 넣는다.

    TODO(사람 확인): docs/assumptions.md A-036
    """
    found: set[int] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            found.update({item, abs(item)})
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return found


def _man_variants(v: int) -> set[int]:
    """만 원 단위로 줄인 값: 버림과 올림(반올림은 둘 중 하나). 472,150 → {470,000, 480,000}.

    Issue #19 예시("48만 원은 반올림이라 통과")에 맞춰 올림도 받는다.
    TODO(사람 확인): docs/assumptions.md A-035
    """
    down = (v // MAN) * MAN
    up = down if v % MAN == 0 else down + MAN
    return {down, up}


def allowed_with_rounding(allowed: Iterable[int]) -> set[int]:
    """허용 목록 + 그 값들을 만 원 단위로 줄인 값. 0원은 늘 허용한다."""
    out = {0}
    for v in allowed:
        out.add(v)
        out.update(_man_variants(v))
    return out


def unknown_amounts(text: str, allowed: set[int]) -> list[tuple[str, int]]:
    """allowed_with_rounding으로 만든 목록 밖의 금액(원래 글자, 값)."""
    return [(raw, v) for raw, v in extract_amounts(text) if v not in allowed]
