"""고정 가상 PDF에서 글자가 뽑히나(AI 없이)."""

import pytest

from taxsplit.extract.text import has_text, pdf_text, render_pages

from .conftest import DOC_NAMES, load_answer, load_pdf


@pytest.mark.parametrize("name", DOC_NAMES)
def test_every_answer_amount_is_in_pdf_text(name):
    # 정답의 대상자 이름과 금액 글자가 뽑은 글에 모두 보여야 AI가 옮길 수 있다
    text = render_pages(pdf_text(load_pdf(name)))
    answer = load_answer(name)
    assert answer["worker_name"] in text
    for item in answer["items"]:
        assert item["person_name"] in text
        assert f"{item['amount']:,}" in text


def test_layout_doc_spans_two_pages_and_tables_are_extracted():
    pages = pdf_text(load_pdf("doc2_2025_layout"))
    assert len(pages) >= 2
    assert all(p.tables for p in pages)
    assert "2쪽" in render_pages(pages)


def test_broken_pdf_raises_value_error():
    with pytest.raises(ValueError, match="PDF를 열 수 없습니다"):
        pdf_text(b"not a pdf")


def test_has_text_false_for_blank_pages():
    from taxsplit.extract.text import PageText

    assert not has_text([PageText(page=1, text="  ", tables=[])])
