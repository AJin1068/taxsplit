"""평가 하네스 명령: `uv run python -m taxsplit.harness run [옵션]`.

명령 하나로 실행 → 채점 → 결과 JSON 저장 → (--baseline이면) 기준 수치 비교까지 한다.
끝 값: 0 정상 / 1 기준 수치보다 떨어짐 / 2 설정·시나리오 오류.
"""

import argparse
import asyncio
import sys
from collections.abc import Callable
from pathlib import Path

import httpx2

from taxsplit.core.config import get_settings
from taxsplit.harness.results import (
    DROPPED,
    compare,
    comparison_lines,
    default_out,
    summary_lines,
    write_result,
)
from taxsplit.harness.run import HarnessDeps, RunOptions, run_all
from taxsplit.harness.scenarios import ScenarioError, load_scenarios
from taxsplit.harness.scoring import DEFAULT_SCENARIOS
from taxsplit.llm.base import CallKind
from taxsplit.llm.call_log import InMemoryLlmCallRepository
from taxsplit.llm.factory import build_judge_client, build_llm_client, judge_model

# 실제 서버를 부를 때 한 요청 대기 상한(초). 한 턴에 AI 호출이 여러 번이라 길게 둔다(운영값)
HTTP_TIMEOUT = 600.0

type DepsFactory = Callable[[argparse.Namespace], HarnessDeps]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m taxsplit.harness")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="시나리오로 에이전트를 돌리고 채점한다")
    run.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS, help="시나리오 폴더")
    run.add_argument("--repeat", type=int, default=3, help="시나리오마다 반복 수")
    run.add_argument("--only", action="append", help="이 id만 돌림(여러 번 줄 수 있음)")
    run.add_argument("--judge", action="store_true", help="GPT 채점(설명 일치)도 한다")
    run.add_argument("--baseline", type=Path, help="비교할 기준 결과 JSON")
    run.add_argument("--out", type=Path, help="결과 JSON 경로(기본 eval-runs/<날짜>-run.json)")
    run.add_argument("--max-cost-usd", type=float, default=10.0, help="누적 비용 상한(USD)")
    run.add_argument("--base-url", help="떠 있는 서버 주소. 없으면 같은 프로세스에 앱을 띄움")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat는 1 이상이어야 합니다")
    return args


def build_deps(args: argparse.Namespace) -> HarnessDeps:
    """설정값(.env)으로 실제 클라이언트를 만든다. 키·모델이 없으면 ValueError."""
    settings = get_settings()
    judge_llm = build_judge_client(settings) if args.judge else None
    if args.base_url:
        client = httpx2.AsyncClient(base_url=args.base_url, timeout=HTTP_TIMEOUT)
    else:
        from taxsplit.main import create_app

        transport = httpx2.ASGITransport(app=create_app())
        client = httpx2.AsyncClient(transport=transport, base_url="http://harness", timeout=None)
    return HarnessDeps(
        client=client,
        sim_llm=build_llm_client(settings, InMemoryLlmCallRepository()),
        judge_llm=judge_llm,
        models={
            # --base-url이면 그 서버의 설정을 따른다. 여기 적는 것은 이 프로세스의 설정값
            "main_agent": settings.model_for(CallKind.MAIN_AGENT),
            "main_agent_provider": settings.llm_provider,
            "sim_user": settings.model_for(CallKind.SIM_USER),
            "judge": judge_model(settings) if args.judge else None,
        },
    )


async def _run(args: argparse.Namespace, deps: HarnessDeps) -> int:
    scenarios = load_scenarios(args.scenarios, args.only)
    opts = RunOptions(args.scenarios, args.repeat, args.max_cost_usd)
    async with deps.client:
        result = await run_all(scenarios, opts, deps)
    code = 0
    if args.baseline:
        result["baseline_comparison"] = compare(result, args.baseline)
        code = 1 if result["baseline_comparison"]["verdict"] == DROPPED else 0
    out = args.out or default_out("run")
    write_result(result, out)
    for line in summary_lines(result):
        print(line)
    if args.baseline:
        for line in comparison_lines(result["baseline_comparison"]):
            print(line)
    print(f"결과 JSON: {out}")
    return code


def main(argv: list[str] | None = None, deps_factory: DepsFactory = build_deps) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        # 시나리오를 먼저 검사해서, 형식이 틀리면 클라이언트를 만들거나 돈을 쓰기 전에 멈춘다
        load_scenarios(args.scenarios, args.only)
        deps = deps_factory(args)
        return asyncio.run(_run(args, deps))
    except (ScenarioError, ValueError) as e:
        print(f"멈춤: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
