"""find_missing_deductions 인자 검사. 가구 칸은 앞 두 도구와 같은 검사(validate_household)를 쓴다.

고른 금액은 선택지 금액만 받는다: AI가 "약 200만"처럼 짐작한 금액을 넣지 못하게 한다.
"""

from typing import Any

from pydantic import ValidationError

from taxsplit.gaps.estimate import OPTION_AMOUNTS
from taxsplit.gaps.models import GapRequest
from taxsplit.tools.validation import ArgError, _message, _path, validate_household


def _pick_errors(req: GapRequest) -> list[ArgError]:
    out: list[ArgError] = []
    names = {m.name for m in req.household.members} if req.household else set()
    allowed = ", ".join(f"{a:,}" for a in sorted(OPTION_AMOUNTS))
    for i, p in enumerate(req.picks):
        if p.amount not in OPTION_AMOUNTS:
            msg = f"선택지 금액이 아님. 받은 값 {p.amount!r}. 허용: {allowed}"
            out.append(ArgError(f"picks[{i}].amount", "not_allowed", msg))
        if req.household is None:
            msg = "놓칠 금액을 계산하려면 household를 함께 넣으세요"
            out.append(ArgError(f"picks[{i}]", "missing", msg))
        elif p.person not in names:
            msg = f"household.members에 없는 사람 {p.person!r}. 그 가족을 members에 넣으세요"
            out.append(ArgError(f"picks[{i}].person", "unknown_target", msg))
    return out


def validate_gap_request(args: Any) -> tuple[GapRequest | None, list[ArgError]]:
    """인자 → (요청, 오류 목록). 오류가 하나라도 있으면 요청은 None."""
    errors: list[ArgError] = []
    if isinstance(args, dict) and args.get("household") is not None:
        # 가구는 앞 두 도구와 같은 규칙(소득 칸 직접 적기, 지출 대상 이름)으로 본다
        _, household_errors = validate_household(args["household"])
        errors += [ArgError(f"household.{e.path}", e.kind, e.message) for e in household_errors]
        if errors:
            return None, errors
    try:
        req = GapRequest.model_validate(args)
    except ValidationError as e:
        for err in e.errors():
            kind, msg = _message(err)
            errors.append(ArgError(_path(err["loc"]), kind, msg))
        return None, errors
    errors = _pick_errors(req)
    return (None, errors) if errors else (req, [])
