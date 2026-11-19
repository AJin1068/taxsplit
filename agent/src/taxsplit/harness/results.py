"""결과 JSON 쓰기와 기준 수치 비교 출력.

비교 판정은 eval/scoring/score.py compare_to_baseline이 한다(규칙: eval/scoring/rules.md).
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

from taxsplit.harness.scoring import score_module

RESULTS_DIR = Path(__file__).resolve().parents[3] / "eval-runs"
DROPPED = "떨어짐"


def default_out(name: str, today: date | None = None) -> Path:
    """agent/eval-runs/<YYYY-MM-DD>-<이름>.json. 이미 있으면 -2, -3…을 붙여 덮어쓰지 않는다."""
    stem = f"{(today or date.today()).isoformat()}-{name}"
    path = RESULTS_DIR / f"{stem}.json"
    n = 2
    while path.exists():
        path = RESULTS_DIR / f"{stem}-{n}.json"
        n += 1
    return path


def write_result(result: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compare(result: dict[str, Any], baseline_path: Path) -> dict[str, Any]:
    """기준 결과 JSON(이 명령이 쓴 파일)과 비교한다. 비용 늘어남은 경고로만 붙는다."""
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if "summary" not in baseline:
        raise ValueError(f"{baseline_path.name}: summary 칸이 없는 결과 JSON입니다")
    out = score_module().compare_to_baseline(result["summary"], baseline["summary"])
    out["baseline"] = str(baseline_path)
    return out


def comparison_lines(cmp: dict[str, Any]) -> list[str]:
    lines = [f"기준 수치 비교: {cmp['verdict']}"]
    lines += [f"  - {r}" for r in cmp["reasons"]]
    if cmp["cost_warning"]:
        lines.append("  - 비용 늘어남(경고): 대화당 비용이 기준의 1.5배를 넘음")
    return lines


def _pct(value: float | None) -> str:
    return "알 수 없음" if value is None else f"{value * 100:.1f}%"


def summary_lines(result: dict[str, Any]) -> list[str]:
    """사람이 터미널에서 보는 요약. 숫자는 summary 그대로 옮긴다."""
    o = result["summary"]["overall"]
    cost = o["cost_per_conversation_usd"]
    lines = [
        f"대화 {o['conversations']}개 (시나리오 {len(result['scenarios']['ids'])}개)",
        f"배분안 일치율 {_pct(o['match_rate'])}",
        f"누락 질문 비율 {_pct(o['missed_question_rate'])}",
        f"잘못된 인자 비율 {_pct(o['invalid_args_rate'])}",
        f"순서 위반 {o['order_violations']}회",
        f"대화당 비용 {'알 수 없음' if cost is None else f'${cost:.4f}'}",
    ]
    for g, n in result["summary"]["by_group"].items():
        lines.append(f"  그룹 {g}: 일치율 {_pct(n['match_rate'])} (대화 {n['conversations']}개)")
    if result["stopped_by_cost_cap"]:
        lines.append(f"비용 상한(${result['max_cost_usd']})으로 멈춤: 남은 대화를 시작하지 않음")
    return lines
