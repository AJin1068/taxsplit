"""실제 AI(기본 Haiku)로 가상 PDF 3개를 추출해 그룹별 일치율·비용·시간을 잰다.

    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... uv run python experiments/measure_extract.py

돈이 드는 호출이라 LLM_PROVIDER=anthropic일 때만 돈다(PDF 3개 합쳐 미화 몇 센트).
보내는 것은 가상 가구 자료뿐이다. 정답 JSON은 이 측정 명령만 읽는다(추출 코드는 읽지 않음).
일치 = 그룹·대상자·금액이 모두 같은 항목. 같은 줄이 두 번이면 두 번 맞아야 한다.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

from taxsplit.extract import DEFAULT_PDF_MODEL, LlmPdfExtractor
from taxsplit.extract.models import GROUP_LABELS
from taxsplit.llm.anthropic_client import AnthropicLLMClient
from taxsplit.llm.base import LLMRequest, LLMResponse
from taxsplit.llm.pricing import cost_usd

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "unit" / "extract" / "fixtures"
DOC_NAMES = ["doc1_2025", "doc2_2025_layout", "doc3_2024"]


class CountingClient:
    """호출마다 답(토큰 수)을 모아 비용을 낸다. 추출기는 이 래퍼를 그냥 LLMClient로 본다."""

    def __init__(self, inner: AnthropicLLMClient) -> None:
        self.inner = inner
        self.responses: list[LLMResponse] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        response = await self.inner.complete(request)
        self.responses.append(response)
        return response

    def stream(self, request: LLMRequest):  # 추출기는 쓰지 않는다
        return self.inner.stream(request)

    def cost(self) -> Decimal:
        costs = [cost_usd("anthropic", r.model, r.usage) for r in self.responses]
        return sum((c or Decimal(0) for c in costs), Decimal(0))


def _keys(items: list[dict]) -> Counter:
    return Counter((i["group"], i["person_name"], i["amount"]) for i in items)


def score(expected: list[dict], got: list[dict]) -> dict[str, tuple[int, int]]:
    """그룹별 (맞은 항목 수, 정답 항목 수)."""
    hit = _keys(expected) & _keys(got)
    out = {}
    for group in GROUP_LABELS:
        total = sum(n for (g, _, _), n in _keys(expected).items() if g == group)
        out[group] = (sum(n for (g, _, _), n in hit.items() if g == group), total)
    return out


async def measure_one(name: str, client: CountingClient, model: str) -> dict:
    expected = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    pdf = (FIXTURES / f"{name}.pdf").read_bytes()
    start = time.perf_counter()
    result = await LlmPdfExtractor(client, model=model).extract(pdf)
    seconds = time.perf_counter() - start
    got = [i.model_dump() for i in result.doc.items] if result.doc else []
    groups = score(expected["items"], got)
    exact = result.ok and _keys(expected["items"]) == _keys(got)
    return {
        "doc": name,
        "ok": result.ok,
        "errors": result.errors,
        "groups": groups,
        "all_match": exact,
        "extra_items": sum((_keys(got) - _keys(expected["items"])).values()),
        "tax_year": result.doc.tax_year if result.doc else None,
        "prior_year": result.doc.prior_year if result.doc else None,
        "calls": len(client.responses),
        "cost_usd": float(client.cost()),
        "seconds": round(seconds, 1),
    }


def to_markdown(rows: list[dict], model: str) -> str:
    head = ["문서"] + [GROUP_LABELS[g] for g in GROUP_LABELS]
    head += ["전체 일치", "남는 항목", "귀속연도", "prior_year", "호출", "비용(USD)", "시간(초)"]
    lines = [f"모델: `{model}`", "", "| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    for r in rows:
        cells = [r["doc"]]
        cells += [f"{h}/{t}" if t else "-" for h, t in r["groups"].values()]
        cells += ["예" if r["all_match"] else "아니오", str(r["extra_items"]), str(r["tax_year"])]
        cells += [str(r["prior_year"]).lower(), str(r["calls"])]
        cells += [f"{r['cost_usd']:.4f}", f"{r['seconds']:.1f}"]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL_PDF_EXTRACT") or None)
    parser.add_argument("--out", type=Path, help="결과 JSON을 쓸 경로(선택)")
    args = parser.parse_args()
    if os.environ.get("LLM_PROVIDER") != "anthropic" or not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("LLM_PROVIDER=anthropic과 ANTHROPIC_API_KEY가 있어야 돈다(돈이 드는 호출)")
    model = args.model or DEFAULT_PDF_MODEL
    inner = AnthropicLLMClient(
        api_key=os.environ["ANTHROPIC_API_KEY"], read_timeout=180, total_timeout=300
    )
    rows = []
    for name in DOC_NAMES:
        rows.append(await measure_one(name, CountingClient(inner), model))
        for err in rows[-1]["errors"]:
            print(f"[{name}] 실패 이유: {err}", file=sys.stderr)
    print(to_markdown(rows, model))
    if args.out:
        args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
