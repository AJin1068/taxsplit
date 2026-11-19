"""글을 의미 벡터로 바꾸는 임베딩.

- `SentenceTransformerEmbedder`: 서비스·측정용. 맥북 CPU에서 공개 다국어 모델을 돌린다.
  무거운 라이브러리(torch)라 선택 의존성이다: `uv sync --extra rag`.
- `HashEmbedder`: 테스트용 가짜. 글자 2-gram을 해시해 정해진 벡터를 만든다(네트워크·모델 없음).
"""

import hashlib
import math
from typing import Protocol

from taxsplit.rag.bm25 import tokenize


class Embedder(Protocol):
    """질문과 조각을 같은 공간의 벡터로 바꾼다. 벡터는 길이 1로 맞춘다(코사인 = 내적)."""

    @property
    def dim(self) -> int: ...

    def embed_queries(self, texts: list[str]) -> list[list[float]]: ...

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    size = math.sqrt(sum(v * v for v in vec))
    return [v / size for v in vec] if size else vec


class HashEmbedder:
    """테스트용 가짜 임베딩. 같은 글은 언제나 같은 벡터, 단어가 겹칠수록 가까운 벡터."""

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            vec[int.from_bytes(digest) % self._dim] += 1.0
        return _normalize(vec)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class SentenceTransformerEmbedder:
    """sentence-transformers로 공개 모델을 돌린다. 처음 쓸 때 모델을 불러온다."""

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None
        # e5 계열은 질문에 "query: ", 원문에 "passage: "를 붙여야 제 성능이 난다(모델 사용법)
        is_e5 = "e5" in model_name.lower()
        self._query_prefix = "query: " if is_e5 else ""
        self._passage_prefix = "passage: " if is_e5 else ""

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:  # 선택 의존성을 깔지 않았을 때 무엇을 하면 되는지 알려 준다
                raise RuntimeError("임베딩 라이브러리가 없음: `uv sync --extra rag`") from e
            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    @property
    def dim(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        vectors = self._load().encode(
            [prefix + t for t in texts],
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [list(map(float, v)) for v in vectors]

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self._query_prefix)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self._passage_prefix)


def make_embedder(model_name: str | None = None) -> SentenceTransformerEmbedder:
    """설정값(RAG_EMBEDDING_MODEL)의 모델로 임베딩을 만든다."""
    if model_name is None:
        from taxsplit.core.config import get_settings

        model_name = get_settings().rag_embedding_model
    return SentenceTransformerEmbedder(model_name)
