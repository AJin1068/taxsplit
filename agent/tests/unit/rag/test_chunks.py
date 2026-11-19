from taxsplit.rag import BOOKLET_PATH, Page, load_chunks, load_pages, split_page
from taxsplit.rag.chunks import CHUNK_SIZE, dump_pages, split_text


def _page(text: str, **kw) -> Page:
    base = {"id": "doc-p1", "tax_year": 2025, "source": "문서", "page": "p1", "print_page": 1}
    return Page(**{**base, **kw, "text": text})


def test_booklet_has_69_pages_of_2025() -> None:
    pages = load_pages(BOOKLET_PATH)
    assert len(pages) == 69
    assert {p.tax_year for p in pages} == {2025}


def test_every_rule_has_an_answer_page_in_booklet(rules_2025) -> None:
    # 정답 쪽이 하나도 원문에 없으면 그 규칙은 적중률을 잴 수 없다(측정 전제 확인).
    # 규칙의 쪽 일부가 원문에 없는 것(예: p44)은 원문 파일을 늘리는 기획 Issue로 넘긴다
    booklet = {p.page for p in load_pages()}
    for rule in rules_2025.values():
        if rule.pages:
            assert booklet & set(rule.pages), rule.id


def test_chunks_never_cross_pages_and_keep_metadata() -> None:
    pages = {p.id: p for p in load_pages()}
    chunks = load_chunks()
    assert len(chunks) >= len(pages)
    for c in chunks:
        page = pages[c.id.rsplit("-c", 1)[0]]
        assert (c.page, c.tax_year, c.source) == (page.page, page.tax_year, page.source)
        assert 0 < len(c.text) <= CHUNK_SIZE


def test_short_paragraphs_are_merged() -> None:
    chunks = split_page(_page("첫 문단\n\n둘째 문단\n\n셋째 문단"))
    assert len(chunks) == 1
    assert chunks[0].text == "첫 문단\n\n둘째 문단\n\n셋째 문단"
    assert chunks[0].id == "doc-p1-c0"


def test_layout_spaces_are_collapsed() -> None:
    assert split_text("의료비      세액공제\n   15%") == ["의료비 세액공제\n15%"]


def test_long_paragraph_is_split_with_overlap() -> None:
    text = "가" * 450 + "나" * 450
    pieces = split_text(text, size=500, overlap=100)
    assert [len(p) for p in pieces] == [500, 500]
    assert pieces[0][-100:] == pieces[1][:100]


def test_paragraphs_overflow_to_next_chunk() -> None:
    text = "가" * 300 + "\n\n" + "나" * 300
    assert split_text(text, size=500, overlap=100) == ["가" * 300, "나" * 300]


def test_dump_and_load_roundtrip(tmp_path) -> None:
    pages = [_page("하나"), _page("둘", id="doc-p2", page="p2", tax_year=2024)]
    path = tmp_path / "x.jsonl"
    path.write_text(dump_pages(pages), encoding="utf-8")
    assert load_pages(path) == pages
