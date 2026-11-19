"""구간표 계산 도우미. 숫자는 모두 규칙표에서 온 것을 받는다.

구간표 한 줄: over = 이 금액을 "넘는" 구간, 값 = base + (금액 − over) × rate.
결과는 Decimal로 돌려주고, 원 미만 버림은 부르는 쪽이 Rulebook.floor로 한다.
"""

from decimal import Decimal
from typing import Any


def pick_bracket(amount: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """금액이 '넘는' 마지막 구간. 0원 이하면 첫 구간."""
    chosen = rows[0]
    for row in rows:
        if amount > row["over"]:
            chosen = row
    return chosen


def bracket_amount(amount: int, brackets: list[dict[str, Any]]) -> Decimal:
    """base + (금액 − over) × rate."""
    row = pick_bracket(amount, brackets)
    return Decimal(row["base"]) + (amount - row["over"]) * Decimal(row["rate"])


def segment_limit(amount: int, segments: list[dict[str, Any]]) -> Decimal:
    """한도 = max(floor, base − (금액 − over) × slope). 근로소득세액공제 한도 모양."""
    seg = pick_bracket(amount, segments)
    reduced = Decimal(seg["base"]) - (amount - seg["over"]) * Decimal(seg["slope"])
    return max(Decimal(seg["floor"]), reduced)
