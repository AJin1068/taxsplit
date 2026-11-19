"""검색 3가지: 키워드(BM25), 의미(벡터), 둘을 합친 하이브리드(RRF).

여기 함수들은 "이미 귀속연도로 거른 조각 목록"을 받아 순위만 매긴다.
연도 거르기는 저장소(store)가 점수를 매기기 전에 한다(설계 원칙 3).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from taxsplit.rag.bm25 import BM25
from taxsplit.rag.chunks import Chunk

Method = Literal["keyword", "vector", "hybrid"]
METHODS: tuple[Method, ...] = ("keyword", "vector", "hybrid")

# RRF 상수. 원 논문(Cormack 2009)의 기본값 60(운영값, 세법 숫자 아님)
RRF_K = 60
# 하이브리드가 합치기 전에 각 방법에서 가져오는 후보 수
CANDIDATES = 50


class Hit(BaseModel):
    """검색 결과 한 줄: 조각과 점수(방법마다 점수 단위가 다르다)."""

    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    score: float


def _top(chunks: list[Chunk], scores: list[float], k: int) -> list[Hit]:
    # 점수가 같으면 원래 순서(쪽 순서)를 지켜 결과가 매번 같게 한다
    order = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))
    return [Hit(chunk=chunks[i], score=scores[i]) for i in order[:k]]


def keyword_search(chunks: list[Chunk], query: str, k: int) -> list[Hit]:
    """BM25 점수로 위에서 k개. 점수 0(겹치는 단어 없음)은 뺀다."""
    if not chunks:
        return []
    hits = _top(chunks, BM25([c.text for c in chunks]).scores(query), k)
    return [h for h in hits if h.score > 0]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def vector_search(
    chunks: list[Chunk], vectors: list[list[float]], query_vec: list[float], k: int
) -> list[Hit]:
    """코사인 유사도(길이 1 벡터의 내적)로 위에서 k개."""
    return _top(chunks, [_dot(v, query_vec) for v in vectors], k)


def rrf(rankings: list[list[Hit]], k: int, rrf_k: int = RRF_K) -> list[Hit]:
    """여러 순위를 합친다. 조각 점수 = Σ 1/(rrf_k + 순위). 순위는 1부터."""
    scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}
    first_seen: dict[str, int] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            cid = hit.chunk.id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
            chunks.setdefault(cid, hit.chunk)
            first_seen.setdefault(cid, len(first_seen))
    order = sorted(scores, key=lambda c: (-scores[c], first_seen[c]))
    return [Hit(chunk=chunks[c], score=scores[c]) for c in order[:k]]


def hybrid_search(
    chunks: list[Chunk], vectors: list[list[float]], query: str, query_vec: list[float], k: int
) -> list[Hit]:
    """키워드 후보와 벡터 후보를 RRF로 합쳐 위에서 k개."""
    return rrf(
        [
            keyword_search(chunks, query, CANDIDATES),
            vector_search(chunks, vectors, query_vec, CANDIDATES),
        ],
        k,
    )
