"""사례 파일의 inputs + 보충 입력(supplement) + 공제 대상 여부(eligibility) → 엔진에 넣을 입력.

테스트 쪽에만 둔다(처리 코드는 사례 파일을 읽지 않는다). 형식은 eval/README.md
"보충 입력"·"공제 대상 여부" 절. Issue #14 정해진 결정(2026-11-18, 2026-11-19 덧붙임).

- 문서에 없는 값(본인 성별·출생연도, "60세 이상" 같은 나이)은 테스트가 채우지 않는다.
  사례 파일의 supplement.values(경로 = JSON Pointer)를 inputs에 더한다.
- 공제 대상이 아닌 지출 목록을 테스트가 따로 두지 않는다. eligibility.rows에서
  filtered_by == "input"인 줄만 엔진 입력에서 뺀다. "engine"인 줄은 넣어 엔진이 0을 내게 둔다.
- 두 칸 중 하나라도 confirmed가 아니면 그 사례는 "입력 부족"이다(채점·비교에 쓰지 않음).
"""

import copy
from typing import Any


def _parts(pointer: str) -> list[str]:
    # RFC 6901: "~1" → "/", "~0" → "~"
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]


def _key(container: Any, part: str) -> Any:
    return int(part) if isinstance(container, list) else part


def set_pointer(doc: dict, pointer: str, value: Any) -> None:
    """doc 안 pointer 자리에 value를 넣는다. 중간 칸이 없으면 객체로 만든다."""
    *parents, last = _parts(pointer)
    cur = doc
    for part in parents:
        if isinstance(cur, dict):
            cur = cur.setdefault(part, {})
        else:
            cur = cur[int(part)]
    if isinstance(cur, list):
        raise ValueError(f"보충 입력은 목록에 줄을 더하지 않는다: {pointer}")
    if last in cur:
        # 형식 검사(eval/cases/supplement.py)가 막지만, 문서 값을 덮어쓰지 않도록 한 번 더 본다
        raise ValueError(f"보충 입력이 inputs에 있는 값을 덮어씀: {pointer}")
    cur[last] = value


def _drop_pointers(doc: dict, pointers: list[str]) -> None:
    """pointers 자리를 지운다. 목록 줄은 뒤에서부터 지워 앞 줄 번호가 밀리지 않게 한다."""
    found = []
    for pointer in pointers:
        *parents, last = _parts(pointer)
        cur = doc
        for part in parents:
            cur = cur[_key(cur, part)]
        found.append((cur, _key(cur, last)))
    # 지울 자리를 먼저 다 찾은 뒤, 목록 번호가 큰 것부터 지운다(객체 칸은 순서 상관없음)
    for container, key in sorted(found, key=lambda f: f[1] if isinstance(f[1], int) else -1)[::-1]:
        del container[key]


def section_ok(case: dict, name: str) -> bool:
    """칸이 없거나 confirmed면 True. draft면 그 칸을 쓸 수 없다."""
    return name not in case or case[name].get("status") == "confirmed"


def usable(case: dict) -> bool:
    """보충 입력·공제 대상 여부가 모두 쓸 수 있는 상태인가(아니면 "입력 부족")."""
    return section_ok(case, "supplement") and section_ok(case, "eligibility")


def engine_inputs(case: dict) -> dict:
    """inputs에 보충 값을 더하고, 지출 종류 자체가 대상 아닌 줄을 뺀 사본."""
    if not usable(case):
        raise ValueError(f"{case['id']}: supplement·eligibility가 confirmed가 아님")
    merged = copy.deepcopy(case["inputs"])
    for ent in case.get("supplement", {}).get("values", []):
        set_pointer(merged, ent["path"], copy.deepcopy(ent["value"]))
    rows = case.get("eligibility", {}).get("rows", [])
    _drop_pointers(merged, [r["path"] for r in rows if r.get("filtered_by") == "input"])
    return merged
