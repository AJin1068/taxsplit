"""규칙표 읽기와 형식 검사.

계산 엔진은 세법 숫자를 코드에 쓰지 않고 `load_rules()`가 돌려준 표에서 읽는다(NFR-05).
표가 규칙을 어기면(ID 중복, 다른 연도, 출처 없음) 읽는 순간 `RuleTableError`로 멈춘다.
"""

import re
import tomllib
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

Group = Literal["base", "dependent", "child", "medical", "education", "card"]
GROUPS: tuple[str, ...] = Group.__args__
Status = Literal["sourced", "todo"]
# 공제 대상이 아닌 지출의 종류: exclude = 지출 종류 자체가 대상 아님,
# subtract = 지출에서 그 금액을 뺌, condition = 조건이 맞을 때만 대상
SpendingKind = Literal["exclude", "subtract", "condition"]
# 이 이름으로 끝나는 규칙은 입력 단계(PDF 추출·도구)가 읽는 "공제 대상이 아닌 지출" 목록이다
EXCLUDED_SUFFIX = ".excluded_spending"

TODO_MARK = "TODO(확인 필요)"
_RULES_DIR = Path(__file__).parent
# 인쇄 쪽 "p94", 쪽 번호가 없는 앞쪽 요약 "PDF 6쪽"
_PAGE = re.compile(r"^(p\d+|PDF \d+쪽)$")
# "0.15"처럼 점이 있는 숫자 문자열은 비율로 보고 Decimal로 바꾼다
_RATE = re.compile(r"^\d+\.\d+$")


class RuleTableError(ValueError):
    """규칙표가 형식이나 규칙을 어겼다."""


def _check_pages(pages: tuple[str, ...]) -> tuple[str, ...]:
    bad = [p for p in pages if not _PAGE.match(p)]
    if bad:
        raise ValueError(f"쪽수 형식이 틀림: {bad} (예: 'p94', 'PDF 6쪽')")
    return pages


class SpendingItem(BaseModel):
    """공제 대상이 아닌 지출 한 항목. 항목마다 원문 쪽이 있어야 한다(설계 원칙 5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: SpendingKind
    pages: tuple[str, ...]
    note: str = ""
    # 같은 내용을 이미 가진 다른 규칙 ID(있으면 그 규칙을 가리키기만 함)
    see: str = ""

    @field_validator("pages")
    @classmethod
    def _page_format(cls, pages: tuple[str, ...]) -> tuple[str, ...]:
        if not pages:
            raise ValueError("항목에 쪽수가 없음")
        return _check_pages(pages)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, name: str) -> str:
        if not name.strip():
            raise ValueError("항목 이름이 비어 있음")
        return name


class Rule(BaseModel):
    """규칙표 한 줄."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    year: int
    group: Group
    summary: str
    statute: str = ""
    pages: tuple[str, ...] = ()
    status: Status
    todo: str = ""
    value: dict[str, Any]
    # 공제 대상이 아닌 지출 목록(엔진은 쓰지 않고 입력 단계가 읽음)
    items: tuple[SpendingItem, ...] = ()

    @field_validator("pages")
    @classmethod
    def _page_format(cls, pages: tuple[str, ...]) -> tuple[str, ...]:
        return _check_pages(pages)

    @field_validator("value")
    @classmethod
    def _rates_to_decimal(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _convert(value)

    @model_validator(mode="after")
    def _source_rules(self) -> Rule:
        # ID에 연도와 그룹이 보여야 한다: 2025.card.threshold
        prefix = f"{self.year}.{self.group}."
        name = self.id.removeprefix(prefix)
        if name == self.id or not re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)*", name):
            raise ValueError(f"ID는 '{prefix}<이름>' 형식이어야 함")
        if self.status == "sourced":
            # 출처 있음 = 쪽수와 조문이 모두 있고 남은 TODO가 없음
            if not self.pages or not self.statute:
                raise ValueError(
                    f"sourced인데 쪽수 또는 조문이 없음. 없으면 status=todo와 {TODO_MARK}"
                )
            if self.todo:
                raise ValueError("sourced인데 todo 칸이 채워져 있음")
        elif not self.todo.startswith(TODO_MARK):
            raise ValueError(f"status=todo이면 todo 칸이 '{TODO_MARK}: 이유'로 시작해야 함")
        if not self.value:
            raise ValueError("value가 비어 있음")
        if self.id.endswith(EXCLUDED_SUFFIX) and not self.items:
            raise ValueError("공제 대상이 아닌 지출 규칙인데 items가 비어 있음")
        return self


def _convert(node: Any) -> Any:
    """TOML 값 안의 비율 문자열("0.15")을 Decimal로 바꾼다. 다른 값은 그대로 둔다."""
    if isinstance(node, dict):
        return {k: _convert(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_convert(v) for v in node]
    if isinstance(node, str) and _RATE.match(node):
        return Decimal(node)
    return node


def rules_path(year: int) -> Path:
    return _RULES_DIR / f"rules_{year}.toml"


def parse_rules(text: str, year: int) -> dict[str, Rule]:
    """TOML 글자를 읽어 {규칙 ID: Rule}로. 규칙을 어기면 RuleTableError."""
    try:
        rows = tomllib.loads(text).get("rule", [])
    except tomllib.TOMLDecodeError as e:
        raise RuleTableError(f"TOML 형식 오류: {e}") from e
    if not rows:
        raise RuleTableError("규칙이 하나도 없음")

    rules: dict[str, Rule] = {}
    for i, row in enumerate(rows):
        label = row.get("id", f"{i + 1}번째 규칙")
        try:
            rule = Rule.model_validate(row)
        except ValidationError as e:
            raise RuleTableError(f"{label}: {e}") from e
        # 한 파일 = 한 귀속연도. 다른 연도 규칙을 섞지 않는다(설계 원칙 3)
        if rule.year != year:
            raise RuleTableError(f"{label}: 귀속연도 {rule.year}가 표 연도 {year}와 다름")
        if rule.id in rules:
            raise RuleTableError(f"{label}: 규칙 ID 중복")
        rules[rule.id] = rule
    # 항목의 see는 같은 표에 있는 규칙만 가리킬 수 있다(표를 다 읽은 뒤 확인)
    for rule in rules.values():
        for item in rule.items:
            if item.see and item.see not in rules:
                raise RuleTableError(f"{rule.id}: 항목 '{item.name}'의 see가 없는 규칙 ID")
    return rules


def load_rules(year: int = 2025, path: Path | None = None) -> dict[str, Rule]:
    """그 귀속연도의 규칙표를 읽는다."""
    file = path or rules_path(year)
    if not file.exists():
        raise RuleTableError(f"{year}년 귀속 규칙표가 없음: {file.name}")
    return parse_rules(file.read_text(encoding="utf-8"), year)


def summary(rules: dict[str, Rule]) -> dict[str, dict[str, int]]:
    """그룹별 규칙 수: {그룹: {"sourced": n, "todo": n}}."""
    counts = Counter((r.group, r.status) for r in rules.values())
    return {g: {s: counts[(g, s)] for s in ("sourced", "todo")} for g in GROUPS}


if __name__ == "__main__":
    # uv run python -m taxsplit.rules.loader  → 그룹별 건수 표
    table = summary(load_rules())
    print("| 그룹 | 출처 있음 | TODO |\n| --- | --- | --- |")
    for group, c in table.items():
        print(f"| {group} | {c['sourced']} | {c['todo']} |")
