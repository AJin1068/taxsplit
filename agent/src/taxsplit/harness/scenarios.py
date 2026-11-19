"""시나리오 읽기. 형식 검사는 채점 코드(score.check_scenario) 것을 그대로 쓴다.

기준 정답(gold)은 채점 코드에만 넘긴다. 에이전트·가상 사용자에게는 public_view만 준다.
"""

import json
from pathlib import Path
from typing import Any

from taxsplit.harness.scoring import score_module


class ScenarioError(ValueError):
    """시나리오 폴더·파일 형식이 틀림. 메시지에 파일 이름과 칸이 들어 있다."""


def load_scenarios(folder: Path, only: list[str] | None = None) -> list[dict[str, Any]]:
    """폴더의 *.json을 id 순으로 읽는다. 하나라도 틀리면 ScenarioError로 멈춘다."""
    if not folder.is_dir():
        raise ScenarioError(f"시나리오 폴더가 없습니다: {folder}")
    check = score_module().check_scenario
    out = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ScenarioError(f"{path.name}: JSON 형식이 틀렸습니다 ({e.lineno}줄)") from e
        if not isinstance(data, dict):
            raise ScenarioError(f"{path.name}: 맨 위가 객체여야 합니다")
        errs = check(data)
        if errs:
            raise ScenarioError(f"{path.name}: " + "; ".join(errs))
        out.append(data)
    if not out:
        raise ScenarioError(f"시나리오 폴더에 *.json이 없습니다: {folder}")
    out.sort(key=lambda s: s["id"])
    if only:
        missing = sorted(set(only) - {s["id"] for s in out})
        if missing:
            raise ScenarioError(f"--only: 없는 시나리오 id {missing}")
        out = [s for s in out if s["id"] in only]
    return out


def public_view(scenario: dict[str, Any]) -> dict[str, Any]:
    """기준 정답·검수 기록을 뺀 시나리오. 실행기와 가상 사용자는 이것만 본다."""
    return {k: v for k, v in scenario.items() if k not in ("gold", "review")}
