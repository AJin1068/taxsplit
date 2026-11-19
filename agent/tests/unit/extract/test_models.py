"""추출 결과 형식."""

import pytest
from pydantic import ValidationError

from taxsplit.extract.models import ExtractedDoc, ExtractedItem, ExtractionResult


def _item(**kw):
    base = {"group": "card", "kind": "신용카드", "person_name": "가", "amount": 100}
    return {**base, **kw}


def test_item_defaults():
    item = ExtractedItem.model_validate(_item())
    assert item.mark == "none" and item.person_birth is None and item.source_text == ""


@pytest.mark.parametrize(
    "bad",
    [{"amount": -1}, {"amount": "100"}, {"amount": 1.5}, {"group": "bogus"}, {"person_name": " "}],
)
def test_item_rejects_bad_values(bad):
    with pytest.raises(ValidationError):
        ExtractedItem.model_validate(_item(**bad))


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        ExtractedDoc.model_validate(
            {"tax_year": 2025, "worker_name": "가", "items": [], "extra": 1}
        )


def test_failure_sets_json_upload_fallback():
    result = ExtractionResult.failure(["이유"])
    assert not result.ok and result.fallback == "json_upload" and result.doc is None
