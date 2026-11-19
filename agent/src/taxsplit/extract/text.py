"""PDF에서 글자 뽑기(pdfplumber).

쪽마다 글자와 표를 그대로 뽑아 AI에게 넘긴다. 표 모양을 코드가 해석하지 않는다
(배치에 맞춘 규칙을 만들지 않기 위해서다. 해석은 AI 정리 단계가 한다).
"""

import io
from dataclasses import dataclass

import pdfplumber


@dataclass(frozen=True)
class PageText:
    page: int  # 1부터
    text: str
    tables: list[list[list[str]]]  # 표 → 줄 → 칸


def pdf_text(pdf_bytes: bytes) -> list[PageText]:
    """PDF 바이트 → 쪽마다 글자와 표. 열 수 없는 파일이면 ValueError."""
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:  # pdfplumber는 깨진 파일에 여러 종류의 오류를 낸다
        raise ValueError(f"PDF를 열 수 없습니다: {e}") from e
    pages = []
    with pdf:
        for i, page in enumerate(pdf.pages, start=1):
            tables = [
                [[cell or "" for cell in row] for row in table] for table in page.extract_tables()
            ]
            pages.append(PageText(page=i, text=page.extract_text() or "", tables=tables))
    return pages


def render_pages(pages: list[PageText]) -> str:
    """AI에게 줄 글: 쪽 번호를 붙이고, 쪽 글자 뒤에 표를 칸 구분(|)으로 붙인다.

    표가 쪽에서 끊겨도 쪽 순서대로 이어 주므로 AI가 이어 읽는다.
    """
    parts = []
    for p in pages:
        parts.append(f"=== {p.page}쪽 글자 ===\n{p.text.strip()}")
        for t, table in enumerate(p.tables, start=1):
            rows = "\n".join(" | ".join(cell.replace("\n", " ") for cell in row) for row in table)
            parts.append(f"--- {p.page}쪽 표 {t} ---\n{rows}")
    return "\n\n".join(parts)


def has_text(pages: list[PageText]) -> bool:
    """글자가 하나라도 있나. 이미지만 있는 PDF(스캔본)는 False."""
    return any(p.text.strip() for p in pages)
