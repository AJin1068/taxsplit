"""Postgres + pgvector 조각 저장소(서비스용). 표는 마이그레이션 0002가 만든다.

- 의미 검색: DB가 `embedding <=> 질문벡터`(코사인 거리)로 가까운 순서를 낸다.
- 키워드 검색: 같은 연도 조각을 불러 메모리 BM25로 돈다. 메모리 저장소와 같은 점수를 내게 하려고
  DB 전문 검색(tsvector)은 쓰지 않는다(69쪽 규모라 충분히 빠르다).
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.asyncio import AsyncEngine

from taxsplit.rag.chunks import Chunk
from taxsplit.rag.embedding import Embedder
from taxsplit.rag.search import CANDIDATES, Hit, Method, keyword_search, rrf

_meta = sa.MetaData()


def chunk_table(dim: int) -> sa.Table:
    """rag_chunks 표 모양. 마이그레이션 0002와 칸 이름이 같아야 한다."""
    return sa.Table(
        "rag_chunks",
        _meta,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("tax_year", sa.Integer, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("page", sa.Text, nullable=False),
        sa.Column("print_page", sa.Integer, nullable=True),
        sa.Column("pdf_page", sa.Integer, nullable=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(dim), nullable=False),
        extend_existing=True,
    )


_CHUNK_COLS = ("id", "tax_year", "source", "page", "print_page", "pdf_page", "seq", "text")


class PgVectorChunkStore:
    def __init__(self, engine: AsyncEngine, embedder: Embedder, dim: int) -> None:
        self.engine = engine
        self.embedder = embedder
        self.table = chunk_table(dim)

    async def add(self, chunks: list[Chunk]) -> None:
        """조각을 넣는다. 같은 id가 있으면 지우고 다시 넣는다(적재 명령을 여러 번 돌려도 같게)."""
        if not chunks:
            return
        vectors = self.embedder.embed_passages([c.text for c in chunks])
        rows = [
            {**c.model_dump(include=set(_CHUNK_COLS)), "embedding": v}
            for c, v in zip(chunks, vectors, strict=True)
        ]
        async with self.engine.begin() as conn:
            await conn.execute(
                sa.delete(self.table).where(self.table.c.id.in_([c.id for c in chunks]))
            )
            await conn.execute(sa.insert(self.table), rows)

    async def _rows(self, stmt: sa.Select) -> list[Chunk]:
        async with self.engine.connect() as conn:
            result = await conn.execute(stmt)
            return [Chunk.model_validate(dict(r._mapping)) for r in result]

    def _select(self, tax_year: int) -> sa.Select:
        cols = [self.table.c[name] for name in _CHUNK_COLS]
        # 연도 거르기가 먼저(WHERE). 정렬·점수는 그 안에서만
        return sa.select(*cols).where(self.table.c.tax_year == tax_year)

    async def _vector(self, query: str, tax_year: int, k: int) -> list[Hit]:
        query_vec = self.embedder.embed_queries([query])[0]
        distance = self.table.c.embedding.cosine_distance(query_vec)
        stmt = self._select(tax_year).add_columns(distance.label("d")).order_by(distance).limit(k)
        async with self.engine.connect() as conn:
            result = await conn.execute(stmt)
            return [
                Hit(
                    chunk=Chunk.model_validate({c: r._mapping[c] for c in _CHUNK_COLS}),
                    score=1.0 - float(r._mapping["d"]),
                )
                for r in result
            ]

    async def search(self, query: str, tax_year: int, method: Method, k: int) -> list[Hit]:
        if method == "vector":
            return await self._vector(query, tax_year, k)
        chunks = await self._rows(self._select(tax_year).order_by(self.table.c.id))
        keyword = keyword_search(chunks, query, CANDIDATES if method == "hybrid" else k)
        if method == "keyword":
            return keyword
        return rrf([keyword, await self._vector(query, tax_year, CANDIDATES)], k)
