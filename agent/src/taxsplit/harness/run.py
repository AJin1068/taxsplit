"""시나리오 전체를 반복 수만큼 하나씩 돌리고, 채점해 결과 dict를 만든다.

비용 상한: 누적 비용(메인 에이전트 + 가상 사용자 + 채점)이 상한 이상이면 새 대화를 시작하지 않는다.
비용을 모르는 호출(None)은 0으로 더한다(상한 판단용). 결과 JSON의 비용 칸은 None 그대로 둔다.
"""

import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2

from taxsplit.harness.judge import judge
from taxsplit.harness.runner import run_conversation
from taxsplit.harness.scenarios import public_view
from taxsplit.harness.scoring import REPO_ROOT, score_module
from taxsplit.llm.base import LLMClient


@dataclass
class HarnessDeps:
    """실행에 필요한 바깥 것들. 명령은 설정값으로 만들고, 테스트는 가짜를 넣는다."""

    client: httpx2.AsyncClient  # 채팅 API를 부르는 HTTP 클라이언트(같은 프로세스 또는 --base-url)
    sim_llm: LLMClient
    judge_llm: LLMClient | None
    models: dict[str, str | None]


@dataclass
class RunOptions:
    scenarios_dir: Path
    repeat: int = 3
    max_cost_usd: float = 10.0


def _commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except OSError, subprocess.CalledProcessError:
        return None
    return out.stdout.strip() or None


def _sum(values: list[float | None]) -> float | None:
    return None if any(v is None for v in values) else sum(v for v in values if v is not None)


def _spent(records: list[dict[str, Any]]) -> float:
    return sum(v or 0 for r in records for v in r["cost"].values())


async def run_all(
    scenarios: list[dict[str, Any]], opts: RunOptions, deps: HarnessDeps
) -> dict[str, Any]:
    started, t0 = datetime.now(UTC), time.monotonic()
    records: list[dict[str, Any]] = []
    stopped_by_cap = False
    for repeat in range(1, opts.repeat + 1):
        for scenario in scenarios:
            if _spent(records) >= opts.max_cost_usd:
                stopped_by_cap = True
                break
            # 실행기·가상 사용자에게는 기준 정답을 뺀 시나리오만 준다
            conv = await run_conversation(deps.client, public_view(scenario), repeat, deps.sim_llm)
            record = conv.record()
            if deps.judge_llm is not None and conv.allocation is not None:
                verdict = await judge(
                    deps.judge_llm, conv.answer_after_allocation or "", conv.allocation
                )
                record["judge"] = {"consistent": verdict.consistent, "reason": verdict.reason}
                record["cost"]["judge_usd"] = (
                    None if verdict.cost_usd is None else float(verdict.cost_usd)
                )
            records.append(record)
        if stopped_by_cap:
            break

    summary = score_module().summarize(scenarios, records)
    costs = {
        k: _sum([r["cost"][k] for r in records])
        for k in ("main_agent_usd", "sim_user_usd", "judge_usd")
    }
    if deps.judge_llm is None:
        costs["judge_usd"] = 0.0
    return {
        "started_at": started.isoformat(timespec="seconds"),
        "elapsed_seconds": round(time.monotonic() - t0, 1),
        "commit": _commit(),
        "models": deps.models,
        "scenarios": {
            "folder": str(opts.scenarios_dir),
            "versions": sorted({s["version"] for s in scenarios}),
            "ids": [s["id"] for s in scenarios],
        },
        "repeat": opts.repeat,
        "judge": deps.judge_llm is not None,
        "max_cost_usd": opts.max_cost_usd,
        "stopped_by_cost_cap": stopped_by_cap,
        # 1회 실행 비용. 메인 에이전트·가상 사용자·채점 따로(모르면 null)
        "cost": {**costs, "total_usd": _sum(list(costs.values()))},
        "records": records,
        "summary": summary,
    }
