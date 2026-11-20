"""놓치기 쉬운 공제 질문 표(questions_<연도>.toml) 읽기.

근거 쪽이 빠졌거나, ID가 겹치거나, 파일 귀속연도가 요청 연도와 다르면 읽지 않고 거부한다.
연도가 다른 표를 섞지 않는다(설계 원칙 3).
"""

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent
KINDS = frozenset({"가", "나", "다", "가/나"})
_REQUIRED = ("no", "id", "kind", "when", "title", "why", "todo", "pages")


class GapTableError(ValueError):
    """질문 표가 규칙에 맞지 않음."""


@dataclass(frozen=True)
class GapQuestion:
    no: int
    id: str
    kind: str
    when: str
    title: str
    why: str
    todo: str
    # 원본 문서 인쇄 쪽
    pages: tuple[str, ...]
    # 원본 문서 정식 이름
    source_doc: str
    question: str | None = None
    options: tuple[str, ...] = ()


def questions_path(year: int) -> Path:
    return _DIR / f"questions_{year}.toml"


def _row(raw: dict[str, Any], source_doc: str) -> GapQuestion:
    missing = [k for k in _REQUIRED if not raw.get(k)]
    if missing:
        raise GapTableError(f"{raw.get('id', '(ID 없음)')}: 빠진 칸 {missing}")
    if not str(raw["id"]).startswith("gap."):
        raise GapTableError(f"{raw['id']}: ID는 gap.으로 시작해야 함(규칙 ID와 섞지 않음)")
    if raw["kind"] not in KINDS:
        raise GapTableError(f"{raw['id']}: 종류 {raw['kind']!r}는 가·나·다·가/나 중 하나여야 함")
    return GapQuestion(
        no=int(raw["no"]),
        id=raw["id"],
        kind=raw["kind"],
        when=raw["when"],
        title=raw["title"],
        why=raw["why"],
        todo=raw["todo"],
        pages=tuple(str(p) for p in raw["pages"]),
        source_doc=source_doc,
        question=raw.get("question"),
        options=tuple(raw.get("options", ())),
    )


def parse_questions(text: str, year: int) -> dict[str, GapQuestion]:
    """TOML 글 → {질문 ID: 질문}. 규칙에 어긋나면 GapTableError."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise GapTableError(f"TOML 형식 오류: {e}") from e
    if data.get("tax_year") != year:
        raise GapTableError(f"표의 귀속연도 {data.get('tax_year')!r} ≠ 요청 연도 {year}")
    source_doc = data.get("source_doc")
    if not source_doc:
        raise GapTableError("source_doc(원본 문서 정식 이름)이 없음")
    out: dict[str, GapQuestion] = {}
    for raw in data.get("question", []):
        q = _row(raw, source_doc)
        if q.id in out:
            raise GapTableError(f"{q.id}: ID가 겹침")
        out[q.id] = q
    return out


@cache
def load_questions(year: int = 2025) -> dict[str, GapQuestion]:
    path = questions_path(year)
    if not path.exists():
        raise GapTableError(f"{year}년 질문 표가 없음: {path.name}")
    return parse_questions(path.read_text(encoding="utf-8"), year)
