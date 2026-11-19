"""추출 결과 검사. AI 답과 JSON 업로드가 같은 검사를 거친다.

실패 이유는 사람이 읽는 한국어로, 어느 칸이 틀렸는지(`items[2].amount`) 함께 적는다.
잡으면 안 되는 것: 합계가 없는 PDF, 0원 줄, 같은 대상자·같은 금액 줄 두 개.
"""

import json
from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from taxsplit.extract.models import GROUP_LABELS, PRIOR_YEAR_NOTE, ExtractedDoc

# 서비스가 계산하는 귀속연도(MVP는 2025, 설계 원칙 3)
SERVICE_YEAR = 2025

# pydantic 오류 종류 → 한국어 이유
_MESSAGES = {
    "missing": "칸이 없습니다",
    "extra_forbidden": "모르는 칸입니다",
    "greater_than_equal": "0 이상이어야 합니다",
    "less_than_equal": "값이 너무 큽니다",
    "int_type": "정수여야 합니다",
    "int_from_float": "정수여야 합니다",
    "string_type": "글자여야 합니다",
    "string_too_short": "비어 있으면 안 됩니다",
    "list_type": "목록이어야 합니다",
    "bool_type": "참/거짓이어야 합니다",
    "model_type": "객체({…})여야 합니다",
    "dict_type": "객체({…})여야 합니다",
}


def _path(loc: tuple[int | str, ...]) -> str:
    """('items', 2, 'amount') → 'items[2].amount'."""
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "(전체)"


def _reason(err: dict[str, Any]) -> str:
    kind = err["type"]
    if kind == "literal_error":
        allowed = err.get("ctx", {}).get("expected", "")
        return f"허용된 값이 아닙니다(입력: {err.get('input')!r}, 가능: {allowed})"
    if kind == "greater_than_equal" and err.get("ctx", {}).get("ge") not in (0, None):
        return f"{err['ctx']['ge']} 이상이어야 합니다"
    return _MESSAGES.get(kind, f"형식이 틀렸습니다({err.get('msg', '')})")


def format_errors(e: ValidationError) -> list[str]:
    """pydantic 오류를 '칸: 이유' 한국어 줄로."""
    return [f"{_path(err['loc'])}: {_reason(err)}" for err in e.errors()]


def strip_fence(text: str) -> str:
    """AI가 ```json … ``` 으로 감싸 답한 경우 감싼 것을 벗긴다."""
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        body = body.rsplit("```", 1)[0]
    return body.strip()


def check_totals(doc: ExtractedDoc) -> list[str]:
    """PDF에 그룹 합계가 있을 때만 항목 합과 대조한다.

    빼고 계산하는 금액(mark=subtract, 예: 보험금 수령액)은 낸 돈이 아니라서 합에 넣지 않는다.
    가정: 가상 PDF의 그룹 합계는 낸 돈만 더한 값이다(실제 PDF 모양은 사람 확인 TODO).
    """
    sums: dict[str, int] = defaultdict(int)
    for item in doc.items:
        if item.mark != "subtract":
            sums[item.group] += item.amount
    errors = []
    for i, total in enumerate(doc.totals):
        got = sums.get(total.group, 0)
        if got != total.amount:
            label = GROUP_LABELS[total.group]
            errors.append(
                f"totals[{i}].amount: {label} 합계가 맞지 않습니다"
                f"(PDF 합계 {total.amount:,}원, 항목 합 {got:,}원)"
            )
    return errors


def finalize(doc: ExtractedDoc) -> ExtractedDoc:
    """작년 자료 표시를 코드가 붙인다. 금액은 바꾸지 않는다."""
    prior = doc.tax_year != SERVICE_YEAR
    notes = [n for n in doc.notes if n != PRIOR_YEAR_NOTE]
    if prior:
        notes.append(PRIOR_YEAR_NOTE)
    return doc.model_copy(update={"prior_year": prior, "notes": notes})


def check_doc(data: str | bytes | dict[str, Any]) -> tuple[ExtractedDoc | None, list[str]]:
    """JSON 글자나 dict를 검사한다. 통과하면 (doc, []), 아니면 (None, 이유 목록)."""
    if isinstance(data, (str, bytes)):
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        try:
            data = json.loads(strip_fence(text))
        except json.JSONDecodeError as e:
            return None, [f"(전체): JSON 형식이 깨졌습니다({e.msg}, {e.lineno}번째 줄)"]
    if not isinstance(data, dict):
        return None, ["(전체): JSON 최상위가 객체({…})여야 합니다"]
    try:
        doc = ExtractedDoc.model_validate(data)
    except ValidationError as e:
        return None, format_errors(e)
    errors = check_totals(doc)
    if errors:
        return None, errors
    return finalize(doc), []
