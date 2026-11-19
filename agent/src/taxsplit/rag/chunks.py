"""근거 원문을 쪽 안에서 조각(chunk)으로 나눈다.

원문 파일(`agent/data/rag/*.jsonl`)은 한 줄에 한 쪽이다. 조각은 쪽을 넘지 않는다.
그래야 조각의 `page`가 늘 하나라서 "맞는 쪽을 찾았나"를 분명하게 잴 수 있다.
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "rag"
BOOKLET_PATH = DATA_DIR / "nts-2025-booklet.jsonl"

# 조각 하나의 글자 수 목표와, 긴 문단을 자를 때 앞 조각과 겹치는 글자 수(운영값, 세법 숫자 아님)
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

_SPACES = re.compile(r"[ \t　]+")
_BLANK_LINES = re.compile(r"\n\s*\n")


class Page(BaseModel):
    """원문 파일 한 줄(= 한 쪽)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    tax_year: int
    source: str
    page: str  # 규칙표 pages와 같은 표기: "p173", "PDF 8쪽"
    print_page: int | None = None
    pdf_page: int | None = None
    text: str


class Chunk(BaseModel):
    """검색 단위. 귀속연도·문서 이름·쪽을 함께 들고 다닌다."""

    model_config = ConfigDict(frozen=True)

    id: str  # "<쪽 id>-c<순번>"
    tax_year: int
    source: str
    page: str
    print_page: int | None = None
    pdf_page: int | None = None
    seq: int  # 쪽 안에서 몇 번째 조각인지(0부터)
    text: str


def load_pages(path: Path = BOOKLET_PATH) -> list[Page]:
    """원문 파일을 읽어 쪽 목록으로."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Page.model_validate_json(line) for line in lines if line.strip()]


def _tidy(text: str) -> str:
    # pdftotext -layout이 넣은 줄 맞춤용 공백만 하나로 줄인다. 글자 자체는 고치지 않는다
    lines = (_SPACES.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(lines)


def _windows(text: str, size: int, overlap: int) -> list[str]:
    """긴 글을 size 글자씩, 앞 조각과 overlap 글자 겹치게 자른다."""
    step = size - overlap
    return [text[i : i + size] for i in range(0, max(len(text) - overlap, 1), step)]


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """빈 줄로 문단을 나누고, 문단을 size까지 모아 조각을 만든다. 넘치는 문단은 겹치게 자른다."""
    paragraphs = [p.strip() for p in _BLANK_LINES.split(_tidy(text)) if p.strip()]
    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > size:
            # 한 문단이 너무 길면 지금까지 모은 것을 내보내고 문단을 잘라 넣는다
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_windows(para, size, overlap))
        elif len(current) + len(para) + 2 > size and current:
            pieces.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def split_page(page: Page, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """쪽 하나를 조각 목록으로. 조각마다 그 쪽의 연도·문서 이름·쪽을 붙인다."""
    return [
        Chunk(
            id=f"{page.id}-c{seq}",
            tax_year=page.tax_year,
            source=page.source,
            page=page.page,
            print_page=page.print_page,
            pdf_page=page.pdf_page,
            seq=seq,
            text=text,
        )
        for seq, text in enumerate(split_text(page.text, size, overlap))
    ]


def load_chunks(path: Path = BOOKLET_PATH) -> list[Chunk]:
    """원문 파일 → 조각 목록."""
    return [chunk for page in load_pages(path) for chunk in split_page(page)]


def dump_pages(pages: list[Page]) -> str:
    """쪽 목록을 원문 파일 모양(JSONL)으로. 테스트가 가짜 원문을 만들 때 쓴다."""
    return "\n".join(json.dumps(p.model_dump(), ensure_ascii=False) for p in pages) + "\n"
