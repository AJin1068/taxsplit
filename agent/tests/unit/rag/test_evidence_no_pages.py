"""근거 찾기는 규칙표의 pages(정답 쪽)를 읽지 않는다: pages를 비워도 결과가 같다."""

import asyncio

import pytest

from taxsplit.rag import METHODS, find_evidence, rule_query


def _without_pages(rules):
    return {rid: r.model_copy(update={"pages": ()}) for rid, r in rules.items()}


@pytest.mark.parametrize("method", METHODS)
def test_same_result_without_pages(booklet_store, rules_2025, method) -> None:
    ids = list(rules_2025)
    with_pages = asyncio.run(find_evidence(booklet_store, ids, 2025, 3, method, rules_2025))
    blank = _without_pages(rules_2025)
    without = asyncio.run(find_evidence(booklet_store, ids, 2025, 3, method, blank))
    assert with_pages == without


def test_query_uses_summary_and_statute_only(rules_2025) -> None:
    for rule in rules_2025.values():
        query = rule_query(rule)
        assert rule.summary in query
        for page in rule.pages:
            assert page not in query.replace(rule.summary, "").replace(rule.statute, "")


def test_evidence_shape(booklet_store, rules_2025) -> None:
    rid = next(iter(rules_2025))
    found = asyncio.run(find_evidence(booklet_store, [rid], 2025, k=3, rules=rules_2025))
    assert list(found) == [rid]
    assert len(found[rid]) == 3
    for ev in found[rid]:
        assert ev.rule_id == rid and ev.tax_year == 2025
        assert ev.source.startswith("2025년")
        assert ev.page and ev.snippet and ev.chunk_id


def test_unknown_rule_id_is_error(booklet_store, rules_2025) -> None:
    with pytest.raises(KeyError):
        asyncio.run(find_evidence(booklet_store, ["2025.base.nope"], 2025, rules=rules_2025))
