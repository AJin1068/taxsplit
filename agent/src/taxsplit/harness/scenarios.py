"""시나리오 읽기. 형식 검사는 채점 코드(score.check_scenario) 것을 그대로 쓴다.

기준 정답(gold)·빈 곳 정답(gaps_expected)은 채점 코드에만 넘긴다.
에이전트·가상 사용자에게는 public_view만 준다.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from taxsplit.harness.scoring import score_module


class ScenarioError(ValueError):
    """시나리오 폴더·파일 형식이 틀림. 메시지에 파일 이름과 칸이 들어 있다."""


# 실행기·가상 사용자가 보면 안 되는 칸(정답·검수 기록)
HIDDEN_KEYS = ("gold", "review", "gaps_expected")


def load_scenarios(
    folders: Path | list[Path], only: list[str] | None = None
) -> list[dict[str, Any]]:
    """폴더(여러 개 가능)의 *.json을 id 순으로 읽는다. 하나라도 틀리면 ScenarioError로 멈춘다.

    여러 폴더를 한 번에 돌릴 때(예: v0 + v1) 시나리오 id가 폴더끼리 겹치면 시작 전에 멈춘다.
    """
    folders = [folders] if isinstance(folders, Path) else folders
    out = [s for folder in folders for s in _load_folder(folder)]
    dup = sorted(i for i, n in Counter(s["id"] for s in out).items() if n > 1)
    if dup:
        raise ScenarioError(f"시나리오 id가 겹칩니다: {dup}")
    out.sort(key=lambda s: s["id"])
    if only:
        missing = sorted(set(only) - {s["id"] for s in out})
        if missing:
            raise ScenarioError(f"--only: 없는 시나리오 id {missing}")
        out = [s for s in out if s["id"] in only]
    return out


def _load_folder(folder: Path) -> list[dict[str, Any]]:
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
    return out


def public_view(scenario: dict[str, Any]) -> dict[str, Any]:
    """정답(기준 정답·빈 곳 정답)과 검수 기록을 뺀 시나리오. 실행기와 가상 사용자는 이것만 본다."""
    return {k: v for k, v in scenario.items() if k not in HIDDEN_KEYS}
