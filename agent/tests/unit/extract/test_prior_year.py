"""작년(2024 귀속) PDF: 귀속연도를 그대로 담고 prior_year와 안내를 붙인다. 금액은 그대로."""

import asyncio
import json

from taxsplit.extract import LlmPdfExtractor
from taxsplit.extract.models import PRIOR_YEAR_NOTE

from .conftest import SequenceLLM, load_answer, load_pdf


def test_prior_year_pdf_keeps_2024_and_flags_it():
    answer = load_answer("doc3_2024")
    reply = {**answer, "prior_year": False, "notes": []}  # AI가 표시를 안 해도 코드가 붙인다
    extractor = LlmPdfExtractor(SequenceLLM([json.dumps(reply, ensure_ascii=False)]))
    result = asyncio.run(extractor.extract(load_pdf("doc3_2024")))
    assert result.ok
    assert result.doc.tax_year == 2024
    assert result.doc.prior_year is True
    assert result.doc.notes == [PRIOR_YEAR_NOTE]
    # 작년 금액을 올해 값으로 바꾸지 않는다
    assert [i.amount for i in result.doc.items] == [i["amount"] for i in answer["items"]]


def test_current_year_pdf_is_not_prior():
    reply = json.dumps(load_answer("doc1_2025"), ensure_ascii=False)
    result = asyncio.run(LlmPdfExtractor(SequenceLLM([reply])).extract(load_pdf("doc1_2025")))
    assert result.ok and result.doc.prior_year is False and result.doc.notes == []
