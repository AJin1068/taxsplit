"""도구 인자 검사: 가구 입력이 맞는지 보고, 틀리면 칸 경로와 한국어 이유를 돌려준다.

인자를 고쳐서 실행하지 않는다(예: "약 300만" → 3,000,000). 거절해서 AI가 사용자에게 묻게 한다.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from taxsplit.allocation.models import WHO, Household

# 부양가족 소득으로 보는 칸. 둘 중 하나는 AI가 직접 적어야 한다(기본값 0원 = "소득 없음" 방지)
INCOME_FIELDS = frozenset({"income_amount", "wage_only_gross"})
_ASK = "사용자에게 정확한 값을 물어 다시 부르세요"


@dataclass(frozen=True)
class ArgError:
    """인자 하나의 검사 실패. kind는 평가에서 "잘못된 값" 종류를 셀 때 쓴다."""

    path: str
    kind: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _path(loc: tuple[Any, ...]) -> str:
    # ('members', 0, 'dependent', 'income_amount') → members[0].dependent.income_amount
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "(가구 전체)"


def _message(err: dict[str, Any]) -> tuple[str, str]:
    """pydantic 오류 하나 → (종류, 한국어 이유)."""
    kind, got = err["type"], err.get("input")
    if kind in ("int_type", "int_parsing", "int_from_float"):
        return "not_integer", f"정수(원)여야 함. 받은 값 {got!r}. {_ASK}"
    if kind == "greater_than_equal":
        return "negative", f"{err['ctx']['ge']} 이상이어야 함. 받은 값 {got!r}. {_ASK}"
    if kind == "missing":
        return "missing", f"꼭 넣어야 하는 칸이 빠짐. {_ASK}"
    if kind == "extra_forbidden":
        return "unknown_field", "모르는 칸. 이 칸은 빼고 스키마에 있는 칸만 쓰세요"
    if kind in ("literal_error", "enum"):
        allowed = err.get("ctx", {}).get("expected", "")
        return "not_allowed", f"허용되지 않는 값. 받은 값 {got!r}. 허용: {allowed}"
    return "bad_format", f"형식이 맞지 않음({err['msg']}). 받은 값 {got!r}"


def _names(args: dict[str, Any]) -> set[str] | None:
    """인자에 적힌 부양가족 이름. members 모양이 깨져 있으면 None(그때는 pydantic 오류로 충분)."""
    members = args.get("members", [])
    if not isinstance(members, list | tuple):
        return None
    try:
        return {m["dependent"]["name"] for m in members}
    except KeyError, TypeError:
        return None


def _target_errors(args: dict[str, Any]) -> list[ArgError]:
    """의료비·교육비 대상과 카드 사용자가 부부나 부양가족 이름인지 본다."""
    names = _names(args)
    if names is None:
        return []
    known = names | set(WHO)
    out: list[ArgError] = []
    for kind, key in (("medical", "for_whom"), ("education", "for_whom"), ("cards", "user")):
        rows = args.get(kind, [])
        for i, row in enumerate(rows if isinstance(rows, list | tuple) else []):
            who = row.get(key) if isinstance(row, dict) else None
            if isinstance(who, str) and who not in known:
                out.append(
                    ArgError(
                        f"{kind}[{i}].{key}",
                        "unknown_target",
                        f"가구에 없는 사람 {who!r}. 'husband', 'wife' 또는 members의 이름이어야 함",
                    )
                )
    return out


def _income_errors(household: Household) -> list[ArgError]:
    """부양가족마다 소득 칸을 AI가 직접 적었는지 본다(0원을 적은 것은 통과)."""
    out: list[ArgError] = []
    for i, m in enumerate(household.members):
        if not INCOME_FIELDS & m.dependent.model_fields_set:
            out.append(
                ArgError(
                    f"members[{i}].dependent.income_amount",
                    "income_missing",
                    f"{m.name}의 올해 소득을 사용자에게 물어 넣으세요. 모르면 추측하지 마세요",
                )
            )
    return out


def validate_household(args: Any) -> tuple[Household | None, list[ArgError]]:
    """인자 → (가구, 오류 목록). 오류가 하나라도 있으면 가구는 None."""
    targets = _target_errors(args) if isinstance(args, dict) else []
    try:
        household = Household.model_validate(args)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            # 지출 대상 오류는 위에서 칸 경로와 함께 이미 잡았다(모델 검사는 경로 없이 한 줄)
            if not err["loc"] and err["type"] == "value_error" and targets:
                continue
            kind, msg = _message(err)
            errors.append(ArgError(_path(err["loc"]), kind, msg))
        return None, errors + targets
    errors = _income_errors(household)
    return (None, errors) if errors else (household, [])


def family_fingerprint(household: Household) -> str:
    """가족 구성 지문: 부부 본인 정보 + 부양가족 목록. 의료비·교육비·카드 금액은 넣지 않는다.

    요건 판정은 지출 금액과 상관없어서, 금액만 바뀌면 요건 확인을 다시 요구하지 않는다(Issue #18).
    부부의 범위 밖 공제 금액(out_of_scope)도 지출 성격이라 뺀다.
    """
    data = {
        "husband": household.husband.model_dump(mode="json", exclude={"out_of_scope"}),
        "wife": household.wife.model_dump(mode="json", exclude={"out_of_scope"}),
        "members": [m.model_dump(mode="json") for m in household.members],
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()
