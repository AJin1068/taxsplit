import math

from taxsplit.core.config import Settings
from taxsplit.rag import HashEmbedder, SentenceTransformerEmbedder


def test_hash_embedder_is_deterministic_and_unit_length() -> None:
    emb = HashEmbedder(32)
    a, b = emb.embed_passages(["의료비 세액공제", "의료비 세액공제"])
    assert a == b
    assert len(a) == 32
    assert math.isclose(sum(v * v for v in a), 1.0)


def test_hash_embedder_similar_texts_are_closer() -> None:
    emb = HashEmbedder(256)
    q, near, far = emb.embed_queries(["의료비 공제", "의료비 세액공제 요건", "신용카드 한도"])
    dot = lambda x, y: sum(i * j for i, j in zip(x, y, strict=True))  # noqa: E731
    assert dot(q, near) > dot(q, far)


class _FakeModel:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, texts, **_kw):
        self.seen.extend(texts)
        return [[1.0, 0.0] for _ in texts]


def test_e5_prefixes_query_and_passage() -> None:
    # 모델을 내려받지 않고 붙는 글자만 본다(테스트는 네트워크가 막혀 있다)
    emb = SentenceTransformerEmbedder("intfloat/multilingual-e5-small")
    emb._model = fake = _FakeModel()
    emb.embed_queries(["질문"])
    emb.embed_passages(["원문"])
    assert fake.seen == ["query: 질문", "passage: 원문"]


def test_non_e5_has_no_prefix() -> None:
    emb = SentenceTransformerEmbedder("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    emb._model = fake = _FakeModel()
    emb.embed_queries(["질문"])
    assert fake.seen == ["질문"]


def test_model_name_is_a_setting(monkeypatch) -> None:
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "some/other-model")
    assert Settings(_env_file=None).rag_embedding_model == "some/other-model"
    monkeypatch.delenv("RAG_EMBEDDING_MODEL")
    assert Settings(_env_file=None).rag_embedding_model == "intfloat/multilingual-e5-small"
    assert Settings(_env_file=None).rag_embedding_dim == 384
