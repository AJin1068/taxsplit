"""귀속연도 필터: 가짜 2024 조각을 섞어도 2025로 검색하면 2024 조각이 0개(설계 원칙 3)."""

import asyncio

import pytest

from taxsplit.rag import METHODS, HashEmbedder, MemoryChunkStore, load_chunks

QUERIES = ["의료비 세액공제 총급여액 3%", "신용카드 소득공제 한도", "기본공제 대상자 연령 요건"]


@pytest.fixture(scope="module")
def mixed_store() -> MemoryChunkStore:
    real = load_chunks()
    # 2025 조각과 글이 똑같은 2024 가짜 조각: 점수가 동점이라 필터가 없으면 반드시 섞인다
    fake_2024 = [c.model_copy(update={"id": f"{c.id}-y2024", "tax_year": 2024}) for c in real]
    store = MemoryChunkStore(HashEmbedder(64))
    asyncio.run(store.add(fake_2024 + real))  # 2024를 앞에 넣어 동점이면 2024가 먼저 나올 자리
    return store


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("query", QUERIES)
def test_2025_search_returns_no_2024_chunks(mixed_store, method, query) -> None:
    hits = asyncio.run(mixed_store.search(query, 2025, method, 10))
    assert hits
    assert {h.chunk.tax_year for h in hits} == {2025}


@pytest.mark.parametrize("method", METHODS)
def test_2024_search_returns_only_2024(mixed_store, method) -> None:
    hits = asyncio.run(mixed_store.search(QUERIES[0], 2024, method, 10))
    assert hits
    assert all(h.chunk.id.endswith("-y2024") for h in hits)


@pytest.mark.parametrize("method", METHODS)
def test_year_without_documents_returns_nothing(mixed_store, method) -> None:
    assert asyncio.run(mixed_store.search(QUERIES[0], 2023, method, 3)) == []
