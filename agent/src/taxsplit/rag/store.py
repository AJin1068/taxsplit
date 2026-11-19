"""조각 저장소. 메모리 저장소(테스트·측정용)와 같은 모양으로 Postgres 저장소(`pg_store.py`)가 있다.

모든 검색은 `tax_year`가 필수 인자이고, 점수를 매기기 전에 그 연도 조각만 남긴다.
그래서 다른 연도 글이 결과에 섞일 길이 없다(설계 원칙 3).
"""

from typing import Protocol

from taxsplit.rag.chunks import Chunk
from taxsplit.rag.embedding import Embedder
from taxsplit.rag.search import Hit, Method, hybrid_search, keyword_search, vector_search


class ChunkStore(Protocol):
    async def add(self, chunks: list[Chunk]) -> None: ...

    async def search(self, query: str, tax_year: int, method: Method, k: int) -> list[Hit]: ...


class MemoryChunkStore:
    """조각과 벡터를 메모리에 둔다. 69쪽 규모면 매 검색마다 전부 훑어도 빠르다."""

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    async def add(self, chunks: list[Chunk]) -> None:
        self._chunks.extend(chunks)
        self._vectors.extend(self.embedder.embed_passages([c.text for c in chunks]))

    def __len__(self) -> int:
        return len(self._chunks)

    def _year(self, tax_year: int) -> tuple[list[Chunk], list[list[float]]]:
        # 연도 거르기가 먼저: 이 뒤의 순위 매기기는 이 연도 조각만 본다
        pairs = [(c, v) for c, v in zip(self._chunks, self._vectors, strict=True)]
        kept = [(c, v) for c, v in pairs if c.tax_year == tax_year]
        return [c for c, _ in kept], [v for _, v in kept]

    async def search(self, query: str, tax_year: int, method: Method, k: int) -> list[Hit]:
        chunks, vectors = self._year(tax_year)
        if method == "keyword":
            return keyword_search(chunks, query, k)
        query_vec = self.embedder.embed_queries([query])[0]
        if method == "vector":
            return vector_search(chunks, vectors, query_vec, k)
        return hybrid_search(chunks, vectors, query, query_vec, k)
