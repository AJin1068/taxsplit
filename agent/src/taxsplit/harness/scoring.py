"""eval/scoring/score.py를 파일 경로로 불러 쓴다(복사·수정하지 않음, Issue #20 정해진 결정).

채점 규칙과 숫자는 모두 그 파일이 정한다. 이 모듈은 불러오기만 한다.
"""

import importlib.util
from functools import cache
from pathlib import Path
from types import ModuleType

# agent/src/taxsplit/harness/scoring.py → 레포 맨 위
REPO_ROOT = Path(__file__).resolve().parents[4]
SCORE_PATH = REPO_ROOT / "eval" / "scoring" / "score.py"
DEFAULT_SCENARIOS = REPO_ROOT / "eval" / "scenarios" / "v0"


@cache
def score_module(path: Path = SCORE_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location("taxsplit_eval_score", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"채점 코드를 불러오지 못했습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
