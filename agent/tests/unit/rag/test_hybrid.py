import asyncio

import pytest

from taxsplit.rag import Chunk, HashEmbedder, Hit, MemoryChunkStore
from taxsplit.rag.search import RRF_K, rrf


def _chunk(cid: str, text: str = "글") -> Chunk:
    return Chunk(id=cid, tax_year=2025, source="문서", page=f"p{cid}", seq=0, text=text)


def _hits(*ids: str) -> list[Hit]:
    return [Hit(chunk=_chunk(i), score=0.0) for i in ids]


def test_rrf_scores_are_sum_of_reciprocal_ranks() -> None:
    merged = rrf([_hits("1", "2"), _hits("2", "3")], k=3)
    assert [h.chunk.id for h in merged] == ["2", "1", "3"]
    assert merged[0].score == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))
    assert merged[1].score == pytest.approx(1 / (RRF_K + 1))


def test_rrf_cuts_to_k() -> None:
    assert len(rrf([_hits("1", "2", "3")], k=2)) == 2


def test_hybrid_finds_what_either_method_finds() -> None:
    chunks = [
        _chunk("1", "의료비 세액공제는 총급여액의 3%를 넘는 금액"),
        _chunk("2", "신용카드 등 사용금액 소득공제 한도"),
        _chunk("3", "교육비 세액공제 대상 교육기관"),
    ]
    store = MemoryChunkStore(HashEmbedder(128))
    asyncio.run(store.add(chunks))
    for method in ("keyword", "vector", "hybrid"):
        hits = asyncio.run(store.search("의료비 세액공제", 2025, method, 1))
        assert hits[0].chunk.id == "1", method


def test_keyword_search_drops_zero_scores() -> None:
    store = MemoryChunkStore(HashEmbedder(16))
    asyncio.run(store.add([_chunk("1", "의료비"), _chunk("2", "신용카드")]))
    hits = asyncio.run(store.search("의료비", 2025, "keyword", 5))
    assert [h.chunk.id for h in hits] == ["1"]
