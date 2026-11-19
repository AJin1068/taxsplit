"""근거 찾기: 계산에 쓴 규칙 ID마다 "신고안내 몇 쪽에 이렇게 적혀 있다"를 찾는다.

검색어는 규칙표의 그 규칙 `summary`(한 줄 설명)와 `statute`(조문)로만 만든다.
규칙표의 `pages`(정답 쪽)는 읽지 않는다. 읽어서 바로 찾아가면 근거 적중률이 의미가 없어진다.
`pages`는 측정 명령(`experiments/measure_rag.py`)과 테스트만 읽는다.
"""

from pydantic import BaseModel, ConfigDict

from taxsplit.rag.search import Method
from taxsplit.rag.store import ChunkStore
from taxsplit.rules.loader import Rule, load_rules

# 화면 근거 칩에 보여 줄 글 일부의 길이(운영값)
SNIPPET_CHARS = 160
DEFAULT_METHOD: Method = "hybrid"


class Evidence(BaseModel):
    """근거 한 줄: 어느 문서 몇 쪽, 글 일부, 점수."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    tax_year: int
    source: str
    page: str
    print_page: int | None
    pdf_page: int | None
    snippet: str
    score: float
    chunk_id: str


def rule_query(rule: Rule) -> str:
    """규칙 하나의 검색어. 정답 쪽(pages)은 넣지 않는다."""
    return f"{rule.summary} {rule.statute}".strip()


def _snippet(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_CHARS else flat[:SNIPPET_CHARS] + "…"


async def find_evidence(
    store: ChunkStore,
    rule_ids: list[str],
    tax_year: int,
    k: int = 3,
    method: Method = DEFAULT_METHOD,
    rules: dict[str, Rule] | None = None,
) -> dict[str, list[Evidence]]:
    """규칙 ID마다 위에서 k개의 근거. 규칙표에 없는 ID면 KeyError."""
    table = rules if rules is not None else load_rules(tax_year)
    out: dict[str, list[Evidence]] = {}
    for rule_id in rule_ids:
        rule = table[rule_id]
        hits = await store.search(rule_query(rule), tax_year, method, k)
        out[rule_id] = [
            Evidence(
                rule_id=rule_id,
                tax_year=h.chunk.tax_year,
                source=h.chunk.source,
                page=h.chunk.page,
                print_page=h.chunk.print_page,
                pdf_page=h.chunk.pdf_page,
                snippet=_snippet(h.chunk.text),
                score=h.score,
                chunk_id=h.chunk.id,
            )
            for h in hits
        ]
    return out
