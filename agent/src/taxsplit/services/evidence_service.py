"""근거 찾기를 에이전트 루프에 붙이는 곳. 원문 조각을 메모리 저장소에 한 번 올려 두고 쓴다.

storage=postgres여도 v1은 메모리 근거 저장소로 충분하다(Issue #19 정해진 결정).
"""

import asyncio
import importlib.util
import logging
from typing import Any

from taxsplit.rag.chunks import load_chunks
from taxsplit.rag.embedding import Embedder, HashEmbedder, make_embedder
from taxsplit.rag.evidence import find_evidence
from taxsplit.rag.search import Method
from taxsplit.rag.store import ChunkStore, MemoryChunkStore
from taxsplit.rules.loader import Rule

logger = logging.getLogger("taxsplit.evidence")

TAX_YEAR = 2025
# 규칙 ID마다 보여 줄 근거 수(운영값)
EVIDENCE_K = 3


def default_method(configured: Method | None) -> Method:
    """설정이 비면: 선택 의존성(--extra rag)이 있으면 hybrid, 없으면 keyword."""
    if configured is not None:
        return configured
    has_rag = importlib.util.find_spec("sentence_transformers") is not None
    return "hybrid" if has_rag else "keyword"


def embedder_for(method: Method, model_name: str) -> Embedder:
    # keyword는 벡터를 쓰지 않으므로 가벼운 가짜 임베딩으로 저장소만 채운다
    return HashEmbedder() if method == "keyword" else make_embedder(model_name)


class EvidenceService:
    def __init__(
        self,
        rules: dict[str, Rule],
        method: Method,
        store: ChunkStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._rules = rules
        self._method = method
        self._store = store
        self._embedder = embedder
        self._lock = asyncio.Lock()

    async def _ready_store(self) -> ChunkStore:
        # 처음 부를 때 한 번만 원문을 올린다(앱 시작을 느리게 하지 않게)
        async with self._lock:
            if self._store is None:
                store = MemoryChunkStore(self._embedder or HashEmbedder())
                await store.add(load_chunks())
                self._store = store
        return self._store

    async def __call__(self, rule_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """규칙 ID마다 근거 위 3개. 실패하면 빈 dict(답은 그대로 보낸다)."""
        try:
            store = await self._ready_store()
            found = await find_evidence(
                store, rule_ids, TAX_YEAR, k=EVIDENCE_K, method=self._method, rules=self._rules
            )
        except Exception:
            logger.exception("근거 찾기 실패: %s", rule_ids)
            return {}
        return {rid: [e.model_dump(mode="json") for e in items] for rid, items in found.items()}
