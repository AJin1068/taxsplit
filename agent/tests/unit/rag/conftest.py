import asyncio

import pytest

from taxsplit.rag import HashEmbedder, MemoryChunkStore, load_chunks
from taxsplit.rules.loader import load_rules


@pytest.fixture(scope="module")
def booklet_store() -> MemoryChunkStore:
    # 실제 원문(2025 신고안내 69쪽) + 가짜 임베딩. 모델·네트워크 없이 돈다
    store = MemoryChunkStore(HashEmbedder(64))
    asyncio.run(store.add(load_chunks()))
    return store


@pytest.fixture(scope="module")
def rules_2025():
    return load_rules(2025)
