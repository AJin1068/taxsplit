"""시나리오의 기준 정답(`gold`)을 검증된 계산 엔진으로 채운다 (ADR-0004 정답 사슬, #20 메모).

실행 (agent/ 폴더에서, 계산 엔진을 쓰므로):
    uv run python ../eval/scenarios/make_gold.py --engine-commit <커밋>          # draft 채우기
    uv run python ../eval/scenarios/make_gold.py --engine-commit <커밋> --check  # 쓰지 않고 비교만

규칙:
1. 같은 입력이면 같은 결과: 시각·난수를 쓰지 않고 정렬을 고정한다. 엔진 커밋은 인자로 받는다.
2. `status: confirmed` 시나리오의 `gold`는 덮어쓰지 않는다. 엔진을 고쳐 값이 달라졌으면
   차이를 출력하고 1로 끝난다(사람이 다시 검수).
"""

import argparse
import json
import sys
from pathlib import Path

from taxsplit.allocation import Household
from taxsplit.allocation.compare import compare_allocations
from taxsplit.rules.loader import load_rules

EVAL = Path(__file__).resolve().parent.parent
DEFAULT_DIR = EVAL / "scenarios" / "v0"
CASE_DIRS = {
    "국세청 사례": EVAL / "cases" / "nts-2025",
    "홈택스 모의계산": EVAL / "cases" / "hometax-2025",
}


def confirmed_cases() -> dict[str, int]:
    """정답 사슬 문장에 쓸 바깥 정답 사례 수(status: confirmed만)."""
    out = {}
    for label, folder in CASE_DIRS.items():
        n = 0
        for path in sorted(folder.glob("*.json")):
            if json.loads(path.read_text(encoding="utf-8")).get("status") == "confirmed":
                n += 1
        out[label] = n
    return out


def _plan_key(a: dict) -> list:
    return sorted(a.items())


def make_gold(scenario: dict, rules: dict, commit: str, cases: dict[str, int]) -> dict:
    h = Household.model_validate(scenario["household"])
    r = compare_allocations(h, rules)
    plans = sorted(
        ({"assignment": dict(sorted(p.assignment.items())), "total": p.total} for p in r.plans),
        key=lambda p: (p["total"], _plan_key(p["assignment"])),
    )
    best = sorted((dict(sorted(p.assignment.items())) for p in r.best_plans), key=_plan_key)
    chain = ", ".join(f"{k} {v}건" for k, v in cases.items())
    return {
        "plan_count": r.plan_count,
        "best_assignments": best,
        "best_total": r.best.total,
        "plans": plans,
        "headline_saving": r.headline_saving,
        "members": [
            {"name": m.name, "relation": m.dependent.relation, "birth_year": m.dependent.birth_year}
            for m in h.members
        ],
        "engine": {
            "commit": commit,
            "chain": (
                f"{chain}으로 검증한 계산 엔진(2025년 귀속 규칙표, 배분 비교)이 만든 기준 정답"
            ),
        },
    }


def _without_commit(gold: dict | None) -> dict | None:
    if gold is None:
        return None
    g = json.loads(json.dumps(gold))
    g.get("engine", {}).pop("commit", None)
    return g


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--engine-commit", required=True)
    ap.add_argument("--check", action="store_true", help="파일을 쓰지 않고 차이만 본다")
    args = ap.parse_args(argv)

    rules = load_rules(2025)
    cases = confirmed_cases()
    changed, blocked = [], []
    for path in sorted(args.scenarios.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        new = make_gold(data, rules, args.engine_commit, cases)
        same = _without_commit(data.get("gold")) == _without_commit(new)
        if data.get("status") == "confirmed":
            if not same:
                blocked.append(path.name)
                print(f"[차이] {path.name}: confirmed 기준 정답과 엔진 결과가 다름. 덮어쓰지 않음")
                print(f"  지금: {json.dumps(data.get('gold'), ensure_ascii=False)}")
                print(f"  엔진: {json.dumps(new, ensure_ascii=False)}")
            continue
        if data.get("gold") == new:
            continue
        changed.append(path.name)
        if not args.check:
            data["gold"] = new
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verb = "바뀔" if args.check else "바꾼"
    print(f"{verb} draft {len(changed)}개: {', '.join(changed) or '-'}")
    print(f"confirmed 차이 {len(blocked)}개: {', '.join(blocked) or '-'}")
    if blocked or (args.check and changed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
