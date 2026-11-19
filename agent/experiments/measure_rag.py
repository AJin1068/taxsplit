"""근거 적중률을 잰다: 규칙표의 규칙 전부를 질문으로, 방법 3가지 × hit@1·hit@3, 그룹별.

    uv sync --extra rag
    uv run python experiments/measure_rag.py                 # 설정 모델(맥북 CPU)
    uv run python experiments/measure_rag.py --fake          # 가짜 임베딩(모델 없이 흐름만)
    uv run python experiments/measure_rag.py --json out.json

적중 = 돌려받은 조각의 쪽이 그 규칙의 `pages` 중 하나와 같다(여러 쪽이면 하나만 맞아도 적중).
정답 `pages`는 이 측정 명령만 읽는다. 검색(find_evidence)은 읽지 않는다.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from taxsplit.rag.chunks import load_chunks
from taxsplit.rag.embedding import HashEmbedder, make_embedder
from taxsplit.rag.evidence import find_evidence
from taxsplit.rag.search import METHODS
from taxsplit.rag.store import MemoryChunkStore
from taxsplit.rules.loader import GROUPS, load_rules

TAX_YEAR = 2025
K = 3


def _rate(hits: int, total: int) -> float:
    return round(hits / total, 3) if total else 0.0


async def measure(fake: bool, model: str | None) -> dict:
    rules = load_rules(TAX_YEAR)
    # 정답 쪽이 없는 규칙(출처 TODO)은 잴 수 없어 뺀다
    measured = {rid: r for rid, r in rules.items() if r.pages}
    embedder = HashEmbedder(384) if fake else make_embedder(model)
    chunks = load_chunks()

    store = MemoryChunkStore(embedder)
    _ = embedder.dim  # 모델 내려받기·불러오기는 벡터화 시간에서 뺀다
    started = time.perf_counter()
    await store.add(chunks)
    embed_seconds = time.perf_counter() - started

    results: dict[str, dict] = {}
    query_ms: dict[str, float] = {}
    for method in METHODS:
        started = time.perf_counter()
        found = await find_evidence(store, list(measured), TAX_YEAR, K, method, rules)
        query_ms[method] = (time.perf_counter() - started) * 1000 / len(measured)
        rows = {}
        for rid, evidence in found.items():
            got = [e.page for e in evidence]
            answer = set(measured[rid].pages)
            rows[rid] = {
                "group": measured[rid].group,
                "pages": list(measured[rid].pages),
                "got": got,
                "hit@1": bool(got[:1]) and got[0] in answer,
                "hit@3": any(p in answer for p in got[:3]),
            }
        results[method] = rows

    table = {
        method: {
            group: {
                "n": len(g := [r for r in rows.values() if group == "all" or r["group"] == group]),
                "hit@1": _rate(sum(r["hit@1"] for r in g), len(g)),
                "hit@3": _rate(sum(r["hit@3"] for r in g), len(g)),
            }
            for group in (*GROUPS, "all")
        }
        for method, rows in results.items()
    }
    misses = [
        {"rule_id": rid, **{k: v for k, v in row.items() if k in ("group", "pages", "got")}}
        for rid, row in results["hybrid"].items()
        if not row["hit@3"]
    ]
    return {
        "model": "HashEmbedder(fake)" if fake else embedder.model_name,
        "chunks": len(chunks),
        "rules_total": len(rules),
        "rules_measured": len(measured),
        "embed_seconds": round(embed_seconds, 2),
        "query_ms": {m: round(v, 1) for m, v in query_ms.items()},
        "table": table,
        "hybrid_misses_at3": misses,
        "per_rule": results,
    }


def print_markdown(report: dict) -> None:
    print(
        f"모델: {report['model']}, 조각 {report['chunks']}개, "
        f"규칙 {report['rules_measured']}/{report['rules_total']}개 측정"
    )
    print(f"전체 벡터화 {report['embed_seconds']}초, 질문 하나 검색(ms) {report['query_ms']}\n")
    header = "| 그룹 | n | " + " | ".join(f"{m} @1 | {m} @3" for m in METHODS) + " |"
    print(header)
    print("|" + " --- |" * (2 + 2 * len(METHODS)))
    for group in (*GROUPS, "all"):
        cells = [str(report["table"]["hybrid"][group]["n"])]
        for m in METHODS:
            row = report["table"][m][group]
            cells += [f"{row['hit@1']:.0%}", f"{row['hit@3']:.0%}"]
        print(f"| {group} | " + " | ".join(cells) + " |")
    print("\n하이브리드 hit@3에서 틀린 규칙:")
    for miss in report["hybrid_misses_at3"]:
        print(
            f"- {miss['rule_id']} ({miss['group']}): 정답 {miss['pages']} / 찾은 쪽 {miss['got']}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="근거 적중률 측정")
    parser.add_argument("--fake", action="store_true", help="가짜 임베딩으로 흐름만 확인")
    parser.add_argument("--model", default=None, help="설정값 대신 쓸 임베딩 모델 이름")
    parser.add_argument("--json", type=Path, default=None, help="결과 JSON을 쓸 곳")
    args = parser.parse_args()
    report = asyncio.run(measure(args.fake, args.model))
    print_markdown(report)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
