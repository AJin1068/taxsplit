"""가상 간소화 PDF 3개와 정답 JSON 만들기.

    uv run python experiments/make_fake_pdfs.py --font <한글 TTF 경로>

글꼴은 재배포 가능한 것(OFL 등, 예: 나눔·Noto Sans KR)을 쓰고 레포에 넣지 않는다.
만든 PDF·JSON은 tests/unit/extract/fixtures/에 커밋해 테스트가 이 스크립트 없이 돈다.
reportlab은 개발 의존성이다(서비스 코드는 쓰지 않음).
"""

import argparse
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

sys.path.insert(0, str(Path(__file__).parent))
from fake_pdf_data import DOCS  # noqa: E402

FIXTURES = Path(__file__).parents[1] / "tests" / "unit" / "extract" / "fixtures"
FONT = "KR"


def _cells(row: tuple, columns: list[str]) -> list[str]:
    """줄 하나를 그 문서의 칸 순서대로 글자로."""
    name, birth, place, kind, amount, _ = row
    by_col = {
        "대상자": name,
        "생년월일": birth,
        "기관·가맹점": place,
        "종류": kind,
        "금액": f"{amount:,}",
    }
    return [by_col[c] for c in columns]


def answer(doc: dict) -> dict:
    """정답 JSON(ExtractedDoc 모양). 합계는 PDF에 합계를 그린 그룹만 넣는다."""
    items, totals = [], []
    for group, _title, show_total, rows in doc["sections"]:
        for row in rows:
            name, birth, _place, kind, amount, mark = row
            items.append(
                {
                    "group": group,
                    "kind": kind,
                    "person_name": name,
                    "person_birth": birth,
                    "amount": amount,
                    "source_text": " ".join(c for c in _cells(row, doc["columns"]) if c),
                    "mark": mark,
                }
            )
        if show_total:
            total = sum(r[4] for r in rows if r[5] != "subtract")
            totals.append({"group": group, "amount": total})
    prior = doc["tax_year"] != 2025
    return {
        "tax_year": doc["tax_year"],
        "worker_name": doc["worker"],
        "items": items,
        "totals": totals,
        "prior_year": prior,
        "notes": ["작년 자료: 올해 달라진 값은 대화로 고칩니다"] if prior else [],
    }


def _section_table(doc: dict, rows: list, show_total: bool) -> Table:
    data = [doc["columns"]] + [_cells(r, doc["columns"]) for r in rows]
    if show_total:
        total = sum(r[4] for r in rows if r[5] != "subtract")
        last = ["" for _ in doc["columns"]]
        amount_col = doc["columns"].index("금액")
        # "합계" 글자는 금액 칸이 아닌 첫 칸에 쓴다
        last[1 if amount_col == 0 else 0] = "합계"
        last[amount_col] = f"{total:,}"
        data.append(last)
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    return table


def render(doc: dict, path: Path) -> None:
    title = ParagraphStyle("t", fontName=FONT, fontSize=14, leading=20)
    body = ParagraphStyle("b", fontName=FONT, fontSize=10, leading=14)
    story = [
        Paragraph(f"{doc['tax_year']}년 귀속 소득·세액공제 증명서류(가상 자료)", title),
        Paragraph(f"근로자 성명: {doc['worker']}", body),
        Spacer(1, 10),
    ]
    for _group, heading, show_total, rows in doc["sections"]:
        story += [Paragraph(f"■ {heading}", body), _section_table(doc, rows, show_total)]
        story.append(Spacer(1, 12))
    SimpleDocTemplate(str(path), pagesize=A4, title="가상 간소화 자료").build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", required=True, help="한글 TTF 글꼴 경로(OFL 등)")
    parser.add_argument("--out", type=Path, default=FIXTURES)
    args = parser.parse_args()
    pdfmetrics.registerFont(TTFont(FONT, args.font))
    args.out.mkdir(parents=True, exist_ok=True)
    for doc in DOCS:
        render(doc, args.out / f"{doc['file']}.pdf")
        text = json.dumps(answer(doc), ensure_ascii=False, indent=2) + "\n"
        (args.out / f"{doc['file']}.json").write_text(text, encoding="utf-8")
        print(f"만듦: {doc['file']}.pdf / .json")


if __name__ == "__main__":
    main()
