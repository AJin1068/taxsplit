"""근거 검색(RAG의 검색 부분). 규칙마다 신고안내의 근거 쪽을 찾는다(PRD FR-05)."""

from taxsplit.rag.chunks import BOOKLET_PATH, Chunk, Page, load_chunks, load_pages, split_page
from taxsplit.rag.embedding import Embedder, HashEmbedder, SentenceTransformerEmbedder
from taxsplit.rag.evidence import Evidence, find_evidence, rule_query
from taxsplit.rag.search import METHODS, Hit, Method
from taxsplit.rag.store import ChunkStore, MemoryChunkStore

__all__ = [
    "BOOKLET_PATH",
    "METHODS",
    "Chunk",
    "ChunkStore",
    "Embedder",
    "Evidence",
    "HashEmbedder",
    "Hit",
    "MemoryChunkStore",
    "Method",
    "Page",
    "SentenceTransformerEmbedder",
    "find_evidence",
    "load_chunks",
    "load_pages",
    "rule_query",
    "split_page",
]
