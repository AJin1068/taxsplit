"""답 외우기 검사 도구: 시나리오 id·부양가족 이름이 처리 코드·프롬프트에 들어 있는지 찾는다.

docs/design.md 7장 "답 외우기 검사". 일반 낱말("어머니")은 찾지 않고, 시나리오에 실제로 적힌
id와 이름만 찾는다. 테스트 코드(agent/tests/)는 보지 않는다.
"""

import json
from pathlib import Path

# 처리 코드와 프롬프트·설정 파일. 캐시(__pycache__)는 보지 않는다
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml"}


def secrets_of(scenarios_root: Path) -> set[str]:
    """시나리오 폴더(하위 폴더 포함)의 id와 부양가족 이름."""
    found: set[str] = set()
    for path in scenarios_root.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "id" not in data:
            continue
        found.add(data["id"])
        for m in data.get("household", {}).get("members", []):
            found.add(m["dependent"]["name"])
    return found


def leaks(code_root: Path, secrets: set[str]) -> list[str]:
    """'파일: 찾은 것' 목록. 비어 있으면 통과."""
    out = []
    for path in sorted(code_root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = sorted(s for s in secrets if s in text)
        if hits:
            out.append(f"{path.relative_to(code_root)}: {', '.join(hits)}")
    return out
