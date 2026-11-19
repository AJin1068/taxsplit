from taxsplit.rag.bm25 import BM25, tokenize


def test_tokenize_words_and_bigrams() -> None:
    assert tokenize("의료비는 15%") == ["의료비는", "의료", "료비", "비는", "15"]


def test_particles_still_match() -> None:
    # 조사가 달라도("의료비는" / "의료비를") 2-gram이 겹쳐 점수가 난다
    bm = BM25(["의료비를 지출한 경우", "신용카드 사용금액"])
    scores = bm.scores("의료비는")
    assert scores[0] > 0 and scores[1] == 0


def test_rare_term_weighs_more() -> None:
    docs = ["공제 공제 대상", "공제 의료비", "공제 교육비"]
    scores = BM25(docs).scores("의료비 공제")
    assert scores.index(max(scores)) == 1


def test_empty_docs() -> None:
    assert BM25([]).scores("아무거나") == []
