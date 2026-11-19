"""적재 명령: 원문 파일 → 조각 → 벡터 → Postgres(rag_chunks 표).

    uv sync --extra rag
    uv run alembic upgrade head
    uv run python -m taxsplit.rag.load                     # 적재
    uv run python -m taxsplit.rag.load --search "의료비 세액공제" --year 2025   # 적재 뒤 검색 한 번

DB 주소는 설정값(DATABASE_URL), 모델은 RAG_EMBEDDING_MODEL에서 읽는다.
"""

import argparse
import asyncio
import time
from pathlib import Path

from taxsplit.core.config import get_settings
from taxsplit.db.engine import make_engine
from taxsplit.rag.chunks import BOOKLET_PATH, load_chunks
from taxsplit.rag.embedding import make_embedder
from taxsplit.rag.pg_store import PgVectorChunkStore
from taxsplit.rag.search import METHODS


async def main(path: Path, query: str | None, year: int, method: str) -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    store = PgVectorChunkStore(engine, make_embedder(), settings.rag_embedding_dim)
    try:
        chunks = load_chunks(path)
        started = time.perf_counter()
        await store.add(chunks)
        print(f"적재: 조각 {len(chunks)}개, {time.perf_counter() - started:.1f}초 ({path.name})")
        if query:
            started = time.perf_counter()
            hits = await store.search(query, year, method, 3)  # type: ignore[arg-type]
            elapsed = (time.perf_counter() - started) * 1000
            print(f"검색({method}, {year}년): {query!r} → {elapsed:.0f}ms")
            for h in hits:
                text = " ".join(h.chunk.text.split())[:80]
                print(f"  {h.chunk.page:>8}  {h.score:.4f}  {text}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="근거 원문을 Postgres에 적재")
    parser.add_argument("--path", type=Path, default=BOOKLET_PATH)
    parser.add_argument("--search", default=None, help="적재 뒤 검색해 볼 질문")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--method", choices=METHODS, default="hybrid")
    args = parser.parse_args()
    asyncio.run(main(args.path, args.search, args.year, args.method))
